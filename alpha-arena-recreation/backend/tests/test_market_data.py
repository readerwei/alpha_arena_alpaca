import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.data import market_data


def _build_mock_history(rows: int = 120) -> pd.DataFrame:
    """Create deterministic OHLCV data for indicator calculations."""
    index = pd.date_range("2023-01-01", periods=rows, freq="D")
    base = np.linspace(100, 200, rows)
    data = pd.DataFrame(
        {
            "Open": base + 0.5,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base,
            "Volume": np.linspace(1_000, 5_000, rows),
        },
        index=index,
    )
    return data


def test_get_detailed_market_data_builds_expected_sections(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_MARKET_DATA", False)
    monkeypatch.setattr(settings, "SAVE_CANDLESTICK_CHARTS", False)
    mock_df = _build_mock_history()

    def fake_download(*args, **kwargs):
        return mock_df.copy()

    monkeypatch.setattr(market_data.yf, "download", fake_download)

    result = market_data.get_detailed_market_data(["TEST"])
    assert "TEST" in result

    test_data = result["TEST"]
    current = test_data["current"]
    intraday = test_data["intraday_series"]
    longer = test_data["longer_term_context"]
    visuals = test_data["visuals"]["candlestick_chart"]

    assert current["current_price"] == pytest.approx(mock_df["Close"].iloc[-1])
    assert isinstance(current["current_ema20"], float)
    assert isinstance(current["current_macd"], float)
    assert isinstance(current["current_rsi7"], float)

    assert len(intraday["mid_prices"]) == 10
    assert len(intraday["ema_indicators"]) == 10
    assert len(intraday["macd_indicators"]) == 10
    assert len(intraday["rsi7_indicators"]) == 10
    assert len(intraday["rsi14_indicators"]) == 10

    assert isinstance(longer["ema20"], float)
    assert isinstance(longer["ema50"], float)
    assert isinstance(longer["atr3"], float)
    assert isinstance(longer["atr14"], float)
    assert visuals["data_uri"].startswith("data:image/png;base64,")
    assert visuals["lookback_bars"] > 0
    assert visuals["interval"] == "1d"
    assert "saved_path" in visuals
    assert visuals["saved_path"] is None


def test_get_current_prices_uses_regular_price_and_history(monkeypatch):
    monkeypatch.setattr(settings, "USE_MOCK_MARKET_DATA", False)
    class InfoTicker:
        def __init__(self):
            self.info = {"regularMarketPrice": 123.45}

        def history(self, period: str):
            # Should not be needed when info price exists, but return a different value to
            # ensure the regular market price is still preferred.
            return pd.DataFrame({"Close": [77.77]})

    class HistoryTicker:
        def __init__(self):
            self.info = {}

        def history(self, period: str):
            return pd.DataFrame({"Close": [98.76]})

    def fake_ticker(symbol: str):
        return InfoTicker() if symbol == "INFO" else HistoryTicker()

    monkeypatch.setattr(market_data.yf, "Ticker", fake_ticker)

    prices = market_data.get_current_prices(["INFO", "FALLBACK"])

    assert prices["INFO"] == 123.45
    assert prices["FALLBACK"] == pytest.approx(98.76, rel=1e-6)


def run_exit_condition_tests() -> int:
    """Expose this module's pytest execution as a callable helper."""
    import pytest

    return pytest.main([__file__])


if __name__ == "__main__":
    raise SystemExit(run_exit_condition_tests())
