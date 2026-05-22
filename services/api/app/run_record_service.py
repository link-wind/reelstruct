import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models import DemoRunResponse, RunRecordSummary


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


def list_demo_run_records(runs_dir: Path, limit: int = 20) -> list[RunRecordSummary]:
    summaries: list[tuple[tuple[str, int], RunRecordSummary]] = []

    for path in runs_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        preview = payload.get("preview", {})
        transfer_plan = preview.get("transfer_plan", {})
        created_at = payload.get("created_at") or _mtime_to_iso(path)
        summaries.append(
            (
                (created_at, path.stat().st_mtime_ns),
                RunRecordSummary(
                    run_id=payload.get("run_id", path.stem),
                    created_at=created_at,
                    status=payload.get("status", "failed"),
                    title=transfer_plan.get("title", "未命名迁移任务"),
                    target_topic=transfer_plan.get("target_topic", ""),
                    gap_count=len(transfer_plan.get("gaps", [])),
                    material_request_count=len(transfer_plan.get("material_request_sheet", [])),
                    video_url=payload.get("rendered_video", {}).get("video_url", ""),
                ),
            )
        )

    return [item for _, item in sorted(summaries, key=lambda pair: pair[0], reverse=True)[:limit]]


def _mtime_to_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
