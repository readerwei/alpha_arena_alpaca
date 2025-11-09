import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
from datetime import datetime, timedelta
from app.models import PositionDetails, ExitPlan

def _symbol_to_ticker(symbol: str) -> str:
    """Converts a symbol to a yfinance ticker."""
    return symbol

def get_detailed_market_data(symbols: list[str]) -> dict:
    """
    Returns a dictionary of detailed market data for the given symbols using Yahoo Finance.
    """
    detailed_data = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365) # 1 year of data for calculations

    for symbol in symbols:
        ticker_str = _symbol_to_ticker(symbol)
        try:
            # Download daily data
            data = yf.download(ticker_str, start=start_date, end=end_date, interval="1d", auto_adjust=False, group_by='ticker')
            if data.empty:
                print(f"Warning: No data found for symbol {ticker_str}")
                continue

            # Flatten MultiIndex columns if they exist
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(0)

            # Ensure we have enough data for indicators
            if len(data) < 50: # Need at least 50 periods for EMA 50
                print(f"Warning: Not enough data for {ticker_str} to calculate all indicators.")
                continue

            # Calculate indicators using pandas-ta
            data.ta.ema(length=20, append=True)
            data.ta.ema(length=50, append=True)
            data.ta.macd(append=True)
            data.ta.rsi(length=7, append=True)
            data.ta.rsi(length=14, append=True)
            data.ta.atr(length=3, append=True)
            data.ta.atr(length=14, append=True)
            
            # Get the latest data point
            latest = data.iloc[-1]

            # Intraday series (using last 10 days as a substitute for 3-min intervals)
            intraday_series_df = data.tail(10)

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
                    "ema20": latest["EMA_20"],
                    "ema50": latest["EMA_50"],
                    "atr3": latest["ATRr_3"],
                    "atr14": latest["ATRr_14"],
                    "current_volume": latest["Volume"],
                    "average_volume": data["Volume"].mean(),
                    "macd_indicators": data.tail(10)["MACD_12_26_9"].round(3).tolist(),
                    "rsi14_indicators": data.tail(10)["RSI_14"].round(3).tolist()
                }
            }
        except Exception as e:
            print(f"Error fetching or processing data for {ticker_str}: {e}")
            continue
            
    return detailed_data

def get_current_prices(symbols: list[str]) -> dict[str, float]:
    """
    Returns a dictionary of current prices for the given symbols using Yahoo Finance.
    """
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
            # Fallback to a placeholder or last known good price if needed
            prices[symbol] = 0.0 
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