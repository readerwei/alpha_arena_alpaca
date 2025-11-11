import asyncio
from types import SimpleNamespace

from app.models import ExitPlan
from app.trading_engine.portfolio import Portfolio


class InMemoryExitPlanStore:
    def __init__(self):
        self.saved = {}

    def load(self):
        return {}

    def save(self, plans):
        self.saved = plans.copy()


async def _run_buy_and_status():
    store = InMemoryExitPlanStore()
    portfolio = Portfolio(initial_cash=10000.0, exit_plan_store=store)

    plan = ExitPlan(
        profit_target=150.0, stop_loss=90.0, invalidation_condition="test"
    )
    await portfolio.execute_trade(
        symbol="AAPL", action="BUY", quantity=5, price=120.0, exit_plan=plan
    )

    status = await portfolio.get_status()
    return portfolio, store, status


def test_portfolio_tracks_local_positions_when_mock_alpaca(monkeypatch):
    portfolio, store, status = asyncio.run(_run_buy_and_status())

    local_pos = portfolio._local_positions["AAPL"]
    assert local_pos.quantity == 5
    assert local_pos.average_price == 120.0
    assert store.saved["AAPL"].profit_target == 150.0

    # The fallback should expose the position via PortfolioStatus even though Alpaca returned none.
    assert "AAPL" in status.positions
    assert status.positions["AAPL"].quantity == 5


def test_portfolio_removes_local_position_on_sell():
    portfolio, store, _ = asyncio.run(_run_buy_and_status())

    asyncio.run(
        portfolio.execute_trade(symbol="AAPL", action="SELL", quantity=5, price=125.0)
    )

    assert "AAPL" not in portfolio._local_positions
    assert "AAPL" not in store.saved
