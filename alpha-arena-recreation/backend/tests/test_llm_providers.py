import asyncio
import random

import pytest

from app.config import settings
from app.llm.mock_provider import MockLLMProvider


def test_mock_llm_provider_generates_deterministic_trade(monkeypatch):
    monkeypatch.setattr(settings, "TRADE_SYMBOLS", ["BTCUSDT"])

    choice_values = iter(["BTC", "buy_to_enter", 20])

    def fake_choice(_options):
        return next(choice_values)

    uniform_values = iter([101000.0, 800.0, 112000.0, 0.42, 0.9])

    def fake_uniform(_a, _b):
        return next(uniform_values)

    monkeypatch.setattr(random, "choice", fake_choice)
    monkeypatch.setattr(random, "uniform", fake_uniform)

    provider = MockLLMProvider(model_name="mock")

    decisions = asyncio.run(provider.get_trade_decision("prompt"))
    assert len(decisions.decisions) == 1

    decision = decisions.decisions[0]
    assert decision.symbol == "BTC"
    assert decision.signal == "buy_to_enter"
    assert decision.leverage == 20
    assert decision.stop_loss == pytest.approx(101000.0)
    assert decision.profit_target == pytest.approx(112000.0)
    assert decision.quantity == pytest.approx(0.42)
    assert decision.risk_usd == pytest.approx(800.0)
    assert decision.confidence == pytest.approx(0.9)
    assert decision.invalidation_condition == "BTC breaks below 101000.0"
