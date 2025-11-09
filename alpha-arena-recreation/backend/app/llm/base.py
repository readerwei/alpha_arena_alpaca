from abc import ABC, abstractmethod
from app.models import LLMTradeDecisionList

class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    """
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    async def get_trade_decision(self, prompt: str) -> LLMTradeDecisionList:
        """
        Takes a prompt with market data and portfolio status and returns a trade decision.
        """
        pass

    def __str__(self):
        return f"{self.__class__.__name__}({self.model_name})"
