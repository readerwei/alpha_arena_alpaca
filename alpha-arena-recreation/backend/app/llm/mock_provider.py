import random
import asyncio
from app.llm.base import BaseLLMProvider
from app.models import LLMTradeDecision, LLMTradeDecisionList
from app.config import settings

class MockLLMProvider(BaseLLMProvider):
    """
    A mock LLM provider that returns random trade decisions for testing.
    """
    async def get_trade_decision(
        self, prompt: str, images: list[str] | None = None
    ) -> LLMTradeDecisionList:
        """
        Ignores the prompt and returns a randomized trade decision in a list.
        """
        await asyncio.sleep(0) # Simulate async operation
        symbol = random.choice([s.replace("USDT", "") for s in settings.TRADE_SYMBOLS])
        signal = random.choice(["buy_to_enter", "sell_to_enter", "hold", "close"])
        
        # Default values for optional fields
        stop_loss = None
        leverage = None
        risk_usd = None
        profit_target = None
        quantity = None
        invalidation_condition = None

        if signal in ["buy_to_enter", "sell_to_enter"]:
            # Populate optional fields for buy/sell signals
            stop_loss = round(random.uniform(100000, 107000) if "BTC" in symbol else random.uniform(3000, 3500), 2)
            leverage = random.choice([10, 20, 50])
            risk_usd = round(random.uniform(500, 1500), 2)
            profit_target = round(random.uniform(108000, 115000) if "BTC" in symbol else random.uniform(3500, 4500), 2)
            quantity = round(random.uniform(0.01, 1.0), 2) # Example quantity
            invalidation_condition = f"{symbol} breaks below {stop_loss}"

        decision = LLMTradeDecision(
            symbol=symbol,
            signal=signal,
            confidence=round(random.uniform(0.5, 1.0), 2),
            justification="This is a mock decision based on random choice. The LLM observed a simulated pattern and decided to act.",
            stop_loss=stop_loss,
            leverage=leverage,
            risk_usd=risk_usd,
            profit_target=profit_target,
            quantity=quantity,
            invalidation_condition=invalidation_condition
        )
        return LLMTradeDecisionList(decisions=[decision])
