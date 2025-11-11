import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Literal

load_dotenv()

class Settings:
    BASE_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT: Path = BASE_DIR.parent

    # Alpaca API credentials
    ALPACA_API_KEY_ID: str = os.getenv("ALPACA_API_KEY_ID")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY")
    
    
    # List of cryptocurrencies to trade
    TRADE_SYMBOLS: list[str] = ["AAPL", "NVDA", "AMD"]
    
    # Trading loop interval in seconds
    LOOP_INTERVAL_SECONDS: int = 300  # 5 minutes

    # LLM Provider Settings
    LLM_PROVIDER: Literal["mock", "ollama"] = os.getenv("LLM_PROVIDER", "mock") # 'mock' or 'ollama'
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    EXIT_PLAN_CSV_PATH: str = os.getenv(
        "EXIT_PLAN_CSV_PATH", str(PROJECT_ROOT / "exit_plans.csv")
    )


settings = Settings()
