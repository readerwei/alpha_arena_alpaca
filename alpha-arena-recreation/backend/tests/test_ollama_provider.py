import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.llm.ollama_provider import OllamaProvider  # noqa: E402


def _provider() -> OllamaProvider:
    return OllamaProvider(model_name="mock", url="http://localhost:11434")


def _sample_decision_payload() -> str:
    return json.dumps(
        {
            "decisions": [
                {
                    "symbol": "AAPL",
                    "signal": "hold",
                    "confidence": 0.5,
                    "justification": "test",
                }
            ]
        }
    )


def test_deserialize_plain_json():
    provider = _provider()
    result = provider._deserialize_response_payload(_sample_decision_payload())
    assert result["decisions"][0]["symbol"] == "AAPL"


def test_deserialize_strips_code_fences():
    provider = _provider()
    payload = f"```json\n{_sample_decision_payload()}\n```"
    result = provider._deserialize_response_payload(payload)
    assert result["decisions"][0]["signal"] == "hold"


def test_deserialize_trims_surrounding_text():
    provider = _provider()
    payload = (
        "Sure, here is what I recommend:\n"
        f"{_sample_decision_payload()}\n"
        "Let me know if you need anything else."
    )
    result = provider._deserialize_response_payload(payload)
    assert result["decisions"][0]["confidence"] == pytest.approx(0.5)


def test_deserialize_raises_for_invalid_json_message():
    provider = _provider()
    payload = "Invalid JSON: Expecting value: line 1 column 1 (char 0)"
    with pytest.raises(json.JSONDecodeError):
        provider._deserialize_response_payload(payload)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OLLAMA_TEST_URL"),
    reason="Set OLLAMA_TEST_URL (and optionally OLLAMA_TEST_MODEL) to run integration test.",
)
def test_real_ollama_provider_returns_decisions():
    """
    Hits a real Ollama endpoint (if configured) and ensures the provider parses JSON.
    """
    url = os.environ["OLLAMA_TEST_URL"]
    model = os.getenv("OLLAMA_TEST_MODEL", "qwen3:4b")
    provider = OllamaProvider(model_name=model, url=url)

    prompt = (
        "### CURRENT MARKET STATE\n"
        "Symbol: AAPL\n"
        "current_price = 100, current_ema20 = 99, current_macd = 1, current_rsi (7 period) = 55\n"
        "### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE\n"
        "Available Cash: 10000\n"
        "Sharpe Ratio: 0.5\n"
        "Provide exactly one hold decision for AAPL referencing this minimal dataset."
    )

    decisions = asyncio.run(provider.get_trade_decision(prompt))
    assert decisions.decisions, "Expected at least one decision from real Ollama server."
    assert decisions.decisions[0].symbol.upper() == "AAPL"


def run_ollama_provider_tests() -> int:
    """Allow running this module directly via `python tests/test_ollama_provider.py`."""
    return pytest.main([__file__])


if __name__ == "__main__":
    raise SystemExit(run_ollama_provider_tests())
