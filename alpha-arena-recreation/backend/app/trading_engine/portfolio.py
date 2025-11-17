from types import SimpleNamespace
from typing import Dict, Optional

import numpy as np
from alpaca.trading.enums import OrderSide

from app.alpaca.client import alpaca_client
from app.data.market_data import get_current_prices
from app.models import ExitPlan, PortfolioStatus, Position, PositionDetails, Trade
from app.storage.exit_plan_store import ExitPlanStore
from app.config import settings


class Portfolio:
    def __init__(
        self,
        initial_cash: float | None = None,
        exit_plan_store: Optional[ExitPlanStore] = None,
    ):
        cash_seed = settings.INITIAL_CASH if initial_cash is None else initial_cash
        self.initial_cash = cash_seed
        self.cash = cash_seed  # This will eventually come from Alpaca account
        self.trade_history: list[Trade] = []
        self.pnl_history = [0.0]  # To calculate Sharpe Ratio
        self.exit_plan_store = exit_plan_store or ExitPlanStore()
        self.exit_plans: Dict[str, ExitPlan] = self.exit_plan_store.load()
        self._local_positions: Dict[str, Position] = {}

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
                self._update_local_position(
                    symbol=symbol,
                    action="BUY",
                    quantity=quantity,
                    price=price,
                    exit_plan=exit_plan,
                )
            else:
                print(f"Failed to submit BUY order for {symbol}.")

        elif action == "SELL":
            # Check if we have an open position to sell
            alpaca_positions = alpaca_client.get_positions()
            current_alpaca_position = next(
                (p for p in alpaca_positions if p.symbol == alpaca_symbol), None
            )
            local_position = self._local_positions.get(symbol)

            can_sell_remote = (
                current_alpaca_position and float(current_alpaca_position.qty) >= quantity
            )
            can_sell_local = local_position and local_position.quantity >= quantity

            if can_sell_remote or can_sell_local:
                order = alpaca_client.submit_order(
                    symbol=alpaca_symbol, qty=quantity, side=OrderSide.SELL
                )
                if order:
                    print(
                        f"Alpaca SELL order submitted for {quantity} of {symbol}. Order ID: {order.id}"
                    )
                    if exit_plan:
                        self.exit_plans[symbol] = exit_plan
                        self.exit_plan_store.save(self.exit_plans)
                    self._update_local_position(
                        symbol=symbol,
                        action="SELL",
                        quantity=quantity,
                        price=price,
                    )
                else:
                    print(f"Failed to submit SELL order for {symbol}.")
            else:
                print(
                    f"Warning: No open position found for {symbol} to sell. Skipping trade."
                )

        # Record trade in history (assuming it was successful on Alpaca)
        trade = Trade(symbol=symbol, action=action, quantity=quantity, price=price)
        self.trade_history.append(trade)

    async def get_status(self) -> PortfolioStatus:
        """
        Calculates the current status of the portfolio by fetching data from Alpaca.
        """
        try:
            alpaca_account = alpaca_client.trading_client.get_account()
            self.cash = float(alpaca_account.cash)
        except Exception as exc:
            print(
                f"Warning: Unable to fetch Alpaca account balances ({exc}). Using last known cash value."
            )

        alpaca_positions = alpaca_client.get_positions()

        if not alpaca_positions and self._local_positions:
            alpaca_positions = [
                SimpleNamespace(
                    symbol=symbol,
                    qty=position.quantity,
                    avg_entry_price=position.average_price,
                    unrealized_pl=0.0,
                    market_value=position.quantity * position.average_price,
                )
                for symbol, position in self._local_positions.items()
            ]

        position_symbols = [p.symbol for p in alpaca_positions]
        current_prices = (
            get_current_prices(position_symbols) if position_symbols else {}
        )

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

    def _update_local_position(
        self,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        exit_plan: Optional[ExitPlan] = None,
    ) -> None:
        """
        Mirror fills locally so offline development can function without Alpaca.
        """
        position = self._local_positions.get(symbol)

        if action == "BUY":
            if position:
                total_qty = position.quantity + quantity
                avg_price = (
                    (position.average_price * position.quantity) + (price * quantity)
                ) / total_qty
                position.quantity = total_qty
                position.average_price = avg_price
                if exit_plan:
                    position.exit_plan = exit_plan
                self._local_positions[symbol] = position
            else:
                self._local_positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=price,
                    exit_plan=exit_plan,
                )
        elif action == "SELL" and position:
            remaining = position.quantity - quantity
            if remaining <= 0:
                self._local_positions.pop(symbol, None)
                if symbol in self.exit_plans:
                    self.exit_plans.pop(symbol, None)
                    self.exit_plan_store.save(self.exit_plans)
            else:
                position.quantity = remaining
                self._local_positions[symbol] = position
