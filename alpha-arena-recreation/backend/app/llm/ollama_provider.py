import httpx
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.llm.base import BaseLLMProvider
from app.models import LLMTradeDecision, LLMTradeDecisionList
from app.config import settings

class OllamaProvider(BaseLLMProvider):
    """
    An LLM provider that connects to an Ollama server.
    """
    def __init__(self, model_name: str, url: str):
        super().__init__(model_name)
        self.chat_url = f"{url}/api/chat"
        self.prompt_log_path = settings.PROJECT_ROOT / "logging" / "ollama_prompts.log"
        self.prompt_log_path.parent.mkdir(parents=True, exist_ok=True)

    async def get_trade_decision(self, prompt: str) -> LLMTradeDecisionList:
        """
        Sends the prompt to the Ollama server and gets a trade decision.
        """
        print(f"Sending prompt to Ollama model: {self.model_name} at {self.chat_url}")
        self._log_prompt(prompt)
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,  # Request a single response payload
            "think": True,  # Capture reasoning traces if the model emits them
        }

        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = await client.post(self.chat_url, json=payload)
                response.raise_for_status() # Raise an exception for bad status codes

                try:
                    response_data = response.json()
                except json.JSONDecodeError as exc:
                    print(f"Error decoding Ollama HTTP payload: {exc}. Raw: {response.text[:200]}")
                    return self._get_fallback_decision()

                api_error = response_data.get("error")
                if api_error:
                    print(f"Ollama API returned an error: {api_error}")
                    return self._get_fallback_decision()

                message_block = response_data.get("message") or {}
                message_content = message_block.get("content", "")
                thinking_trace = message_block.get("thinking")

                json_content = self._deserialize_response_payload(message_content)
                try:
                    normalized_payload = self._normalize_decisions(json_content)
                except ValueError as exc:
                    print(f"Ollama response normalization failed: {exc}")
                    print("Raw Ollama content:", message_content)
                    raise

                print("Received response from Ollama:", json_content)
                if thinking_trace:
                    print("Ollama reasoning trace:", thinking_trace)
                self._log_response(json_content, thinking_trace)
                
                # Validate with Pydantic
                decisions = LLMTradeDecisionList(**normalized_payload)
                return decisions

        except httpx.RequestError as e:
            print(f"Error making request to Ollama: {e} ({e.__class__.__name__})")
            # Fallback to a 'hold' decision on error
            return self._get_fallback_decision()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Ollama: {e}")
            # response_data may be undefined if decoding of HTTP payload failed earlier.
            raw_response = locals().get("response_data")
            if raw_response:
                message_block = raw_response.get("message") or {}
                print(f"Raw response content: {message_block.get('content')}")
            else:
                print("Raw response content unavailable due to earlier failure.")
            return self._get_fallback_decision()
        except Exception as e:
            print(f"An unexpected error occurred with Ollama provider: {e}")
            return self._get_fallback_decision()

    def _get_fallback_decision(self) -> LLMTradeDecisionList:
        """Returns a default 'hold' decision in case of an error."""
        return LLMTradeDecisionList(decisions=[
            LLMTradeDecision(
                symbol="N/A",
                signal="hold",
                confidence=0.0,
                justification="Fell back to default 'hold' due to an error in the LLM provider."
            )
        ])

    def _deserialize_response_payload(self, message_content: str) -> dict[str, Any]:
        """
        Extracts and cleans the JSON content emitted by Ollama. Even in chat mode models may wrap
        their JSON in markdown fences or prepend explanatory text, so we normalize before loading.
        """
        json_content_str = message_content or ""

        if not json_content_str:
            raise json.JSONDecodeError("Empty response payload from Ollama.", "", 0)

        cleaned = json_content_str.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Some models may preface text before the first JSON object—trim to the outer braces.
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end >= brace_start:
            candidate = cleaned[brace_start : brace_end + 1]
        else:
            candidate = cleaned

        if "Invalid JSON" in candidate:
            raise json.JSONDecodeError("Ollama reported invalid JSON output.", candidate, 0)

        return json.loads(candidate)

    def _log_prompt(self, prompt: str) -> None:
        """Append the outgoing prompt to the log file."""
        self._append_log_entry("PROMPT", prompt)

    def _log_response(self, payload: dict[str, Any], thinking: Optional[str] = None) -> None:
        """Append the parsed response (and optional reasoning trace) to the log file."""
        formatted = json.dumps(payload, indent=2, sort_keys=True)
        if thinking:
            formatted = f"{formatted}\n\nReasoning Trace:\n{thinking}"
        self._append_log_entry("RESPONSE", formatted)

    def _normalize_decisions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Ensures the Ollama response conforms to the LLMTradeDecisionList schema. Some models emit
        decision dictionaries keyed by symbol with nested {action, reason} objects; convert those
        into the expected list of decision dicts.
        """
        decisions = payload.get("decisions")
        if decisions is None:
            # Some models omit the wrapper and return {symbol: {...}} directly.
            if all(
                isinstance(v, dict)
                and any(k in v for k in ("signal", "action", "decision"))
                for v in payload.values()
            ):
                decisions = payload
            else:
                raise ValueError("Ollama response missing 'decisions' key.")

        if isinstance(decisions, list):
            return payload

        if isinstance(decisions, dict):
            normalized_list: list[dict[str, Any]] = []
            for symbol, decision_data in decisions.items():
                if not isinstance(decision_data, dict):
                    continue
                action = decision_data.get("signal") or decision_data.get("action")
                if not action:
                    continue
                normalized_list.append(
                    {
                        "symbol": symbol,
                        "signal": action,
                        "confidence": decision_data.get("confidence", 0.5),
                        "justification": decision_data.get("justification") or decision_data.get("reason") or "",
                        "reasoning_trace": decision_data.get("reasoning_trace"),
                        "stop_loss": decision_data.get("stop_loss"),
                        "leverage": decision_data.get("leverage"),
                        "risk_usd": decision_data.get("risk_usd"),
                        "profit_target": decision_data.get("profit_target"),
                        "quantity": decision_data.get("quantity"),
                        "invalidation_condition": decision_data.get("invalidation_condition"),
                    }
                )
            payload["decisions"] = normalized_list
            return payload

        raise ValueError("Ollama response 'decisions' must be a list or dict.")

    def _append_log_entry(self, label: str, content: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        entry_lines = [
            f"[{timestamp} UTC] {label}",
            content.rstrip(),
            "=" * 80,
            "",
        ]
        try:
            with self.prompt_log_path.open("a", encoding="utf-8") as logfile:
                logfile.write("\n".join(entry_lines))
        except OSError as exc:
            print(f"Warning: Failed to write Ollama prompt log: {exc}")
