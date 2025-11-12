import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.llm.base import BaseLLMProvider
from app.models import (
    ExitPlan,
    PortfolioStatus,
    Position,
    PositionDetails,
)
from app.trading_engine import agent as agent_module
from app.trading_engine.agent import Agent
from app.config import settings


class DummyProvider(BaseLLMProvider):
    async def get_trade_decision(self, prompt: str):
        raise NotImplementedError


class StubPortfolio:
    def __init__(self, status: PortfolioStatus):
        self._status = status

    async def get_status(self) -> PortfolioStatus:
        return self._status


def _make_portfolio_status() -> PortfolioStatus:
    exit_plan = ExitPlan(
        profit_target=46000.0,
        stop_loss=43000.0,
        invalidation_condition="BTC breaks structure",
    )
    position = Position(
        symbol="BTC",
        quantity=0.5,
        average_price=44000.0,
        exit_plan=exit_plan,
    )
    detail = PositionDetails(
        symbol="BTC",
        quantity=0.5,
        entry_price=44000.0,
        current_price=45000.0,
        liquidation_price=30000.0,
        unrealized_pnl=500.0,
        leverage=2,
        exit_plan=exit_plan,
        confidence=0.8,
        risk_usd=250.0,
        sl_oid=1,
        tp_oid=2,
        wait_for_fill=False,
        entry_oid=3,
        notional_usd=22500.0,
    )
    return PortfolioStatus(
        cash=1000.0,
        positions={"BTC": position},
        live_positions_details=[detail],
        total_value=23500.0,
        pnl=500.0,
        total_return_percent=5.0,
        sharpe_ratio=1.1,
    )


def test_generate_prompt_includes_market_and_portfolio_sections(monkeypatch):
    # Force single test symbol
    monkeypatch.setattr(settings, "TRADE_SYMBOLS", ["BTC"])

    detailed_snapshot = {
        "BTC": {
            "current": {
                "current_price": 45000.0,
                "current_ema20": 44800.0,
                "current_macd": 120.0,
                "current_rsi7": 65.0,
                "open_interest_latest": 25000.0,
                "open_interest_average": 24500.0,
                "funding_rate": 0.00001,
            },
            "intraday_series": {
                "mid_prices": [44000, 44500],
                "ema_indicators": [44200, 44750],
                "macd_indicators": [110, 120],
                "rsi7_indicators": [55, 60],
                "rsi14_indicators": [50, 55],
            },
            "longer_term_context": {
                "ema20": 44000.0,
                "ema50": 43000.0,
                "atr3": 500.0,
                "atr14": 900.0,
                "current_volume": 100000.0,
                "average_volume": 95000.0,
                "macd_indicators": [10, 11],
                "rsi14_indicators": [45, 47],
            },
        }
    }

    monkeypatch.setattr(
        agent_module, "get_detailed_market_data", lambda symbols: detailed_snapshot
    )

    portfolio_status = _make_portfolio_status()
    stub_portfolio = StubPortfolio(portfolio_status)

    agent = Agent("prompt-test", "Prompt Test", DummyProvider("mock"))
    agent.portfolio = stub_portfolio
    agent.start_time -= 600  # ensure elapsed_minutes > 0

    prompt = asyncio.run(agent._generate_prompt())

    assert "### ALL BTC DATA" in prompt
    assert "current_price = 45000.0" in prompt
    assert "Open Interest: Latest: 25000.0" in prompt
    assert "### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE" in prompt
    assert "\"symbol\": \"BTC\"" in prompt
    assert "provide a JSON object with a 'decisions' key" in prompt


def run_exit_condition_tests() -> int:
    """Expose this module's pytest execution as a callable helper."""
    import pytest

    return pytest.main([__file__])


if __name__ == "__main__":
    raise SystemExit(run_exit_condition_tests())
