from pathlib import Path
import subprocess
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.api.api_models import SampleUploadResponse, SampleVideoInput, TranscriptUploadResponse
from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.shot_detector import detect_video_signal


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SAMPLE_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "samples"
DEFAULT_KEYFRAMES_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "keyframes"


def save_sample_upload(
    file: UploadFile,
    *,
    sample_dir: Optional[Path] = None,
    keyframes_dir: Optional[Path] = None,
) -> SampleUploadResponse:
    target_dir = sample_dir or DEFAULT_SAMPLE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    sample_id = f"sample-{uuid4().hex[:8]}"
    suffix = Path(file.filename or "sample.mp4").suffix or ".mp4"
    filename = f"{sample_id}{suffix.lower()}"
    target_path = target_dir / filename

    with target_path.open("wb") as handle:
        handle.write(file.file.read())

    video_signal = detect_video_signal(target_path)
    target_keyframes_dir = (keyframes_dir or DEFAULT_KEYFRAMES_DIR) / sample_id
    keyframes = extract_keyframes(
        target_path,
        video_signal.shots,
        output_dir=target_keyframes_dir,
        public_prefix=f"/keyframes/{sample_id}",
    )

    return SampleUploadResponse(
        sample_id=sample_id,
        filename=filename,
        local_path=str(target_path),
        public_url=f"/samples/{filename}",
        sample=SampleVideoInput(
            title=file.filename or filename,
            duration=round(video_signal.metadata.duration, 1),
            shot_count=video_signal.shot_count,
            transcript_summary="已上传样例视频，系统已完成真实视频信号解析，等待 AI 视频结构拆解。",
        ),
        video_signal=video_signal,
        keyframes=keyframes,
    )


def extract_transcript_upload(file: UploadFile) -> TranscriptUploadResponse:
    raw_bytes = file.file.read()
    raw_text = raw_bytes.decode("utf-8", errors="ignore")
    transcript_summary = normalize_transcript_text(raw_text)
    return TranscriptUploadResponse(
        filename=file.filename or "transcript.txt",
        transcript_summary=transcript_summary,
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


def normalize_transcript_text(raw_text: str) -> str:
    cleaned_lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        if "-->" in stripped:
            continue
        cleaned_lines.append(stripped)
    return " ".join(cleaned_lines)
