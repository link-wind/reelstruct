from pathlib import Path
import subprocess
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.models import SampleUploadResponse, SampleVideoInput


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SAMPLE_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "samples"


def save_sample_upload(file: UploadFile, *, sample_dir: Optional[Path] = None) -> SampleUploadResponse:
    target_dir = sample_dir or DEFAULT_SAMPLE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    sample_id = f"sample-{uuid4().hex[:8]}"
    suffix = Path(file.filename or "sample.mp4").suffix or ".mp4"
    filename = f"{sample_id}{suffix.lower()}"
    target_path = target_dir / filename

    with target_path.open("wb") as handle:
        handle.write(file.file.read())

    duration = probe_video_duration(target_path) or 30.0
    shot_count = detect_shot_count(target_path) or estimate_shot_count(duration)
    return SampleUploadResponse(
        sample_id=sample_id,
        filename=filename,
        local_path=str(target_path),
        public_url=f"/samples/{filename}",
        sample=SampleVideoInput(
            title=file.filename or filename,
            duration=round(duration, 1),
            shot_count=shot_count,
            transcript_summary="已上传样例视频，第一版先基于时长和镜头节奏做结构拆解。",
        ),
    )


def probe_video_duration(path: Path) -> Optional[float]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def estimate_shot_count(duration: float) -> int:
    return max(1, round(duration / 3))


def detect_shot_count(path: Path, *, threshold: float = 0.3) -> Optional[int]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            f"select='gt(scene,{threshold})',metadata=print:file=-",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = f"{result.stdout}\n{result.stderr}"
    scene_cuts = output.count("lavfi.scene_score=")
    if result.returncode != 0 and scene_cuts == 0:
        return None
    return max(1, scene_cuts + 1)
