import base64
import io
import os
from datetime import datetime, timedelta

import matplotlib
import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from matplotlib import dates as mdates
from matplotlib.patches import Rectangle

# Avoid numba caching errors in sandboxed environments by disabling JIT at startup.
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.models import PositionDetails, ExitPlan
from app.config import settings


def _safe_float(value) -> float:
    """Convert numeric-like values (including numpy scalars) to built-in floats."""
    if value is None:
        return float("nan")
    try:
        if pd.isna(value):
            return float("nan")
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")

def _symbol_to_ticker(symbol: str) -> str:
    """Converts a symbol to a yfinance ticker."""
    return symbol

def get_detailed_market_data(symbols: list[str]) -> dict:
    """
    Returns a dictionary of detailed market data for the given symbols using Yahoo Finance.
    """
    if settings.USE_MOCK_MARKET_DATA:
        return {symbol: _generate_mock_market_data(symbol) for symbol in symbols}

    detailed_data = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365) # 1 year of data for calculations

    for symbol in symbols:
        ticker_str = _symbol_to_ticker(symbol)
        try:
            # Download daily data
            data = yf.download(ticker_str, start=start_date, end=end_date, interval="1d", auto_adjust=False, group_by='ticker')
            if data.empty:
                print(f"Warning: No data found for symbol {ticker_str}. Using mock data.")
                detailed_data[symbol] = _generate_mock_market_data(symbol)
                continue

            # Flatten MultiIndex columns if they exist
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(0)

            # Ensure we have enough data for indicators
            if len(data) < 50: # Need at least 50 periods for EMA 50
                print(f"Warning: Not enough data for {ticker_str} to calculate all indicators. Using mock data.")
                detailed_data[symbol] = _generate_mock_market_data(symbol)
                continue

            # Ensure datetime index for resampling operations
            data.index = pd.DatetimeIndex(data.index)

            # Calculate indicators using pandas-ta on daily data
            data.ta.ema(length=20, append=True)
            data.ta.ema(length=50, append=True)
            data.ta.macd(append=True)
            data.ta.rsi(length=7, append=True)
            data.ta.rsi(length=14, append=True)
            data.ta.atr(length=3, append=True)
            data.ta.atr(length=14, append=True)

            # Resample to weekly data for longer-term context
            weekly_ohlcv = (
                data[["Open", "High", "Low", "Close", "Volume"]]
                .resample("W")
                .agg(
                    {
                        "Open": "first",
                        "High": "max",
                        "Low": "min",
                        "Close": "last",
                        "Volume": "sum",
                    }
                )
            ).dropna()

            if len(weekly_ohlcv) < 10:
                print(
                    f"Warning: Limited weekly data for {ticker_str}. Long-term indicators may be less reliable."
                )

            weekly_data = weekly_ohlcv.copy()
            weekly_close = weekly_data["Close"]
            weekly_high = weekly_data["High"]
            weekly_low = weekly_data["Low"]

            weekly_data["EMA_20"] = ta.ema(weekly_close, length=20)
            weekly_data["EMA_50"] = ta.ema(weekly_close, length=50)

            weekly_macd = ta.macd(weekly_close)
            if weekly_macd is not None and "MACD_12_26_9" in weekly_macd.columns:
                weekly_data["MACD_12_26_9"] = weekly_macd["MACD_12_26_9"]
            else:
                weekly_data["MACD_12_26_9"] = float("nan")

            weekly_data["RSI_14"] = ta.rsi(weekly_close, length=14)
            weekly_data["ATRr_3"] = ta.atr(
                high=weekly_high, low=weekly_low, close=weekly_close, length=3
            )
            weekly_data["ATRr_14"] = ta.atr(
                high=weekly_high, low=weekly_low, close=weekly_close, length=14
            )
            
            # Get the latest data point
            latest = data.iloc[-1]
            latest_weekly = weekly_data.iloc[-1]

            # Intraday series (using last 10 days as a substitute for 3-min intervals)
            intraday_series_df = data.tail(10)

            candlestick_visual = _build_candlestick_visual(
                data[["Open", "High", "Low", "Close"]], symbol
            )

            detailed_data[symbol] = {
                "current": {
                    "current_price": latest["Close"],
                    "current_ema20": latest["EMA_20"],
                    "current_macd": latest["MACD_12_26_9"],
                    "current_rsi7": latest["RSI_7"],
                    # Mocking these as yfinance doesn't provide them directly
                    "open_interest_latest": round(np.random.uniform(20000, 30000), 2),
                    "open_interest_average": round(np.random.uniform(20000, 30000), 2),
                    "funding_rate": float(f"{np.random.uniform(1e-6, 1e-5):.8f}")
                },
                "intraday_series": {
                    "mid_prices": intraday_series_df["Close"].round(3).tolist(),
                    "ema_indicators": intraday_series_df["EMA_20"].round(3).tolist(),
                    "macd_indicators": intraday_series_df["MACD_12_26_9"].round(3).tolist(),
                    "rsi7_indicators": intraday_series_df["RSI_7"].round(3).tolist(),
                    "rsi14_indicators": intraday_series_df["RSI_14"].round(3).tolist()
                },
                "longer_term_context": {
                    "ema20": _safe_float(latest_weekly["EMA_20"]),
                    "ema50": _safe_float(latest_weekly["EMA_50"]),
                    "atr3": _safe_float(latest_weekly["ATRr_3"]),
                    "atr14": _safe_float(latest_weekly["ATRr_14"]),
                    "current_volume": _safe_float(latest_weekly["Volume"]),
                    "average_volume": _safe_float(weekly_data["Volume"].mean()),
                    "macd_indicators": weekly_data.tail(10)["MACD_12_26_9"].round(3).tolist(),
                    "rsi14_indicators": weekly_data.tail(10)["RSI_14"].round(3).tolist()
                },
                "visuals": {
                    "candlestick_chart": candlestick_visual,
                },
            }
        except Exception as e:
            print(f"Error fetching or processing data for {ticker_str}: {e}. Using mock data.")
            detailed_data[symbol] = _generate_mock_market_data(symbol)
            continue
            
    return detailed_data

def get_current_prices(symbols: list[str]) -> dict[str, float]:
    """
    Returns a dictionary of current prices for the given symbols using Yahoo Finance.
    """
    if settings.USE_MOCK_MARKET_DATA:
        return {symbol: _generate_mock_price(symbol) for symbol in symbols}

    prices = {}
    for symbol in symbols:
        ticker_str = _symbol_to_ticker(symbol)
        try:
            # Get the latest price info
            ticker = yf.Ticker(ticker_str)
            # 'regularMarketPrice' is a good option for near real-time data
            # Fallback to previous close if not available
            price = ticker.info.get('regularMarketPrice', ticker.history(period="1d")["Close"].iloc[-1])
            prices[symbol] = round(price, 2)
        except Exception as e:
            print(f"Could not fetch current price for {ticker_str}: {e}")
            # Fallback to mock price if network/data unavailable
            prices[symbol] = _generate_mock_price(symbol)
    return prices

def get_mock_position_details(symbols: list[str]) -> list[PositionDetails]:
    """
    Generates mock detailed position information for a few symbols.
    """
    mock_positions = []
    if "NVDA" in symbols: # Example for NVDA
        entry_price = 180.0 
        current_prices = get_current_prices(["NVDA"])
        current_price = current_prices.get("NVDA", entry_price * 1.05) # Assume a slight profit if not found
        
        liquidation_price = round(entry_price * 0.9, 2) # Example liquidation price
        quantity = 10.0 # Example quantity
        unrealized_pnl = round((current_price - entry_price) * quantity, 2)
        mock_positions.append(PositionDetails(
            symbol='NVDA',
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            liquidation_price=liquidation_price,
            unrealized_pnl=unrealized_pnl,
            leverage=1, # Assuming no leverage for stocks
            exit_plan=ExitPlan(profit_target=current_price * 1.1, stop_loss=current_price * 0.9, invalidation_condition='Market sentiment shifts bearish'),
            confidence=0.75,
            risk_usd=100.0, # Example risk
            sl_oid=-1,
            tp_oid=-1,
            wait_for_fill=False,
            entry_oid=12345,
            notional_usd=round(quantity * current_price, 2)
        ))
    
    return mock_positions


def _build_candlestick_visual(
    ohlc: pd.DataFrame, symbol: str, lookback: int = 60
) -> dict:
    """
    Render a recent OHLC slice to a base64-encoded PNG candlestick chart so LLMs
    can inspect visual price action.
    """
    required = {"Open", "High", "Low", "Close"}
    if ohlc is None or not required.issubset(ohlc.columns):
        return {}

    try:
        trimmed = (
            ohlc.tail(lookback)
            .copy()
            .dropna(subset=required, how="any")
        )
        if trimmed.empty:
            return {}
        trimmed.index = pd.DatetimeIndex(trimmed.index)

        fig, ax = plt.subplots(figsize=(6, 3))
        fig.suptitle(f"{symbol} – Last {len(trimmed)} Daily Candles", fontsize=10)
        ax.set_ylabel("Price")
        ax.grid(alpha=0.15)

        date_nums = mdates.date2num(trimmed.index.to_pydatetime())
        body_width = 0.6
        min_body_height = max(trimmed["Close"].mean() * 0.0005, 0.01)

        for x, (_, row) in zip(date_nums, trimmed.iterrows()):
            open_price = float(row["Open"])
            close_price = float(row["Close"])
            high_price = float(row["High"])
            low_price = float(row["Low"])
            color = "#16a34a" if close_price >= open_price else "#dc2626"
            ax.plot([x, x], [low_price, high_price], color=color, linewidth=1)
            body_height = abs(close_price - open_price)
            body_height = body_height if body_height > 0 else min_body_height
            lower_edge = min(open_price, close_price)
            rect = Rectangle(
                (x - body_width / 2, lower_edge),
                body_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.4,
            )
            ax.add_patch(rect)

        ax.xaxis_date()
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        fig.autofmt_xdate()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        image_bytes = buf.getvalue()
        buf.close()

        saved_path = None
        if settings.SAVE_CANDLESTICK_CHARTS:
            try:
                charts_dir = settings.CANDLESTICK_CHARTS_DIR
                charts_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = charts_dir / f"{symbol}_{timestamp}.png"
                with open(file_path, "wb") as file_obj:
                    file_obj.write(image_bytes)
                saved_path = str(file_path)
            except Exception as file_exc:
                print(
                    f"Warning: Failed to persist candlestick chart for {symbol}: {file_exc}"
                )

        plt.close(fig)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {
            "data_uri": f"data:image/png;base64,{encoded}",
            "lookback_bars": len(trimmed),
            "start": trimmed.index[0].isoformat(),
            "end": trimmed.index[-1].isoformat(),
            "interval": "1d",
            "description": "Base64-encoded candlestick chart for visual pattern review.",
            "saved_path": saved_path,
        }
    except Exception as exc:
        print(f"Warning: Failed to render candlestick chart for {symbol}: {exc}")
        return {}


def _build_mock_ohlc(
    rng: np.random.Generator, periods: int = 60
) -> pd.DataFrame:
    """Create a deterministic but realistic OHLCV frame for mock environments."""
    end_date = datetime.now()
    index = pd.date_range(end=end_date, periods=periods, freq="D")
    base_price = rng.uniform(50, 300)
    close_changes = rng.normal(0, base_price * 0.01, size=periods)
    close = base_price + np.cumsum(close_changes)
    close = np.clip(close, 5, None)
    open_noise = rng.normal(0, base_price * 0.005, size=periods)
    open_price = np.clip(close + open_noise, 5, None)
    high_spread = rng.uniform(base_price * 0.002, base_price * 0.02, size=periods)
    low_spread = rng.uniform(base_price * 0.002, base_price * 0.02, size=periods)
    high = np.maximum(open_price, close) + high_spread
    low = np.minimum(open_price, close) - low_spread
    volume = rng.uniform(10_000, 100_000, size=periods)

    data = pd.DataFrame(
        {
            "Open": open_price,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )
    return data


def _generate_mock_market_data(symbol: str) -> dict:
    rng = _mock_rng(symbol)
    ohlc = _build_mock_ohlc(rng)
    intraday_df = ohlc.tail(10)
    mid_prices = np.round(intraday_df["Close"], 3).tolist()
    ema_series = np.round(
        pd.Series(mid_prices).ewm(span=5, adjust=False).mean(), 3
    ).tolist()

    ema20 = float(
        ohlc["Close"].ewm(span=20, adjust=False).mean().iloc[-1]
    )
    ema50 = float(
        ohlc["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
    )

    longer_macd = np.round(rng.normal(0, 5, size=10), 3).tolist()
    longer_rsi = np.round(rng.uniform(35, 65, size=10), 3).tolist()

    candlestick_visual = _build_candlestick_visual(ohlc, symbol)

    mock_data = {
        "current": {
            "current_price": round(mid_prices[-1], 2),
            "current_ema20": round(ema20, 2),
            "current_macd": round(rng.normal(0, 5), 3),
            "current_rsi7": round(rng.uniform(40, 70), 3),
            "open_interest_latest": round(rng.uniform(20000, 30000), 2),
            "open_interest_average": round(rng.uniform(20000, 30000), 2),
            "funding_rate": float(f"{rng.uniform(1e-6, 1e-5):.8f}"),
        },
        "intraday_series": {
            "mid_prices": mid_prices,
            "ema_indicators": ema_series,
            "macd_indicators": np.round(rng.normal(0, 5, size=10), 3).tolist(),
            "rsi7_indicators": np.round(rng.uniform(35, 70, size=10), 3).tolist(),
            "rsi14_indicators": np.round(rng.uniform(35, 70, size=10), 3).tolist(),
        },
        "longer_term_context": {
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "atr3": round(rng.uniform(1, 5), 3),
            "atr14": round(rng.uniform(5, 15), 3),
            "current_volume": round(float(ohlc["Volume"].iloc[-1]), 2),
            "average_volume": round(float(ohlc["Volume"].mean()), 2),
            "macd_indicators": longer_macd,
            "rsi14_indicators": longer_rsi,
        },
        "visuals": {
            "candlestick_chart": candlestick_visual,
        },
    }
    print(f"Using mock market data for {symbol}.")
    return mock_data


def _generate_mock_price(symbol: str) -> float:
    rng = _mock_rng(symbol)
    return round(rng.uniform(50, 300), 2)


def _mock_rng(symbol: str) -> np.random.Generator:
    seed = abs(hash(symbol)) % (2**32)
    return np.random.default_rng(seed)
