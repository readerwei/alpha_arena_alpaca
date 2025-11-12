from pathlib import Path

from app.models import ExitPlan
from app.storage.exit_plan_store import ExitPlanStore


def test_exit_plan_store_persists_and_loads(tmp_path):
    csv_path = tmp_path / "exit_plans.csv"
    store = ExitPlanStore(csv_path)

    # No file yet -> empty plans
    assert store.load() == {}

    plans = {
        "AAPL": ExitPlan(
            profit_target=210.5, stop_loss=180.25, invalidation_condition="trend breaks"
        ),
        "NVDA": ExitPlan(
            profit_target=500.0, stop_loss=420.0, invalidation_condition="macro shock"
        ),
    }

    store.save(plans)

    reloaded = store.load()
    assert set(reloaded.keys()) == {"AAPL", "NVDA"}
    assert reloaded["AAPL"].profit_target == 210.5
    assert reloaded["AAPL"].stop_loss == 180.25
    assert reloaded["AAPL"].invalidation_condition == "trend breaks"

    # Simulate manual edit by tweaking the CSV directly
    csv_contents = csv_path.read_text().replace("trend breaks", "manual edit")
    csv_path.write_text(csv_contents)

    edited = store.load()
    assert edited["AAPL"].invalidation_condition == "manual edit"


def run_exit_condition_tests() -> int:
    """Expose this module's pytest execution as a callable helper."""
    import pytest

    return pytest.main([__file__])


if __name__ == "__main__":
    raise SystemExit(run_exit_condition_tests())
