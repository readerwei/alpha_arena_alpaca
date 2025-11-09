from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from datetime import datetime


class Trade(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL"]
    quantity: float
    price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExitPlan(BaseModel):
    profit_target: float
    stop_loss: float
    invalidation_condition: str


class Position(BaseModel):
    symbol: str
    quantity: float
    average_price: float
    exit_plan: Optional[ExitPlan] = None


class PositionDetails(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    liquidation_price: float
    unrealized_pnl: float
    leverage: int
    exit_plan: Optional[ExitPlan] = None
    confidence: float
    risk_usd: float
    sl_oid: int
    tp_oid: int
    wait_for_fill: bool
    entry_oid: int
    notional_usd: float


class PortfolioStatus(BaseModel):
    cash: float
    positions: dict[str, Position]  # Simplified for internal tracking
    live_positions_details: list[PositionDetails]  # Detailed for LLM prompt
    total_value: float
    pnl: float
    total_return_percent: float
    sharpe_ratio: float


class LLMTradeDecision(BaseModel):
    symbol: str  # Renamed from coin
    signal: Literal[
        "buy_to_enter", "sell_to_enter", "hold", "close"
    ]  # More specific actions
    confidence: float = Field(ge=0, le=1)
    justification: str  # Renamed from reasoning

    # New fields from the prompt example
    stop_loss: Optional[float] = None
    leverage: Optional[int] = None
    risk_usd: Optional[float] = None
    profit_target: Optional[float] = None
    quantity: Optional[float] = (
        None  # This seems to be a percentage or ratio in the example
    )
    invalidation_condition: Optional[str] = None


class LLMTradeDecisionList(BaseModel):
    decisions: List[LLMTradeDecision]


class AgentState(BaseModel):
    agent_id: str
    name: str
    llm_provider: str
    portfolio: PortfolioStatus
    trade_history: list[Trade] = []
