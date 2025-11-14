import httpx
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.llm.base import BaseLLMProvider
from app.models import LLMTradeDecision, LLMTradeDecisionList
from app.config import settings

class ChatUnavailableError(Exception):
    """Raised when the Ollama chat endpoint is not available for the target model."""

class OllamaProvider(BaseLLMProvider):
    """
    An LLM provider that connects to an Ollama server.
    """
    def __init__(self, model_name: str, url: str):
        super().__init__(model_name)
        self.chat_url = f"{url}/api/chat"
        self.generate_url = f"{url}/api/generate"
        self.prompt_log_path = settings.PROJECT_ROOT / "logging" / "ollama_prompts.log"
        self.prompt_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.system_prompt = (
            "You are an autonomous equity trader. Every response must be valid JSON with the schema: "
            '{"decisions": [{"symbol": str, "signal": "buy_to_enter"|"sell_to_enter"|"hold"|"close", '
            '"confidence": float (0–1), "justification": str, "reasoning_trace": str, '
            '"stop_loss": float|null, "profit_target": float|null, "quantity": float|null, '
            '"invalidation_condition": str|null, "leverage": int|null, "risk_usd": float|null}]}.\n\n'
            "When thinking through a cycle:\n"
            "1. Current Position Review — summarize each open holding (entry price, current price, exit plan, unrealized PnL, conviction) and call out whether exit-plan rules are satisfied.\n"
            "2. Market Analysis — interpret the provided daily/weekly EMA, MACD, RSI, ATR, and volume for every allowed symbol; highlight opportunities even if you stay flat.\n"
            "3. Position Management — for held names explain whether to hold/close/add/reverse and cite the exact exit-plan clause or signal; for new trades include quantity, risk_usd, stop_loss, profit_target, and invalidation_condition.\n"
            "4. Strategic Assessment — outline the broader thesis linking your decisions (momentum, mean reversion, catalysts) and note triggers that would invalidate it.\n"
            "5. Risk Assessment — describe portfolio-level risk (exposure concentration, cash, drawdown) and ensure every trade has explicit risk controls.\n\n"
            "Formatting rules:\n"
            "- Always return {\"decisions\": [...]} with an array; never key by symbol.\n"
            "- Fill reasoning_trace with the multi-step thought process (signals reviewed, comparisons, risk checks).\n"
            "- Confidence must be a numeric probability.\n"
            "- If you skip a symbol, omit it from the array.\n"
            "- Output raw JSON only (no markdown, prose, or extra keys)."
        )

    async def get_trade_decision(self, prompt: str) -> LLMTradeDecisionList:
        """
        Sends the prompt to the Ollama server and gets a trade decision.
        """
        print(f"Sending prompt to Ollama model: {self.model_name} at {self.chat_url}")
        self._log_prompt(prompt)
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,  # Request a single response payload
            "think": True,  # Capture reasoning traces if the model emits them
        }

        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                try:
                    json_content, thinking_trace = await self._execute_chat_request(client, payload)
                except ChatUnavailableError:
                    print("Ollama chat endpoint unavailable for this model; falling back to /api/generate.")
                    json_content, thinking_trace = await self._execute_generate_request(client, prompt)

                normalized_payload = self._normalize_decisions(json_content)

                print("Received response from Ollama:", json_content)
                if thinking_trace:
                    print("Ollama reasoning trace:", thinking_trace)
                self._log_response(json_content, thinking_trace)
                
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

    async def _execute_chat_request(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], Optional[str]]:
        try:
            response = await client.post(self.chat_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ChatUnavailableError from exc
            raise

        try:
            response_data = response.json()
        except json.JSONDecodeError as exc:
            print(f"Error decoding Ollama HTTP payload: {exc}. Raw: {response.text[:200]}")
            raise

        api_error = response_data.get("error")
        if api_error:
            print(f"Ollama API returned an error: {api_error}")
            raise RuntimeError(api_error)

        message_block = response_data.get("message") or {}
        message_content = message_block.get("content", "")
        thinking_trace = message_block.get("thinking")

        json_content = self._deserialize_response_payload(message_content)
        return json_content, thinking_trace

    async def _execute_generate_request(
        self, client: httpx.AsyncClient, prompt: str
    ) -> tuple[dict[str, Any], Optional[str]]:
        prefixed_prompt = (
            f"{self.system_prompt}\n\nUSER PROMPT:\n{prompt}"
        )
        payload = {
            "model": self.model_name,
            "prompt": prefixed_prompt,
            "format": "json",
            "stream": False,
        }
        response = await client.post(self.generate_url, json=payload)
        response.raise_for_status()

        try:
            response_data = response.json()
        except json.JSONDecodeError as exc:
            print(f"Error decoding Ollama HTTP payload (generate): {exc}. Raw: {response.text[:200]}")
            raise

        api_error = response_data.get("error")
        if api_error:
            print(f"Ollama API returned an error: {api_error}")
            raise RuntimeError(api_error)

        message_content = response_data.get("response", "")
        json_content = self._deserialize_response_payload(message_content)
        return json_content, None

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
                print("Warning: Ollama response missing 'decisions'; defaulting to no-op decisions.")
                payload["decisions"] = []
                return payload

        if isinstance(decisions, list):
            return payload

        if isinstance(decisions, dict):
            normalized_list: list[dict[str, Any]] = []
            for symbol, decision_data in decisions.items():
                if not isinstance(decision_data, dict):
                    continue
                action = (
                    decision_data.get("signal")
                    or decision_data.get("action")
                    or decision_data.get("decision")
                )
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
