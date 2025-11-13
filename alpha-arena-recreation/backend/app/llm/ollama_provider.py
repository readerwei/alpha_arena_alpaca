import httpx
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.llm.base import BaseLLMProvider
from app.models import LLMTradeDecision, LLMTradeDecisionList
from app.config import settings

class OllamaProvider(BaseLLMProvider):
    """
    An LLM provider that connects to an Ollama server.
    """
    def __init__(self, model_name: str, url: str):
        super().__init__(model_name)
        self.url = f"{url}/api/generate"
        self.prompt_log_path = settings.PROJECT_ROOT / "logging" / "ollama_prompts.log"
        self.prompt_log_path.parent.mkdir(parents=True, exist_ok=True)

    async def get_trade_decision(self, prompt: str) -> LLMTradeDecisionList:
        """
        Sends the prompt to the Ollama server and gets a trade decision.
        """
        print(f"Sending prompt to Ollama model: {self.model_name} at {self.url}")
        self._log_prompt(prompt)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "format": "json", # Request JSON output
            "stream": False # For simplicity, get the full response at once
        }

        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                response = await client.post(self.url, json=payload)
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

                json_content = self._deserialize_response_payload(response_data)

                print("Received response from Ollama:", json_content)
                self._log_response(json_content)
                
                # Validate with Pydantic
                decisions = LLMTradeDecisionList(**json_content)
                return decisions

        except httpx.RequestError as e:
            print(f"Error making request to Ollama: {e}")
            # Fallback to a 'hold' decision on error
            return self._get_fallback_decision()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Ollama: {e}")
            # response_data may be undefined if decoding of HTTP payload failed earlier.
            raw_response = locals().get("response_data")
            if raw_response:
                print(f"Raw response content: {raw_response.get('response')}")
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

    def _deserialize_response_payload(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extracts and cleans the JSON content emitted by Ollama. Ollama sometimes wraps JSON in
        markdown fences or returns plain-text error strings, so we normalize before loading.
        """
        json_content_str = response_data.get("response", "")

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

    def _log_response(self, payload: dict[str, Any]) -> None:
        """Append the parsed response to the log file."""
        formatted = json.dumps(payload, indent=2, sort_keys=True)
        self._append_log_entry("RESPONSE", formatted)

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
