import os
import sys
import types
from pathlib import Path

# Disable numba JIT caching during tests to avoid filesystem locator issues in pandas_ta.
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

# Provide a lightweight Alpaca stub if the dependency is missing so imports succeed.
if "alpaca" not in sys.modules:
    alpaca_module = types.ModuleType("alpaca")
    trading_module = types.ModuleType("alpaca.trading")
    client_module = types.ModuleType("alpaca.trading.client")
    requests_module = types.ModuleType("alpaca.trading.requests")
    enums_module = types.ModuleType("alpaca.trading.enums")

    class TradingClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def get_all_positions(self):
            return []

        def submit_order(self, *args, **kwargs):
            return types.SimpleNamespace(id="stub-order")

        def close_position(self, *args, **kwargs):
            return None

        def get_account(self):
            return types.SimpleNamespace(cash="0")

    class MarketOrderRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class ClosePositionRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class OrderSide:
        BUY = "buy"
        SELL = "sell"

    class TimeInForce:
        DAY = "day"

    client_module.TradingClient = TradingClient
    requests_module.MarketOrderRequest = MarketOrderRequest
    requests_module.ClosePositionRequest = ClosePositionRequest
    enums_module.OrderSide = OrderSide
    enums_module.TimeInForce = TimeInForce

    sys.modules["alpaca"] = alpaca_module
    sys.modules["alpaca.trading"] = trading_module
    sys.modules["alpaca.trading.client"] = client_module
    sys.modules["alpaca.trading.requests"] = requests_module
    sys.modules["alpaca.trading.enums"] = enums_module

    alpaca_module.trading = trading_module

# Ensure the backend root is importable so `app.*` modules resolve under pytest.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
