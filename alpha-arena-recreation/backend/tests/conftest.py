import os
import sys
from pathlib import Path

# Disable numba JIT caching during tests to avoid filesystem locator issues in pandas_ta.
os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

# Ensure the backend root is importable so `app.*` modules resolve under pytest.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
