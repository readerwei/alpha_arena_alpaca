# Alpha Arena Recreation

This project is a simulation of LLM-powered autonomous trading agents, designed to recreate the core concepts of the "Alpha Arena" experiment—originally showcased at [nof1.ai](https://nof1.ai/alpha-arena)—while operating on US equities by default (AAPL, NVDA, AMD). It combines live Alpaca paper trading, yfinance market data, and optional Ollama-backed LLM agents.

## Project Overview

*   **Purpose**: To create a framework where multiple AI agents, powered by Large Language Models (LLMs), can autonomously trade in a simulated-yet-order-executing equities environment. The system is designed to be observable, allowing for the analysis of different agents' behaviors, prompts, exit-plan handling, and performance.

*   **Architecture**:
    *   **Backend**: A Python 3.10+ application built with **FastAPI**. It exposes REST endpoints (`/api/v1/agents`, `/engine/status`) and runs the asynchronous trading loop used by both the API and local debug scripts.
    *   **Frontend**: Placeholder React app (not yet implemented) slated to visualize agent performance and trace decision rationales.

*   **Core Logic**:
*   The backend runs a **Trading Engine** in a continuous loop.
*   In each cycle, the engine fetches either:
    *   **Live** quotes/indicator data via yfinance (when `USE_MOCK_MARKET_DATA=false`), or
    *   **Deterministic mock** data (when `USE_MOCK_MARKET_DATA=true`) so you can test offline.
*   It then prompts each trading agent for a decision. The prompt includes detailed market data (current, intraday series, longer-term context), filtered live positions, and exit-plan reminders. The LLM is expected to emit raw JSON conforming to `LLMTradeDecisionList`.
*   Supported LLM providers:
    *   **MockLLMProvider** – generates random trades for rapid iteration.
    *   **OllamaProvider** – calls a local/remote Ollama server and includes robust JSON sanitization/fallback.
*   Trades are executed through Alpaca. With `USE_MOCK_ALPACA=true`, fills are simulated locally; otherwise the paper-trading API is used. Exit plans persist to `exit_plans.csv` so restarts pick up trailing targets and stops.

## Building and Running

### Backend (FastAPI)

1.  **Navigate to the backend directory**:
    ```bash
    cd alpha-arena-recreation/backend
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**:
    Create a `.env` file in the backend directory (loaded by `app/config.py`). Minimum keys:
    ```
    LLM_PROVIDER=mock            # or ollama
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=qwen3:4b
    ALPACA_API_KEY_ID=your_paper_key
    ALPACA_SECRET_KEY=your_paper_secret
    USE_MOCK_ALPACA=true         # flip to false for live paper trading
    USE_MOCK_MARKET_DATA=true    # flip to false for yfinance data
    TRADE_SYMBOLS=AAPL,NVDA,AMD  # symbols the LLM is allowed to trade
    ```
    Adjust timeouts, exit-plan CSV paths, or symbol lists as needed. When hitting a real Alpaca account, ensure valid paper credentials exist before importing `app.alpaca.client`.

5.  **Run the development server**:
    The trading engine starts automatically when the server starts.
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The API documentation will be available at `http://localhost:8000/docs`.

### Frontend (React)

*   **TODO**: Add build and run instructions once the frontend has been implemented.

## Development Conventions & Key Components

### General
*   **Modular Structure**: The backend code is organized into distinct modules based on functionality:
    *   `app/api`: API endpoints and routing.
    *   `app/trading_engine`: Contains the core simulation logic, including the `TradingEngine`, `Agent`, and `Portfolio` classes.
    *   `app/llm`: Handles interaction with LLMs, with a `BaseLLMProvider` interface and concrete implementations for `MockLLMProvider` and `OllamaProvider`.
    *   `app/data`: Responsible for fetching market data (currently mocked with detailed structures).
    *   `app/models.py`: Defines Pydantic models for data structures like trades, positions, and agent states, including a detailed `LLMTradeDecision` model.

*   **Configuration**: Application settings are managed via a `config.py` file, which loads values from environment variables (a `.env` file is expected). This allows for easy switching between LLM providers and configuration of their parameters.

*   **Mock-first toggles**: `USE_MOCK_ALPACA` and `USE_MOCK_MARKET_DATA` short-circuit live dependencies so you can iterate in sandboxes.

*   **Asynchronous**: The application uses `asyncio` to run the trading loop in the background, concurrent with the API server.

### Code Style Guidelines

#### Imports
- Standard library imports first
- Third-party imports second
- Local imports last
- Use absolute imports for local modules

#### Formatting
- Use 4 spaces for indentation
- Line length: no strict limit, but keep readable
- Use f-strings for string formatting

#### Types
- Use type hints for all function parameters and return values
- Use `typing` module for complex types (List, Dict, Optional, etc.)
- Use Pydantic BaseModel for data structures

#### Naming Conventions
- Functions/variables: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- Private methods: _leading_underscore

#### Error Handling
- Use try/except blocks for expected errors
- Log errors with descriptive messages
- Don't suppress exceptions without good reason

#### Documentation
- Use docstrings for all public functions and classes
- Keep docstrings concise but informative

## Build / Lint / Test Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run server**: `uvicorn app.main:app --reload`
- **Debug single cycle** (no API): `python debug_engine.py`
- **Run entire test suite**: `pytest`
- **Run only Ollama integration test** (requires `OLLAMA_TEST_URL`): `pytest tests/test_ollama_provider.py -m integration`
