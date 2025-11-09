# Alpha Arena Recreation

This project is a simulation of LLM-powered autonomous trading agents, designed to recreate the core concepts of the "Alpha Arena" experiment.

## Project Overview

*   **Purpose**: To create a framework where multiple AI agents, powered by Large Language Models (LLMs), can autonomously trade in a simulated cryptocurrency market. The system is designed to be observable, allowing for the analysis of different agents' behaviors and performance.

*   **Architecture**:
    *   **Backend**: A Python application built with **FastAPI**. It serves a REST API to manage and monitor the trading agents.
    *   **Frontend**: A **React** application (currently planned, not yet implemented) that will act as a dashboard to visualize agent performance, trades, and decision-making processes.

*   **Core Logic**:
    *   The backend runs a **Trading Engine** in a continuous loop.
    *   In each cycle, the engine fetches mock market data for a predefined set of cryptocurrencies (BTC, ETH, SOL).
    *   It then prompts each trading agent for a decision. The prompt includes detailed market data (current, intraday series, longer-term context) and comprehensive account information, mirroring the structure of the original Alpha Arena experiment. The LLM is expected to generate its own "Reasoning Trace" and then output a JSON decision conforming to the `LLMTradeDecision` model.
    *   The system supports configurable LLM providers, including a mock provider for development and an **Ollama provider** for integration with local or remote Ollama instances.
    *   The engine simulates the trade execution and updates the agent's portfolio (cash, positions, PnL).

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
    Create a `.env` file in the `alpha-arena-recreation/backend` directory. This file is crucial for configuring the LLM provider and its settings. It should contain:
    *   `LLM_PROVIDER`: Set to `mock` for a randomized decision-making agent, or `ollama` to use an Ollama-hosted LLM.
    *   `OLLAMA_URL`: (Required if `LLM_PROVIDER=ollama`) The URL of your Ollama server (e.g., `http://localhost:11434`).
    *   `OLLAMA_MODEL`: (Required if `LLM_PROVIDER=ollama`) The name of the Ollama model to use (e.g., `qwen3:4b`).

    Example `.env` for Ollama:
    ```
    LLM_PROVIDER=ollama
    OLLAMA_URL=http://localhost:11434
    OLLAMA_MODEL=qwen3:4b
    ```
    Example `.env` for Mock:
    ```
    LLM_PROVIDER=mock
    ```

5.  **Run the development server**:
    The trading engine starts automatically when the server starts.
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The API documentation will be available at `http://localhost:8000/docs`.

### Frontend (React)

*   **TODO**: Add build and run instructions once the frontend has been implemented.

## Development Conventions

### General
*   **Modular Structure**: The backend code is organized into distinct modules based on functionality:
    *   `app/api`: API endpoints and routing.
    *   `app/trading_engine`: Contains the core simulation logic, including the `TradingEngine`, `Agent`, and `Portfolio` classes.
    *   `app/llm`: Handles interaction with LLMs, with a `BaseLLMProvider` interface and concrete implementations for `MockLLMProvider` and `OllamaProvider`.
    *   `app/data`: Responsible for fetching market data (currently mocked with detailed structures).
    *   `app/models.py`: Defines Pydantic models for data structures like trades, positions, and agent states, including a detailed `LLMTradeDecision` model.

*   **Configuration**: Application settings are managed via a `config.py` file, which loads values from environment variables (a `.env` file is expected). This allows for easy switching between LLM providers and configuration of their parameters.

*   **Mock-First Development**: External services, such as the LLM and market data APIs, are abstracted and have mock implementations. This allows for isolated development and testing of the core application logic without relying on external dependencies or APIs. The mock market data now generates more realistic and detailed time-series and account information.

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

## Build/Lint/Test Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run server**: `uvicorn app.main:app --reload`
- **Debug single cycle**: `python debug_engine.py`
- **Run tests**: No test framework configured yet
- **Run single test**: No test framework configured yet
