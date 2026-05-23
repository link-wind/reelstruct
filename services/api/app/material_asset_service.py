from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.models import UserSlotAsset


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATERIAL_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "materials"


def save_material_upload(
    file: UploadFile,
    *,
    slot_id: str,
    material_dir: Optional[Path] = None,
) -> UserSlotAsset:
    target_dir = material_dir or DEFAULT_MATERIAL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "material.mp4").suffix or ".mp4"
    filename = f"material-{uuid4().hex[:8]}{suffix.lower()}"
    target_path = target_dir / filename
    with target_path.open("wb") as handle:
        handle.write(file.file.read())

    return UserSlotAsset(
        slot_id=slot_id,
        filename=filename,
        local_path=str(target_path),
        public_url=f"/materials/{filename}",
    )
