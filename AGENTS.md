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
OLLAMA_TIMEOUT_SECONDS=120     # HTTP timeout when calling Ollama (chat responses can take a while)
ALPACA_API_KEY_ID=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
TRADE_SYMBOLS=AAPL,NVDA,AMD  # optional override via code if needed
LOOP_INTERVAL_SECONDS=300    # optional override via code if needed
EXIT_PLAN_CSV_PATH=exit_plans.csv  # optional: persistent store for exit plans
USE_MOCK_ALPACA=true        # set false to hit the real Alpaca API
USE_MOCK_MARKET_DATA=true   # set false to pull from yfinance
```
- The Alpaca client is instantiated at import time; missing keys raise immediately (`app/alpaca/client.py`). Set valid paper keys before starting anything.
- When `LLM_PROVIDER=ollama`, make sure the referenced model is pulled and the server reachable; otherwise stick with `mock` during development.
- yfinance requests hit the public Yahoo Finance API; if offline, expect empty datasets and guard accordingly.
- Exit plans persist to the CSV path above; tweak it before restarting if you want to hand-edit targets/stop losses.
- `LLM_PROVIDER` should remain `mock` unless you have an Ollama instance running at `OLLAMA_URL`. When using Ollama the backend writes every prompt/response (plus the model’s reasoning trace) to `alpha-arena-recreation/backend/logging/ollama_prompts.log` for post-mortems.
- `USE_MOCK_ALPACA` defaults to `true` so you can run the engine offline; set it to `false` (with valid keys) for live paper trading.
- `USE_MOCK_MARKET_DATA` avoids yfinance calls in sandboxed environments; turn it off once you have network access.
- **Never modify `.env` files without explicit user permission.** Treat every env file as sensitive secrets storage; read-only unless the user directs otherwise.

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
- `pytest` exercises backend units (`alpha-arena-recreation/backend/tests`).
- Still run `python debug_engine.py` and hit `/api/v1/agents` for smoke coverage after heavy changes.

## Execution Flow (what the engine actually does)
1. **Startup** (`TradingEngine.__init__`): builds one or more `Agent` instances based on `LLM_PROVIDER`. Ollama mode registers a single named agent; mock mode registers two preconfigured mocks.
2. **Loop** (`engine.run_trading_loop`): every `settings.LOOP_INTERVAL_SECONDS`, gather all agents’ `decide_and_trade()` coroutines concurrently.
3. **Prompt assembly** (`Agent._generate_prompt`): 
   - Pull Alpaca-backed portfolio status (cash, `PositionDetails`, Sharpe computation).
   - Fetch enriched market context from `app/data/market_data.py`. “Intraday” series are daily bars; longer-term context is resampled weekly so EMA/MACD/RSI/ATR reflect multi-week trends.
   - Stitch a verbose markdown-like prompt (see `execution_flow.md`). The final instructions now **require** a JSON array under `decisions`, explicit `confidence`, and a detailed `reasoning_trace` for each trade.
4. **LLM interaction**:
   - `MockLLMProvider` fabricates `LLMTradeDecisionList`.
   - `OllamaProvider` first tries `/api/chat` (with a system prompt that enforces the schema, risk review, and reasoning trace). Responses are logged, normalized, and validated. If the chat endpoint/model is unavailable (404, etc.), the provider automatically falls back to `/api/generate` using the same system prompt. Any malformed payload is coerced into the expected list when possible; otherwise the agent defaults to a “hold” decision.
5. **Trade execution**:
   - All trades route through `Portfolio.execute_trade`, which hits Alpaca’s paper API immediately. Exit plans (profit target/stop loss) are stored per symbol and re-evaluated each cycle.
   - Exit plans are mirrored into the CSV store so restarts and manual edits carry forward.
   - When `USE_MOCK_ALPACA=true`, trades are simulated in-memory so you can debug without network access; set it to `false` when you are ready to send real paper orders.
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
- **Prompt discipline**: `Agent._generate_prompt()` now enforces raw-JSON replies, filters live positions to `settings.TRADE_SYMBOLS`, and tells the LLM to evaluate exit plans itself. It also reminds the model to keep `decisions` as an array and to emit `reasoning_trace` entries describing the indicator/risk checks that led to each action. Keep those constraints in sync with any schema tweaks or symbol-list changes.
- **Documentation**: Keep docstrings up to date for all public classes/functions. When prompt shape changes, mirror it in `execution_flow.md`.

## Testing & Validation Expectations
- Backend unit tests live in `alpha-arena-recreation/backend/tests`; run them with `pytest`.
- To run the optional Ollama integration test, set `OLLAMA_TEST_URL` (and optionally `OLLAMA_TEST_MODEL`) and execute `pytest tests/test_ollama_provider.py -m integration`. The helper will `asyncio.run` the provider against your live endpoint.
- Always smoke test the trading loop via `python debug_engine.py` after touching agent logic.
- Hit `curl http://localhost:8000/api/v1/agents` (or the Swagger UI) while the server runs to sanity-check serialized state.
- Temporary instrumentation/log prints are acceptable during debugging but remove them before merging unless they provide lasting value.
- When adding new calculators/providers, extend the pytest suite so deterministic behaviors (mocked data, provider fallbacks) stay covered.

## Open Gaps / Notes for Future Work
- Frontend directory is empty; any new UI scaffolding should live in `alpha-arena-recreation/frontend`.
- Consider providing a mock Alpaca implementation for offline development; right now missing keys hard-stop the app.
- Network dependencies (yfinance, Ollama) can throttle CI. For pipelines, inject cached data or feature flags to short-circuit external calls.
- Build artifacts (`venv/`, `backend.log`) should stay untracked; do not edit inside `venv`.
- Ollama must return a JSON object containing a `decisions` list. The provider now normalizes symbol-keyed maps and even plain “status” blobs, but don’t rely on that—always keep model prompts/examples aligned with the expected schema.
- When calling a host-level Ollama server from the dev shell, set `OLLAMA_URL` to a reachable address (e.g., `http://host.docker.internal:11434`) and validate with `curl $OLLAMA_URL/api/tags` from inside the repo before running `debug_engine.py`.
- Large Ollama models can exceed the CLI command timeout. Use `LLM_PROVIDER=mock` or a smaller model for quick diagnostics, or restart the Codex CLI with a higher timeout when you need full-length runs.

Keep this file current—update commands, architecture notes, and coding expectations whenever the repo evolves.
