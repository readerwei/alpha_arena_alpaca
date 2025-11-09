from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from app.config import settings

class AlpacaClient:
    def __init__(self):
        if not settings.ALPACA_API_KEY_ID or not settings.ALPACA_SECRET_KEY:
            raise ValueError("Alpaca API keys are not configured.")
        
        self.trading_client = TradingClient(
            settings.ALPACA_API_KEY_ID,
            settings.ALPACA_SECRET_KEY,
            paper=True  # Use paper trading environment
        )

    def get_positions(self):
        """
        Returns all open positions from Alpaca.
        """
        try:
            return self.trading_client.get_all_positions()
        except Exception as e:
            print(f"Error fetching Alpaca positions: {e}")
            return []

    def submit_order(self, symbol: str, qty: float, side: OrderSide, time_in_force: TimeInForce = TimeInForce.DAY):
        """
        Submits a market order to Alpaca.
        """
        market_order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=time_in_force
        )
        try:
            return self.trading_client.submit_order(order_data=market_order_data)
        except Exception as e:
            print(f"Error submitting order to Alpaca for {symbol}: {e}")
            return None

    def close_position(self, symbol: str):
        """
        Closes the entire position for the given symbol.
        """
        try:
            return self.trading_client.close_position(symbol)
        except Exception as e:
            print(f"Error closing position on Alpaca for {symbol}: {e}")
            return None

# Create a single instance of the client to be used throughout the app
alpaca_client = AlpacaClient()
