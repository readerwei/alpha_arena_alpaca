# AGENTS.md

Field guide for autonomous coding agents working inside `alpha_arena`. Read this before touching the codebase.

## Mission Snapshot
- **Goal**: Simulate Alpha Arena-style autonomous trading agents backed by FastAPI + async trading loop (`alpha-arena-recreation/backend`).
- **Primary runtime**: Python 3.10+ (virtualenv recommended), FastAPI, Alpaca paper trading, yfinance-powered market data, optional Ollama LLM.
- **Current surface area**: Backend is live; frontend folder is empty scaffolding; docs live at root (`README.md`, `execution_flow.md`, `target.md`).
- **Critical dependencies**: Network access for Alpaca + yfinance; .env-driven configuration; see below for required secrets.

## Repository Map
- `alpha-arena-recreation/backend/app/main.py`: FastAPI entrypoint, wires API + background trading loop.
- `app/api/v1/routes.py`: REST surface (`/api/v1/agents`, `/engine/status`) and startup hooks.
- `app/trading_engine/`: Core simulation (`engine.py`, `agent.py`, `portfolio.py`).
- `app/llm/`: Provider interface + Mock/Ollama implementations.
- `app/data/market_data.py`: yfinance + pandas-ta indicator generation for prompts.
- `app/alpaca/client.py`: Thin Alpaca trading client wrapper (paper trading environment by default).
- `app/models.py`: Pydantic models for everything shared between modules and LLM IO.
- `debug_engine.py`: Run a single trading cycle without the API server; use for quick iteration.

## Environment & Secrets
Create `alpha-arena-recreation/backend/.env` (dotenv loaded in `app/config.py`):
```
LLM_PROVIDER=mock            # or ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
ALPACA_API_KEY_ID=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
TRADE_SYMBOLS=AAPL,NVDA,AMD  # optional override via code if needed
LOOP_INTERVAL_SECONDS=300    # optional override via code if needed
```
- The Alpaca client is instantiated at import time; missing keys raise immediately (`app/alpaca/client.py`). Set valid paper keys before starting anything.
- When `LLM_PROVIDER=ollama`, make sure the referenced model is pulled and the server reachable; otherwise stick with `mock` during development.
- yfinance requests hit the public Yahoo Finance API; if offline, expect empty datasets and guard accordingly.

## Backend Workflow & Commands
All commands below assume the working directory `alpha-arena-recreation/backend`.

### Bootstrap
```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Run FastAPI + continuous trading loop
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Startup event (`app/api/v1/routes.py`) spins `engine.run_trading_loop()` as an async task.
- Visit `http://localhost:8000/docs` for interactive OpenAPI once the server is up.

### Debug a single cycle (no server)
```bash
python debug_engine.py
```
- Useful to validate prompt payloads, Alpaca interactions, and `LLMTradeDecision` parsing quickly.

### Tests / lint
- No automated tests yet. When you add features, include lightweight scripts or pytest scaffolding; at minimum, run `python debug_engine.py` and hit `/api/v1/agents`.

## Execution Flow (what the engine actually does)
1. **Startup** (`TradingEngine.__init__`): builds one or more `Agent` instances based on `LLM_PROVIDER`. Ollama mode registers a single named agent; mock mode registers two preconfigured mocks.
2. **Loop** (`engine.run_trading_loop`): every `settings.LOOP_INTERVAL_SECONDS`, gather all agents’ `decide_and_trade()` coroutines concurrently.
3. **Prompt assembly** (`Agent._generate_prompt`): 
   - Pull Alpaca-backed portfolio status (cash, `PositionDetails`, Sharpe computation).
   - Fetch enriched market context from `app/data/market_data.py` (EMA, MACD, RSI, ATR, volume stats).
   - Stitch a verbose markdown-like prompt that mirrors `execution_flow.md`.
4. **LLM interaction**:
   - `MockLLMProvider` fabricates `LLMTradeDecisionList`.
   - `OllamaProvider` POSTs to `/api/generate`, asks for JSON, strips code fences, and validates with Pydantic. Errors fall back to a `hold`.
5. **Trade execution**:
   - All trades route through `Portfolio.execute_trade`, which hits Alpaca’s paper API immediately. Exit plans (profit target/stop loss) are stored per symbol and re-evaluated each cycle.
   - Portfolio stats recompute via live Alpaca account + yfinance quotes for valuation.
6. **API exposure**: endpoint consumers get serialized `AgentState` snapshots (portfolio + trade history) and engine status toggles.

## Coding Standards & Practices
- **Imports**: stdlib → third-party → local, use absolute package paths (`from app...`).
- **Formatting**: 4 spaces, prefer descriptive f-strings, keep lines readable (<120 chars when possible).
- **Typing**: Annotate every function parameter/return. Use `typing` primitives (e.g., `list[str]`). Pydantic models already encapsulate runtime validation—extend them rather than ad-hoc dicts.
- **Concurrency**: Anything touching FastAPI routes or engine loops must stay async-friendly. Blocking IO (e.g., heavy yfinance calls) should be isolated or made async if it creeps into request handlers.
- **Error handling**: 
  - Catch expected provider/network failures and log them; never silently drop exceptions unless there’s a documented fallback (see Ollama provider pattern).
  - When interacting with Alpaca, log symbol/qty on failure to ease postmortems.
- **State management**: Update `app/models.py` and prompt builders together whenever `LLMTradeDecision` schema changes; mismatches create runtime validation errors.
- **Documentation**: Keep docstrings up to date for all public classes/functions. When prompt shape changes, mirror it in `execution_flow.md`.

## Testing & Validation Expectations
- No formal suite exists; rely on:
  - `python debug_engine.py` for end-to-end agent cycle.
  - Manual `curl http://localhost:8000/api/v1/agents` to inspect serialized state.
  - Temporary instrumentation/log prints are acceptable but remove before merge unless they provide persistent value.
- If you introduce new calculators/providers, add deterministic unit tests (pytest) under `alpha-arena-recreation/backend/tests/` and wire them into this doc.

## Open Gaps / Notes for Future Work
- Frontend directory is empty; any new UI scaffolding should live in `alpha-arena-recreation/frontend`.
- Consider providing a mock Alpaca implementation for offline development; right now missing keys hard-stop the app.
- Network dependencies (yfinance, Ollama) can throttle CI. For pipelines, inject cached data or feature flags to short-circuit external calls.
- Build artifacts (`venv/`, `backend.log`) should stay untracked; do not edit inside `venv`.

Keep this file current—update commands, architecture notes, and coding expectations whenever the repo evolves.
