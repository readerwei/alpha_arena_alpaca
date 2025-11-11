from app.models import Position, PortfolioStatus, Trade, ExitPlan, PositionDetails
from app.data.market_data import get_current_prices
from app.alpaca.client import alpaca_client
from alpaca.trading.enums import OrderSide
import numpy as np
from typing import Optional, Dict
from app.storage.exit_plan_store import ExitPlanStore


class Portfolio:
    def __init__(
        self,
        initial_cash: float = 10000.0,
        exit_plan_store: Optional[ExitPlanStore] = None,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash  # This will eventually come from Alpaca account
        self.trade_history: list[Trade] = []
        self.pnl_history = [0.0]  # To calculate Sharpe Ratio
        self.exit_plan_store = exit_plan_store or ExitPlanStore()
        self.exit_plans: Dict[str, ExitPlan] = self.exit_plan_store.load()

    async def execute_trade(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        exit_plan: Optional[ExitPlan] = None,
    ):
        """
        Executes a trade via Alpaca API and updates the portfolio.
        """
        alpaca_symbol = symbol  # Alpaca uses direct symbols like AAPL, NVDA

        if action == "BUY":
            order = alpaca_client.submit_order(
                symbol=alpaca_symbol, qty=quantity, side=OrderSide.BUY
            )
            if order:
                print(
                    f"Alpaca BUY order submitted for {quantity} of {symbol}. Order ID: {order.id}"
                )
                # Store exit plan if provided
                if exit_plan:
                    self.exit_plans[symbol] = exit_plan
                    self.exit_plan_store.save(self.exit_plans)
            else:
                print(f"Failed to submit BUY order for {symbol}.")

        elif action == "SELL":
            # Check if we have an open position to sell
            alpaca_positions = alpaca_client.get_positions()
            current_alpaca_position = next(
                (p for p in alpaca_positions if p.symbol == alpaca_symbol), None
            )

            if current_alpaca_position:
                # If selling to close an existing position
                if float(current_alpaca_position.qty) >= quantity:
                    order = alpaca_client.submit_order(
                        symbol=alpaca_symbol, qty=quantity, side=OrderSide.SELL
                    )
                    if order:
                        print(
                            f"Alpaca SELL order submitted for {quantity} of {symbol}. Order ID: {order.id}"
                        )
                        # If position is fully closed, remove exit plan
                        if float(current_alpaca_position.qty) == quantity:
                            self.exit_plans.pop(symbol, None)
                            self.exit_plan_store.save(self.exit_plans)
                    else:
                        print(f"Failed to submit SELL order for {symbol}.")
                else:
                    print(
                        f"Warning: Not enough holdings on Alpaca to sell {quantity} of {symbol}. Current: {current_alpaca_position.qty}. Skipping trade."
                    )
            else:
                print(
                    f"Warning: No open position on Alpaca for {symbol} to sell. Skipping trade."
                )

        # Record trade in history (assuming it was successful on Alpaca)
        trade = Trade(symbol=symbol, action=action, quantity=quantity, price=price)
        self.trade_history.append(trade)

    async def get_status(self) -> PortfolioStatus:
        """
        Calculates the current status of the portfolio by fetching data from Alpaca.
        """
        alpaca_account = alpaca_client.trading_client.get_account()
        self.cash = float(alpaca_account.cash)

        alpaca_positions = alpaca_client.get_positions()

        current_prices = get_current_prices(
            [p.symbol for p in alpaca_positions]
        )  # Get prices for current positions

        positions_value = 0.0
        live_positions_details = []
        current_positions_dict: Dict[str, Position] = {}

        for alpaca_pos in alpaca_positions:
            symbol = alpaca_pos.symbol
            quantity = float(alpaca_pos.qty)
            entry_price = float(alpaca_pos.avg_entry_price)
            current_price = current_prices.get(
                symbol, entry_price
            )  # Fallback to entry price if current not found

            positions_value += quantity * current_price
            unrealized_pnl = float(alpaca_pos.unrealized_pl)

            # Retrieve stored exit plan
            exit_plan = self.exit_plans.get(symbol)

            pos_details = PositionDetails(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                exit_plan=exit_plan,
                # Mocked fields or derived from Alpaca data
                liquidation_price=0,  # Alpaca doesn't provide this directly for stocks
                leverage=1,  # Assuming no leverage for stocks
                confidence=0,  # Not from Alpaca
                risk_usd=0,  # Not from Alpaca
                sl_oid=0,  # Not from Alpaca
                tp_oid=0,  # Not from Alpaca
                wait_for_fill=False,  # Not from Alpaca
                entry_oid=0,  # Not from Alpaca
                notional_usd=float(alpaca_pos.market_value),
            )
            live_positions_details.append(pos_details)
            current_positions_dict[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                average_price=entry_price,
                exit_plan=exit_plan,
            )

        total_value = self.cash + positions_value
        pnl = total_value - self.initial_cash

        self.pnl_history.append(pnl)
        returns = (
            np.diff(self.pnl_history) / self.initial_cash
            if self.initial_cash > 0
            else np.array([0])
        )
        sharpe_ratio = (
            np.mean(returns) / np.std(returns) * np.sqrt(252)
            if np.std(returns) != 0
            else 0.0
        )

        total_return_percent = (
            (pnl / self.initial_cash) * 100 if self.initial_cash > 0 else 0.0
        )

        return PortfolioStatus(
            cash=self.cash,
            positions=current_positions_dict,  # Use positions fetched from Alpaca
            live_positions_details=live_positions_details,
            total_value=round(total_value, 2),
            pnl=round(pnl, 2),
            total_return_percent=round(total_return_percent, 2),
            sharpe_ratio=round(sharpe_ratio, 3),
        )
