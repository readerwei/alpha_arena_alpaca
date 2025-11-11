import csv
from pathlib import Path
from typing import Dict, Optional

from app.config import settings
from app.models import ExitPlan


class ExitPlanStore:
    """
    Lightweight CSV-backed storage for exit plans so they survive process restarts
    and can be tweaked manually when needed.
    """

    FIELDNAMES = ["symbol", "profit_target", "stop_loss", "invalidation_condition"]

    def __init__(self, file_path: Optional[str | Path] = None):
        path = Path(file_path) if file_path else Path(settings.EXIT_PLAN_CSV_PATH)
        self.file_path = path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, ExitPlan]:
        if not self.file_path.exists():
            return {}

        plans: Dict[str, ExitPlan] = {}
        with self.file_path.open("r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                symbol = row.get("symbol")
                if not symbol:
                    continue
                try:
                    plans[symbol] = ExitPlan(
                        profit_target=float(row.get("profit_target", 0)),
                        stop_loss=float(row.get("stop_loss", 0)),
                        invalidation_condition=row.get(
                            "invalidation_condition", ""
                        ).strip(),
                    )
                except (ValueError, TypeError):
                    # Skip malformed rows but continue loading the rest
                    continue
        return plans

    def save(self, plans: Dict[str, ExitPlan]) -> None:
        with self.file_path.open("w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.FIELDNAMES)
            writer.writeheader()
            for symbol, plan in sorted(plans.items()):
                writer.writerow(
                    {
                        "symbol": symbol,
                        "profit_target": plan.profit_target,
                        "stop_loss": plan.stop_loss,
                        "invalidation_condition": plan.invalidation_condition,
                    }
                )
