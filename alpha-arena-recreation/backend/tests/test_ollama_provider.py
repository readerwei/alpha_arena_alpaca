import asyncio
import base64
import json
import os
import sys
from pathlib import Path

import httpx
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


SAMPLE_RED_PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)


def _create_dummy_candlestick_chart(destination: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 2))
    x_values = [0, 1, 2, 3, 4, 5]
    prices = [150, 152, 149, 151, 148, 147]
    ax.plot(x_values, prices, color="#d62728", linewidth=2)
    ax.set_title("Test Candlestick Snapshot")
    ax.set_xlabel("Day")
    ax.set_ylabel("Price")
    fig.tight_layout()
    fig.savefig(destination, format="png")
    plt.close(fig)
    return destination


def test_get_trade_decision_sends_image_payload(monkeypatch, tmp_path):
    """
    Ensure that when an image path is provided the provider sends a base64-encoded attachment.
    """
    provider = _provider()
    provider.prompt_log_path = tmp_path / "ollama_prompts.log"
    provider.prompt_log_path.parent.mkdir(parents=True, exist_ok=True)

    image_path = tmp_path / "candles.png"
    image_bytes = base64.b64decode(SAMPLE_RED_PIXEL)
    image_path.write_bytes(image_bytes)
    expected_encoded = base64.b64encode(image_bytes).decode("ascii")

    captured_payloads: list[dict[str, object]] = []

    def _mock_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        captured_payloads.append(payload)
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": _sample_decision_payload(),
                    "thinking": "vision mode test",
                }
            },
        )

    transport = httpx.MockTransport(_mock_handler)
    real_async_client = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)

    async def _run_provider():
        return await provider.get_trade_decision(
            "Analyze the candlestick snapshot and respond.", [str(image_path)]
        )

    decisions = asyncio.run(_run_provider())
    assert decisions.decisions, "Expected parsed decisions from mock Ollama response."
    assert captured_payloads, "Ollama provider never issued an HTTP request."

    user_message = captured_payloads[0]["messages"][1]
    assert user_message["content"].startswith("Analyze the candlestick snapshot")
    assert user_message["images"] == [expected_encoded]


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OLLAMA_TEST_URL"),
    reason="Set OLLAMA_TEST_URL (and optionally OLLAMA_TEST_MODEL) to run integration test.",
)
def test_real_ollama_provider_returns_decisions(tmp_path):
    """
    Hits a real Ollama endpoint (if configured) and ensures the provider parses JSON.
    """
    url = os.environ["OLLAMA_TEST_URL"]
    model = os.getenv("OLLAMA_TEST_MODEL", "qwen3:4b")
    provider = OllamaProvider(model_name=model, url=url)
    image_path = _create_dummy_candlestick_chart(tmp_path / "integration_chart.png")

    prompt = (
        "### CURRENT MARKET STATE\n"
        "Symbol: AAPL\n"
        "current_price = 100, current_ema20 = 99, current_macd = 1, current_rsi (7 period) = 55\n"
        "### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE\n"
        "Available Cash: 10000\n"
        "Sharpe Ratio: 0.5\n"
        "Provide exactly one hold decision for AAPL referencing this minimal dataset and the attached candlestick snapshot."
    )

    decisions = asyncio.run(provider.get_trade_decision(prompt, [str(image_path)]))
    assert decisions.decisions, "Expected at least one decision from real Ollama server."
    assert decisions.decisions[0].symbol.upper() == "AAPL"


def run_ollama_provider_tests() -> int:
    """Allow running this module directly via `python tests/test_ollama_provider.py`."""
    return pytest.main([__file__])


if __name__ == "__main__":
    raise SystemExit(run_ollama_provider_tests())
