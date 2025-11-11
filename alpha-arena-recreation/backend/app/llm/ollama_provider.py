import httpx
import json
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

    async def get_trade_decision(self, prompt: str) -> LLMTradeDecisionList:
        """
        Sends the prompt to the Ollama server and gets a trade decision.
        """
        print(f"Sending prompt to Ollama model: {self.model_name} at {self.url}")
        
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

                response_data = response.json()
                
                # The actual JSON content is in the 'response' key
                json_content_str = response_data.get("response", "{}")
                
                # The response might contain markdown ```json ... ```, let's strip it
                if json_content_str.startswith("```json"):
                    json_content_str = json_content_str[7:]
                if json_content_str.endswith("```"):
                    json_content_str = json_content_str[:-3]
                
                json_content = json.loads(json_content_str.strip())

                print("Received response from Ollama:", json_content)
                
                # Validate with Pydantic
                decisions = LLMTradeDecisionList(**json_content)
                return decisions

        except httpx.RequestError as e:
            print(f"Error making request to Ollama: {e}")
            # Fallback to a 'hold' decision on error
            return self._get_fallback_decision()
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Ollama: {e}")
            print(f"Raw response content: {response_data.get('response')}")
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
