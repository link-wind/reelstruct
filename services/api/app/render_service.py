from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Optional

from app.fixture_asset_service import RenderClip


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "output"
VERTICAL_WIDTH = 720
VERTICAL_HEIGHT = 1280
OUTPUT_FPS = 30


@dataclass(frozen=True)
class RenderResult:
    video_url: str
    local_path: str


def build_render_plan(clips: list[RenderClip], output_path: Path) -> dict:
    return {
        "segments": [
            {
                "input": clip.local_path,
                "caption": clip.caption,
                "trimStart": 0,
                "trimDuration": max(0.0, float(clip.duration or 0.0)),
            }
            for clip in clips
        ],
        "output": {
            "path": str(output_path),
            "width": VERTICAL_WIDTH,
            "height": VERTICAL_HEIGHT,
            "fps": OUTPUT_FPS,
            "vcodec": "libx264",
            "acodec": "aac",
        },
    }


def render_demo_video(
    clips: list[RenderClip],
    *,
    output_filename: str,
    output_dir: Optional[Path] = None,
) -> RenderResult:
    if not clips:
        raise RuntimeError("没有可渲染的片段")

    target_dir = output_dir or DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / output_filename
    render_plan = build_render_plan(clips, output_path)

    with tempfile.TemporaryDirectory(dir=target_dir) as temp_dir:
        segment_paths = []
        for index, segment in enumerate(render_plan["segments"], start=1):
            segment_path = Path(temp_dir) / f"segment_{index:02d}.mp4"
            _render_segment(segment, segment_path)
            segment_paths.append(segment_path)
        _concat_segments(segment_paths, output_path)

    return RenderResult(video_url=f"/output/{output_filename}", local_path=str(output_path))


def _render_segment(segment: dict, segment_path: Path) -> None:
    input_path = str(segment["input"])
    duration = max(0.0, float(segment.get("trimDuration") or 0.0))
    if duration <= 0:
        raise RuntimeError(f"片段时长无效: {input_path}")
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, float(segment.get("trimStart") or 0.0))),
        "-t",
        str(duration),
        "-i",
        input_path,
        "-f",
        "lavfi",
        "-t",
        str(duration),
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        f"scale={VERTICAL_WIDTH}:{VERTICAL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VERTICAL_WIDTH}:{VERTICAL_HEIGHT},fps={OUTPUT_FPS},setsar=1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-shortest",
        str(segment_path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def _concat_segments(segment_paths: list[Path], output_path: Path) -> None:
    if not segment_paths:
        raise RuntimeError("没有可合并的片段")

    list_path = output_path.with_suffix(".txt")
    list_path.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        if list_path.exists():
            list_path.unlink()
