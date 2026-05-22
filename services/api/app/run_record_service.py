from pathlib import Path
from typing import Optional

from app.models import DemoRunResponse


def save_demo_run_record(run: DemoRunResponse, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    target_path = runs_dir / f"{run.run_id}.json"
    target_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    return target_path


def load_demo_run_record(run_id: str, runs_dir: Path) -> Optional[DemoRunResponse]:
    target_path = runs_dir / f"{run_id}.json"
    if not target_path.exists():
        return None
    return DemoRunResponse.model_validate_json(target_path.read_text(encoding="utf-8"))
