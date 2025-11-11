import asyncio

from app.llm.base import BaseLLMProvider
from app.models import ExitPlan, Position, PortfolioStatus, PositionDetails
from app.trading_engine import agent as agent_module
from app.trading_engine.agent import Agent


class DummyProvider(BaseLLMProvider):
    async def get_trade_decision(self, prompt: str):
        raise NotImplementedError


class StubPortfolio:
    def __init__(self, status: PortfolioStatus):
        self._status = status
        self.executed = []

    async def get_status(self) -> PortfolioStatus:
        return self._status

    async def execute_trade(
        self, symbol: str, action: str, quantity: float, price: float, exit_plan=None
    ):
        self.executed.append((symbol, action, quantity, price, exit_plan))


def _build_portfolio_status(exit_plan: ExitPlan, quantity: float = 10.0) -> PortfolioStatus:
    position = Position(
        symbol="AAPL",
        quantity=quantity,
        average_price=100.0,
        exit_plan=exit_plan,
    )
    detail = PositionDetails(
        symbol="AAPL",
        quantity=quantity,
        entry_price=100.0,
        current_price=110.0,
        liquidation_price=90.0,
        unrealized_pnl=100.0,
        leverage=1,
        exit_plan=exit_plan,
        confidence=0.5,
        risk_usd=100.0,
        sl_oid=0,
        tp_oid=0,
        wait_for_fill=False,
        entry_oid=0,
        notional_usd=quantity * 110.0,
    )
    return PortfolioStatus(
        cash=1000.0,
        positions={"AAPL": position},
        live_positions_details=[detail],
        total_value=2000.0,
        pnl=500.0,
        total_return_percent=5.0,
        sharpe_ratio=1.2,
    )


def test_exit_conditions_trigger_take_profit(monkeypatch):
    exit_plan = ExitPlan(profit_target=120.0, stop_loss=80.0, invalidation_condition="")
    status = _build_portfolio_status(exit_plan)
    stub_portfolio = StubPortfolio(status)

    agent = Agent("test", "Test Agent", DummyProvider("dummy"))
    agent.portfolio = stub_portfolio

    monkeypatch.setattr(
        agent_module, "get_current_prices", lambda symbols: {"AAPL": 125.0}
    )

    asyncio.run(agent._check_exit_conditions())

    assert stub_portfolio.executed == [("AAPL", "SELL", 10.0, 125.0, None)]


def test_exit_conditions_trigger_stop_loss(monkeypatch):
    exit_plan = ExitPlan(profit_target=150.0, stop_loss=90.0, invalidation_condition="")
    status = _build_portfolio_status(exit_plan)
    stub_portfolio = StubPortfolio(status)

    agent = Agent("test2", "Test Agent 2", DummyProvider("dummy"))
    agent.portfolio = stub_portfolio

    monkeypatch.setattr(
        agent_module, "get_current_prices", lambda symbols: {"AAPL": 85.0}
    )

    asyncio.run(agent._check_exit_conditions())

    assert stub_portfolio.executed == [("AAPL", "SELL", 10.0, 85.0, None)]
