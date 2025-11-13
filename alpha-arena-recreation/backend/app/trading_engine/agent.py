from app.llm.base import BaseLLMProvider
from app.trading_engine.portfolio import Portfolio
from app.models import (
    AgentState,
    LLMTradeDecision,
    LLMTradeDecisionList,
    PositionDetails,
    ExitPlan,
)
from app.data.market_data import get_detailed_market_data, get_current_prices
from app.config import settings
import pandas as pd
import json
import time


class Agent:
    def __init__(
        self,
        agent_id: str,
        name: str,
        llm_provider: BaseLLMProvider,
        initial_cash: float = 10000.0,
    ):
        self.agent_id = agent_id
        self.name = name
        self.llm_provider = llm_provider
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.start_time = time.time()

    async def _generate_prompt(self) -> str:
        """
        Generates the prompt to be sent to the LLM, matching the structure in execution_flow.md.
        """
        portfolio_status = await self.portfolio.get_status()
        detailed_market_data = get_detailed_market_data(settings.TRADE_SYMBOLS)

        elapsed_minutes = int((time.time() - self.start_time) / 60)

        prompt = f"It has been {elapsed_minutes} minute since you started trading.\n\n"
        prompt += "Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.\n\n"
        prompt += (
            "**ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST**\n\n"
        )
        prompt += "**Timeframes note:** Unless stated otherwise in a section title, the series provided below are sampled at **daily intervals**. If a symbol uses a different interval, it is explicitly stated in that symbol’s section.\n\n"
        prompt += "---\n\n"
        prompt += "### CURRENT MARKET STATE FOR ALL SYMBOLS\n\n"

        for symbol, data in detailed_market_data.items():
            prompt += f"### ALL {symbol} DATA\n\n"
            prompt += f"current_price = {data['current']['current_price']}, current_ema20 = {data['current']['current_ema20']}, current_macd = {data['current']['current_macd']}, current_rsi (7 period) = {data['current']['current_rsi7']}\n\n"
            prompt += "**Daily series (oldest → latest):**\n\n"
            prompt += f"Mid prices: {data['intraday_series']['mid_prices']}\n\n"
            prompt += f"EMA indicators (20‑period): {data['intraday_series']['ema_indicators']}\n\n"
            prompt += (
                f"MACD indicators: {data['intraday_series']['macd_indicators']}\n\n"
            )
            prompt += f"RSI indicators (7‑Period): {data['intraday_series']['rsi7_indicators']}\n\n"
            prompt += f"RSI indicators (14‑Period): {data['intraday_series']['rsi14_indicators']}\n\n"
            prompt += "**Longer‑term context (weekly timeframe):**\n\n"
            prompt += f"20‑Period EMA: {data['longer_term_context']['ema20']} vs. 50‑Period EMA: {data['longer_term_context']['ema50']}\n\n"
            prompt += f"3‑Period ATR: {data['longer_term_context']['atr3']} vs. 14‑Period ATR: {data['longer_term_context']['atr14']}\n\n"
            prompt += f"Current Volume: {data['longer_term_context']['current_volume']} vs. Average Volume: {data['longer_term_context']['average_volume']}\n\n"
            prompt += (
                f"MACD indicators: {data['longer_term_context']['macd_indicators']}\n\n"
            )
            prompt += f"RSI indicators (14‑Period): {data['longer_term_context']['rsi14_indicators']}\n\n"
            prompt += "---\n\n"

        prompt += "### HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE\n\n"
        prompt += f"Current Total Return (percent): {portfolio_status.total_return_percent}%\n\n"
        prompt += f"Available Cash: {portfolio_status.cash}\n\n"
        prompt += f"**Current Account Value:** {portfolio_status.total_value}\n\n"
        prompt += "Current live positions & performance:\n"
        allowed_symbols = set(settings.TRADE_SYMBOLS)
        if not portfolio_status.live_positions_details:
            prompt += "{}\\n\n"
        else:
            wrote_position = False
            for pos in portfolio_status.live_positions_details:
                if pos.symbol not in allowed_symbols:
                    continue
                prompt += json.dumps(pos.dict(), indent=4) + "\n\n"
                wrote_position = True
            if not wrote_position:
                prompt += "{}\\n\n"
        prompt += f"Sharpe Ratio: {portfolio_status.sharpe_ratio}\n\n"
        prompt += "### EXIT PLAN STATUS & INSTRUCTIONS\n"
        prompt += (
            "For every currently held symbol, inspect its `exit_plan` (profit_target / stop_loss / invalidation_condition) "
            "versus the latest market data above. If current conditions satisfy the exit plan—for example price >= profit_target "
            "or price <= stop_loss—issue the appropriate `close` decision in this cycle. Only keep holding if neither boundary is met.\n\n"
        )
        prompt += (
            "You may ONLY issue decisions for the following symbols: "
            f"{', '.join(settings.TRADE_SYMBOLS)}. Ignore any other holdings you might see. "
        )
        prompt += "Based on the above information, provide a JSON object with a 'decisions' key, containing a list of trade decisions for each symbol you want to trade, hold, or close. "
        prompt += (
            "Each decision in the list should conform to the LLMTradeDecision model, including 'symbol', 'signal' (one of 'buy_to_enter', 'sell_to_enter', 'hold', 'close'), "
            "'confidence', 'justification', and relevant optional fields like 'stop_loss', 'leverage', 'risk_usd', 'profit_target', 'quantity', and 'invalidation_condition'. "
            "The 'confidence' field must reflect your best-effort probability (0.0–1.0) that the action is correct for the given market context—do not default to 0.0 unless truly uncertain.\n"
        )
        prompt += "For 'close' signals, you must specify the symbol of the position to close.\n"
        prompt += (
            "For 'buy_to_enter' or 'sell_to_enter', you must specify both a quantity and a clear 'invalidation_condition' describing when the exit plan should trigger (e.g., price crosses a threshold, indicator flips, etc.).\n"
        )
        prompt += (
            "You can also choose to 'hold' a position or do nothing for a symbol.\n"
        )
        prompt += (
            "OUTPUT FORMAT REQUIREMENTS: Respond with raw JSON only (no markdown fences, no prose, no error strings). "
            "Use double quotes for all keys/strings, and if you have no trades simply respond with {\"decisions\": []}. "
            "Never include messages like 'Invalid JSON' or explanations outside the JSON object.\n"
        )

        return prompt

    async def decide_and_trade(self):
        """
        Checks for exit conditions, then gets decisions from the LLM and executes trades.
        """
        # 1. Exit plans now evaluated by the LLM prompt; skip redundant local checks.
        # await self._check_exit_conditions()

        # 2. Generate prompt and get decisions from LLM
        prompt = await self._generate_prompt()

        decision_list = await self.llm_provider.get_trade_decision(prompt)

        if not decision_list or not decision_list.decisions:
            print(f"Warning: LLM provided no decisions. Skipping trade cycle.")
            return

        current_prices = get_current_prices(settings.TRADE_SYMBOLS)

        for decision in decision_list.decisions:
            trade_symbol = decision.symbol
            price = current_prices.get(trade_symbol)

            if price is None:
                print(
                    f"Warning: Could not get current price for {decision.symbol}. Skipping trade for this symbol."
                )
                continue

            if decision.signal in ["buy_to_enter", "sell_to_enter"]:
                if decision.quantity is None or decision.quantity <= 0:
                    print(
                        f"Warning: LLM decided to {decision.signal} for {decision.symbol} but quantity was not specified. Skipping trade."
                    )
                    continue

                # Create ExitPlan from decision
                exit_plan = None
                if (
                    decision.stop_loss is not None
                    and decision.profit_target is not None
                ):
                    exit_plan = ExitPlan(
                        profit_target=decision.profit_target,
                        stop_loss=decision.stop_loss,
                        invalidation_condition=decision.invalidation_condition or "",
                    )

                await self.portfolio.execute_trade(
                    symbol=trade_symbol,
                    action="BUY" if decision.signal == "buy_to_enter" else "SELL",
                    quantity=decision.quantity,
                    price=price,
                    exit_plan=exit_plan,
                )
                print(
                    f"Agent {self.name} executed: {decision.signal} {decision.quantity:.6f} {decision.symbol} @ ${price:,.2f}"
                )
                print(f"  Justification: {decision.justification}")

            elif decision.signal == "close":
                # Fetch current positions from portfolio (which now gets them from Alpaca)
                portfolio_status = await self.portfolio.get_status()
                position_to_close = portfolio_status.positions.get(trade_symbol)
                if position_to_close:
                    close_action = "SELL" if position_to_close.quantity > 0 else "BUY"

                    await self.portfolio.execute_trade(
                        symbol=trade_symbol,
                        action=close_action,
                        quantity=abs(position_to_close.quantity),
                        price=price,
                    )
                    print(
                        f"Agent {self.name} decided to CLOSE position for {decision.symbol} at price ${price:,.2f}."
                    )
                    print(f"  Justification: {decision.justification}")
                else:
                    print(
                        f"Warning: Agent {self.name} decided to CLOSE position for {decision.symbol}, but no open position was found."
                    )

            elif decision.signal == "hold":
                print(
                    f"Agent {self.name} decided to HOLD position for {decision.symbol}."
                )

            else:
                print(
                    f"Warning: Unknown signal '{decision.signal}' for {decision.symbol}. Skipping."
                )

    async def _check_exit_conditions(self):
        """
        Checks all open positions for stop-loss or take-profit triggers.
        """
        print("--- Checking exit conditions for open positions ---")

        portfolio_status = await self.portfolio.get_status()
        positions_to_check = (
            portfolio_status.positions.values()
        )  # Get actual Position objects

        if not positions_to_check:
            print("No open positions to check.")
            return

        current_prices = get_current_prices([p.symbol for p in positions_to_check])

        for position in positions_to_check:
            symbol = position.symbol
            if not position.exit_plan:
                continue

            price = current_prices.get(symbol)
            if not price:
                continue

            exit_plan = position.exit_plan

            # Check for long position exits
            if position.quantity > 0:
                if price >= exit_plan.profit_target:
                    print(
                        f"Take-profit triggered for {symbol} at ${price:,.2f} (Target: ${exit_plan.profit_target:,.2f})"
                    )
                    await self.portfolio.execute_trade(
                        symbol, "SELL", abs(position.quantity), price
                    )
                elif price <= exit_plan.stop_loss:
                    print(
                        f"Stop-loss triggered for {symbol} at ${price:,.2f} (Stop: ${exit_plan.stop_loss:,.2f})"
                    )
                    await self.portfolio.execute_trade(
                        symbol, "SELL", abs(position.quantity), price
                    )

            # Add logic for short positions if they are ever implemented
            # elif position.quantity < 0:
            #     ...

    async def get_state(self) -> AgentState:
        """
        Returns the current state of the agent.
        """
        return AgentState(
            agent_id=self.agent_id,
            name=self.name,
            llm_provider=str(self.llm_provider),
            portfolio=await self.portfolio.get_status(),
            trade_history=self.portfolio.trade_history,
        )
