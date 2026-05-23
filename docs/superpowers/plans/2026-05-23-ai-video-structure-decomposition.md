# AI Video Structure Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace rule-led sample structure decomposition with a real AI-driven video structure decomposition path built from actual video metadata, shot detection, keyframes, vision analysis, and AI segment reasoning.

**Architecture:** Build this as vertical feature slices. The upload path first produces real video signals, then shot evidence with keyframes, then real AI visual descriptions, then AI structure segments that are adapted into the existing `TemplateStructure` used by transfer, material gap, packaging, and render services. Rules may generate evidence and emergency failure protection, but must not decide the creative structure.

**Tech Stack:** FastAPI, Pydantic, ffprobe/ffmpeg subprocess calls, optional PySceneDetect/OpenCV fallback, OpenAI-compatible multimodal HTTP calls via `httpx`, Next.js/TypeScript UI, pytest.

---

## Scope And Existing Entry Points

This plan implements the approved spec at `docs/superpowers/specs/2026-05-23-ai-video-structure-decomposition-design.md`.

Current relevant entry points:

- Backend upload endpoint: `services/api/app/main.py` `POST /api/samples/upload`
- Current sample service: `services/api/app/sample_service.py`
- Current structure service: `services/api/app/structure_service.py`
- Existing models: `services/api/app/models.py`
- Current frontend upload UI: `apps/web/src/app/ReelStructWorkspace.tsx`
- Existing backend checks:
  - `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/pytest tests/test_structure_service.py tests/test_workflow_service.py tests/test_media_api.py tests/test_fixture_asset_service.py -q`
- Existing frontend build:
  - `cd /Users/linkwind/Code/ReelStruct/apps/web && npm run build`

Implementation commits should be grouped by vertical stage, not every tiny step, because the project owner prefers fewer commits.

## File Structure

Create focused backend modules:

- `services/api/app/video_understanding/schemas.py`
  - Owns `VideoMetadata`, `VideoShot`, `VideoSignal`, `KeyframeEvidence`, `ShotVisualAnalysis`, `VideoStructureSegment`, `AIStructureAnalysis`.
- `services/api/app/video_understanding/media_probe.py`
  - Owns real `ffprobe` metadata parsing.
- `services/api/app/video_understanding/shot_detector.py`
  - Owns real shot detection and uniform fallback annotation.
- `services/api/app/video_understanding/keyframe_service.py`
  - Owns real ffmpeg keyframe extraction.
- `services/api/app/video_understanding/evidence_service.py`
  - Builds shot evidence from video signals, keyframes, transcript text, and visual analysis.
- `services/api/app/video_understanding/ai_vision_service.py`
  - Calls a real multimodal model for keyframe visual understanding.
- `services/api/app/video_understanding/ai_structure_service.py`
  - Calls a real AI model to produce `AIStructureAnalysis`.
- `services/api/app/video_understanding/template_adapter.py`
  - Converts `AIStructureAnalysis` to existing `TemplateStructure`.
- `services/api/app/video_understanding/pipeline.py`
  - Orchestrates sample video analysis for the upload and preview paths.

Modify existing backend modules:

- `services/api/app/models.py`
  - Extend sample upload and template analysis models with video signal and AI source fields.
- `services/api/app/sample_service.py`
  - Replace duration/shot-count-only upload response with real video signal and keyframe evidence generation.
- `services/api/app/structure_service.py`
  - Add AI structure decomposition path; keep the old four-slot rule function only as emergency fallback with explicit source.
- `services/api/app/main.py`
  - Mount keyframe static directory and pass storage dirs into sample pipeline.
- `services/api/app/run_export_service.py`
  - Export AI decomposition evidence file.

Modify frontend:

- `apps/web/src/app/ReelStructWorkspace.tsx`
  - Add sample video metadata, shot list, keyframes, AI visual notes, AI source, confidence, and evidence display.
- `apps/web/scripts/check-material-request-sheet.mjs`
  - Extend regression checks for AI decomposition evidence after the feature is integrated.

Create tests:

- `services/api/tests/test_video_understanding_media.py`
- `services/api/tests/test_video_understanding_pipeline.py`
- `services/api/tests/test_ai_video_structure_service.py`
- Extend `services/api/tests/test_media_api.py`
- Extend `services/api/tests/test_structure_service.py`
- Extend `services/api/tests/test_workflow_service.py`

## Task 1: Real Video Metadata Model And Probe

**Files:**

- Create: `services/api/app/video_understanding/__init__.py`
- Create: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/media_probe.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write failing tests for metadata probing**

Add `services/api/tests/test_video_understanding_media.py`:

```python
from pathlib import Path

from app.video_understanding.media_probe import probe_video_metadata


def test_probe_video_metadata_returns_real_duration_resolution_and_fps():
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    metadata = probe_video_metadata(fixture_path)

    assert metadata.duration > 0
    assert metadata.fps > 0
    assert metadata.width > 0
    assert metadata.height > 0
    assert metadata.format_name
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py::test_probe_video_metadata_returns_real_duration_resolution_and_fps -q
```

Expected: FAIL because `app.video_understanding.media_probe` does not exist.

- [ ] **Step 3: Add schemas**

Create `services/api/app/video_understanding/__init__.py` as an empty module.

Create `services/api/app/video_understanding/schemas.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    duration: float
    fps: float
    width: int
    height: int
    format_name: str = ""


class VideoShot(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    keyframe_time: float = 0


class RhythmMetrics(BaseModel):
    avg_shot_duration: float = 0
    cut_density: Literal["slow", "medium", "fast"] = "medium"
    fastest_window: str = ""
    slowest_window: str = ""


class VideoSignal(BaseModel):
    metadata: VideoMetadata
    shot_count: int = 0
    detection_method: Literal["scene_detect", "uniform_fallback"] = "scene_detect"
    shots: list[VideoShot] = Field(default_factory=list)
    rhythm_metrics: RhythmMetrics = Field(default_factory=RhythmMetrics)
```

- [ ] **Step 4: Implement ffprobe metadata parsing**

Create `services/api/app/video_understanding/media_probe.py`:

```python
import json
from pathlib import Path
import subprocess

from app.video_understanding.schemas import VideoMetadata


def probe_video_metadata(path: Path) -> VideoMetadata:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe failed for {path}: {result.stderr.strip()}")

    payload = json.loads(result.stdout)
    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise ValueError(f"no video stream found for {path}")

    duration = float(payload.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    fps = _parse_fps(str(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"))
    format_name = str(payload.get("format", {}).get("format_name") or "")
    if duration <= 0 or width <= 0 or height <= 0 or fps <= 0:
        raise ValueError(f"incomplete video metadata for {path}")

    return VideoMetadata(
        duration=round(duration, 3),
        fps=round(fps, 3),
        width=width,
        height=height,
        format_name=format_name,
    )


def _parse_fps(value: str) -> float:
    if "/" not in value:
        return float(value or 0)
    numerator, denominator = value.split("/", 1)
    denominator_float = float(denominator or 1)
    if denominator_float == 0:
        return 0
    return float(numerator or 0) / denominator_float
```

- [ ] **Step 5: Run test and verify it passes**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py::test_probe_video_metadata_returns_real_duration_resolution_and_fps -q
```

Expected: PASS.

## Task 2: Real Shot Detection And Rhythm Metrics

**Files:**

- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/shot_detector.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write failing tests for shot detection**

Append to `services/api/tests/test_video_understanding_media.py`:

```python
from app.video_understanding.shot_detector import detect_video_signal


def test_detect_video_signal_returns_shots_and_rhythm_metrics():
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    signal = detect_video_signal(fixture_path)

    assert signal.metadata.duration > 0
    assert signal.shot_count == len(signal.shots)
    assert signal.shot_count >= 1
    assert signal.shots[0].start == 0
    assert signal.shots[-1].end <= signal.metadata.duration + 0.1
    assert signal.rhythm_metrics.avg_shot_duration > 0
    assert signal.rhythm_metrics.cut_density in {"slow", "medium", "fast"}
    assert signal.detection_method in {"scene_detect", "uniform_fallback"}
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py::test_detect_video_signal_returns_shots_and_rhythm_metrics -q
```

Expected: FAIL because `shot_detector.py` does not exist.

- [ ] **Step 3: Implement shot detection**

Create `services/api/app/video_understanding/shot_detector.py`:

```python
from pathlib import Path
import re
import subprocess

from app.video_understanding.media_probe import probe_video_metadata
from app.video_understanding.schemas import RhythmMetrics, VideoShot, VideoSignal


def detect_video_signal(path: Path, *, threshold: float = 0.3, fallback_seconds: float = 3.0) -> VideoSignal:
    metadata = probe_video_metadata(path)
    cuts = _detect_scene_cut_times(path, threshold=threshold)
    detection_method = "scene_detect"
    if len(cuts) < 1 and metadata.duration > fallback_seconds * 2:
        shots = _uniform_shots(metadata.duration, fallback_seconds=fallback_seconds)
        detection_method = "uniform_fallback"
    else:
        shots = _shots_from_cuts(metadata.duration, cuts)
    rhythm_metrics = _build_rhythm_metrics(shots)
    return VideoSignal(
        metadata=metadata,
        shot_count=len(shots),
        detection_method=detection_method,
        shots=shots,
        rhythm_metrics=rhythm_metrics,
    )


def _detect_scene_cut_times(path: Path, *, threshold: float) -> list[float]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
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
    times = []
    for match in re.finditer(r"pts_time:([0-9.]+)", output):
        value = float(match.group(1))
        if value > 0:
            times.append(round(value, 3))
    return sorted(set(times))


def _shots_from_cuts(duration: float, cuts: list[float]) -> list[VideoShot]:
    boundaries = [0.0, *[cut for cut in cuts if 0 < cut < duration], duration]
    shots = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        if end <= start:
            continue
        shots.append(_make_shot(index, start, end))
    return shots or [_make_shot(1, 0, duration)]


def _uniform_shots(duration: float, *, fallback_seconds: float) -> list[VideoShot]:
    shots = []
    start = 0.0
    index = 1
    while start < duration:
        end = min(duration, start + fallback_seconds)
        shots.append(_make_shot(index, start, end))
        start = end
        index += 1
    return shots


def _make_shot(index: int, start: float, end: float) -> VideoShot:
    start = round(start, 3)
    end = round(end, 3)
    return VideoShot(
        index=index,
        start=start,
        end=end,
        duration=round(end - start, 3),
        keyframe_time=round(start + (end - start) / 2, 3),
    )


def _build_rhythm_metrics(shots: list[VideoShot]) -> RhythmMetrics:
    if not shots:
        return RhythmMetrics()
    avg = sum(shot.duration for shot in shots) / len(shots)
    if avg < 1.8:
        density = "fast"
    elif avg > 3.5:
        density = "slow"
    else:
        density = "medium"
    shortest = min(shots, key=lambda shot: shot.duration)
    longest = max(shots, key=lambda shot: shot.duration)
    return RhythmMetrics(
        avg_shot_duration=round(avg, 2),
        cut_density=density,
        fastest_window=f"{shortest.start}-{shortest.end}s",
        slowest_window=f"{longest.start}-{longest.end}s",
    )
```

- [ ] **Step 4: Run shot detection test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py -q
```

Expected: both tests PASS.

## Task 3: Real Keyframe Extraction

**Files:**

- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/keyframe_service.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Add keyframe schema**

Extend `services/api/app/video_understanding/schemas.py`:

```python
class KeyframeEvidence(BaseModel):
    shot_index: int
    keyframe_time: float
    local_path: str
    public_url: str
```

- [ ] **Step 2: Write failing keyframe test**

Append to `services/api/tests/test_video_understanding_media.py`:

```python
from app.video_understanding.keyframe_service import extract_keyframes


def test_extract_keyframes_writes_real_image_files(tmp_path):
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"
    signal = detect_video_signal(fixture_path)

    keyframes = extract_keyframes(
        fixture_path,
        signal.shots[:2],
        output_dir=tmp_path / "keyframes",
        public_prefix="/keyframes",
    )

    assert len(keyframes) == min(2, len(signal.shots))
    for keyframe in keyframes:
        path = Path(keyframe.local_path)
        assert path.is_file()
        assert path.suffix == ".jpg"
        assert keyframe.public_url.startswith("/keyframes/")
```

- [ ] **Step 3: Run keyframe test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py::test_extract_keyframes_writes_real_image_files -q
```

Expected: FAIL because `keyframe_service.py` does not exist.

- [ ] **Step 4: Implement keyframe extraction**

Create `services/api/app/video_understanding/keyframe_service.py`:

```python
from pathlib import Path
import subprocess

from app.video_understanding.schemas import KeyframeEvidence, VideoShot


def extract_keyframes(
    video_path: Path,
    shots: list[VideoShot],
    *,
    output_dir: Path,
    public_prefix: str,
) -> list[KeyframeEvidence]:
    output_dir.mkdir(parents=True, exist_ok=True)
    keyframes: list[KeyframeEvidence] = []
    for shot in shots:
        filename = f"shot-{shot.index:03d}.jpg"
        target_path = output_dir / filename
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(shot.keyframe_time),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-y",
                str(target_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not target_path.is_file():
            continue
        keyframes.append(
            KeyframeEvidence(
                shot_index=shot.index,
                keyframe_time=shot.keyframe_time,
                local_path=str(target_path),
                public_url=f"{public_prefix.rstrip('/')}/{filename}",
            )
        )
    return keyframes
```

- [ ] **Step 5: Run media tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py -q
```

Expected: PASS.

## Task 4: Expose Real Video Signal And Keyframes From Sample Upload

**Files:**

- Modify: `services/api/app/models.py`
- Modify: `services/api/app/main.py`
- Modify: `services/api/app/sample_service.py`
- Test: `services/api/tests/test_media_api.py`
- Modify: `apps/web/src/app/ReelStructWorkspace.tsx`

- [ ] **Step 1: Write failing API test**

Append to `services/api/tests/test_media_api.py`:

```python
def test_upload_sample_video_returns_real_video_signal_and_keyframes():
    client = TestClient(app)
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    response = client.post(
        "/api/samples/upload",
        files={"file": ("sample.mp4", fixture_path.read_bytes(), "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample"]["duration"] > 0
    assert body["video_signal"]["metadata"]["duration"] > 0
    assert body["video_signal"]["shot_count"] >= 1
    assert body["video_signal"]["shots"][0]["start"] == 0
    assert len(body["keyframes"]) >= 1
    assert body["keyframes"][0]["public_url"].startswith("/keyframes/")
```

- [ ] **Step 2: Run failing API test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_media_api.py::test_upload_sample_video_returns_real_video_signal_and_keyframes -q
```

Expected: FAIL because `SampleUploadResponse` does not include `video_signal` or `keyframes`.

- [ ] **Step 3: Add response fields**

Modify imports and `SampleUploadResponse` in `services/api/app/models.py`:

```python
from app.video_understanding.schemas import KeyframeEvidence, VideoSignal


class SampleUploadResponse(BaseModel):
    sample_id: str
    filename: str
    local_path: str
    public_url: str
    sample: SampleVideoInput
    video_signal: VideoSignal | None = None
    keyframes: list[KeyframeEvidence] = Field(default_factory=list)
```

- [ ] **Step 4: Mount keyframe static directory**

Modify `services/api/app/main.py` near storage constants:

```python
KEYFRAMES_DIR = STORAGE_DIR / "keyframes"
KEYFRAMES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/keyframes", StaticFiles(directory=str(KEYFRAMES_DIR)), name="keyframes")
```

Pass `keyframes_dir=KEYFRAMES_DIR` into `save_sample_upload`.

- [ ] **Step 5: Generate video signal and keyframes in upload**

Modify `services/api/app/sample_service.py`:

```python
from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.shot_detector import detect_video_signal

DEFAULT_KEYFRAME_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "keyframes"


def save_sample_upload(
    file: UploadFile,
    *,
    sample_dir: Optional[Path] = None,
    keyframes_dir: Optional[Path] = None,
) -> SampleUploadResponse:
    ...
    video_signal = detect_video_signal(target_path)
    sample_keyframe_dir = (keyframes_dir or DEFAULT_KEYFRAME_DIR) / sample_id
    keyframes = extract_keyframes(
        target_path,
        video_signal.shots,
        output_dir=sample_keyframe_dir,
        public_prefix=f"/keyframes/{sample_id}",
    )
    return SampleUploadResponse(
        ...
        sample=SampleVideoInput(
            title=file.filename or filename,
            duration=round(video_signal.metadata.duration, 1),
            shot_count=video_signal.shot_count,
            transcript_summary="已上传样例视频，系统已完成真实视频信号解析，等待 AI 视频结构拆解。",
        ),
        video_signal=video_signal,
        keyframes=keyframes,
    )
```

Keep `probe_video_duration`, `detect_shot_count`, and `estimate_shot_count` temporarily for material analysis compatibility; do not let them decide sample structure.

- [ ] **Step 6: Extend frontend types and sample panel**

Modify `apps/web/src/app/ReelStructWorkspace.tsx` types:

```ts
type VideoShot = {
  index: number
  start: number
  end: number
  duration: number
  keyframe_time: number
}

type VideoSignal = {
  metadata: {
    duration: number
    fps: number
    width: number
    height: number
    format_name: string
  }
  shot_count: number
  detection_method: 'scene_detect' | 'uniform_fallback'
  shots: VideoShot[]
  rhythm_metrics: {
    avg_shot_duration: number
    cut_density: 'slow' | 'medium' | 'fast'
    fastest_window: string
    slowest_window: string
  }
}

type KeyframeEvidence = {
  shot_index: number
  keyframe_time: number
  local_path: string
  public_url: string
}

type SampleUploadResponse = {
  sample_id: string
  filename: string
  public_url: string
  sample: SampleVideoInput
  video_signal: VideoSignal | null
  keyframes: KeyframeEvidence[]
}
```

In the sample info panel, add visible lines:

```tsx
<p>Resolution: {sampleUpload?.video_signal ? `${sampleUpload.video_signal.metadata.width}x${sampleUpload.video_signal.metadata.height}` : 'waiting for upload'}</p>
<p>FPS: {sampleUpload?.video_signal?.metadata.fps || 'waiting for upload'}</p>
<p>Detection: {sampleUpload?.video_signal?.detection_method || 'not analyzed'}</p>
<p>Avg shot: {sampleUpload?.video_signal?.rhythm_metrics.avg_shot_duration || 0}s</p>
```

Render keyframes below the panel:

```tsx
{sampleUpload?.keyframes?.length ? (
  <div className="mt-4 grid gap-3 sm:grid-cols-2">
    {sampleUpload.keyframes.slice(0, 6).map((keyframe) => (
      <figure key={keyframe.shot_index} className="rounded-md border border-line bg-white p-2">
        <img className="aspect-video w-full rounded object-cover" src={keyframe.public_url} alt={`Shot ${keyframe.shot_index}`} />
        <figcaption className="mt-2 text-xs text-slate-600">
          Shot {keyframe.shot_index} / {keyframe.keyframe_time}s
        </figcaption>
      </figure>
    ))}
  </div>
) : null}
```

- [ ] **Step 7: Run backend and frontend checks for Stage 1**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py tests/test_media_api.py -q
```

Expected: PASS.

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run build
```

Expected: PASS.

- [ ] **Step 8: Stage 1 commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding services/api/app/models.py services/api/app/main.py services/api/app/sample_service.py services/api/tests/test_video_understanding_media.py services/api/tests/test_media_api.py apps/web/src/app/ReelStructWorkspace.tsx
git commit -m "feat: parse sample video signals"
```

## Task 5: Real AI Vision Understanding For Keyframes

**Files:**

- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/ai_vision_service.py`
- Modify: `services/api/app/video_understanding/evidence_service.py`
- Modify: `services/api/requirements.txt`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [ ] **Step 1: Add visual analysis schema**

Extend `services/api/app/video_understanding/schemas.py`:

```python
class ShotVisualAnalysis(BaseModel):
    shot_index: int
    visual_summary: str
    subject_type: str = ""
    scene_type: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    confidence: float = 0
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Add real model configuration**

Modify `services/api/requirements.txt`:

```text
fastapi==0.115.6
httpx==0.28.1
pydantic==2.10.4
python-multipart==0.0.20
pytest==8.3.4
uvicorn==0.34.0
```

No new dependency is required because `httpx` already exists.

- [ ] **Step 3: Write a real-integration test gated by API key**

Create `services/api/tests/test_ai_video_structure_service.py`:

```python
import os
from pathlib import Path

import pytest

from app.video_understanding.ai_vision_service import analyze_keyframe_visuals
from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.shot_detector import detect_video_signal


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires real AI provider")
def test_analyze_keyframe_visuals_returns_real_model_descriptions(tmp_path):
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"
    signal = detect_video_signal(fixture_path)
    keyframes = extract_keyframes(
        fixture_path,
        signal.shots[:1],
        output_dir=tmp_path / "keyframes",
        public_prefix="/keyframes/test",
    )

    analyses = analyze_keyframe_visuals(keyframes)

    assert len(analyses) == 1
    assert analyses[0].shot_index == keyframes[0].shot_index
    assert analyses[0].visual_summary.strip()
    assert analyses[0].confidence > 0
```

This test is skipped without `OPENAI_API_KEY`, but the feature acceptance must be run once with a real key before claiming AI vision is complete.

- [ ] **Step 4: Implement real AI vision call**

Create `services/api/app/video_understanding/ai_vision_service.py`:

```python
import base64
import json
import os
from pathlib import Path

import httpx

from app.video_understanding.schemas import KeyframeEvidence, ShotVisualAnalysis


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def analyze_keyframe_visuals(keyframes: list[KeyframeEvidence]) -> list[ShotVisualAnalysis]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for real AI vision analysis")
    model = os.getenv("REELSTRUCT_VISION_MODEL", "gpt-4.1-mini")
    analyses = []
    for keyframe in keyframes:
        image_data_url = _image_data_url(Path(keyframe.local_path))
        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "请分析这张短视频关键帧。输出严格 JSON，字段为 "
                                "visual_summary, subject_type, scene_type, packaging_signals, confidence, warnings。"
                                "packaging_signals 只写画面中可见的字幕、标题条、贴纸、转场、封面感等信号。"
                            ),
                        },
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
        }
        result = httpx.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        result.raise_for_status()
        parsed = _extract_json(result.json())
        analyses.append(
            ShotVisualAnalysis(
                shot_index=keyframe.shot_index,
                visual_summary=str(parsed.get("visual_summary") or ""),
                subject_type=str(parsed.get("subject_type") or ""),
                scene_type=str(parsed.get("scene_type") or ""),
                packaging_signals=[str(item) for item in parsed.get("packaging_signals") or []],
                confidence=float(parsed.get("confidence") or 0),
                warnings=[str(item) for item in parsed.get("warnings") or []],
            )
        )
    return analyses


def _image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _extract_json(payload: dict) -> dict:
    texts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(str(content.get("text") or ""))
    raw_text = "\n".join(texts).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json\n", "", 1)
    return json.loads(raw_text)
```

- [ ] **Step 5: Run non-keyed test suite**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_ai_video_structure_service.py -q
```

Expected without key: `1 skipped`.

- [ ] **Step 6: Run real AI vision acceptance with API key**

Run only in an environment with `OPENAI_API_KEY`:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY=$OPENAI_API_KEY PYTHONPATH=. .venv/bin/pytest tests/test_ai_video_structure_service.py::test_analyze_keyframe_visuals_returns_real_model_descriptions -q
```

Expected with key: PASS and real model output.

- [ ] **Step 7: Stage 2 commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/schemas.py services/api/app/video_understanding/ai_vision_service.py services/api/tests/test_ai_video_structure_service.py
git commit -m "feat: analyze keyframes with ai vision"
```

## Task 6: Build Shot Evidence And AI Structure Analysis

**Files:**

- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/evidence_service.py`
- Create: `services/api/app/video_understanding/ai_structure_service.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [ ] **Step 1: Add evidence and structure schemas**

Extend `services/api/app/video_understanding/schemas.py`:

```python
class ShotEvidence(BaseModel):
    shot_index: int
    start: float
    end: float
    duration: float
    keyframe_public_url: str = ""
    transcript_text: str = ""
    visual_summary: str = ""
    packaging_signals: list[str] = Field(default_factory=list)


class VideoStructureSegment(BaseModel):
    id: str
    label: str
    type: str
    start: float
    end: float
    shot_indices: list[int] = Field(default_factory=list)
    purpose: str
    method: str
    evidence: str
    rhythm: str
    packaging: str
    required_asset: str = ""
    transferable_rule: str
    non_transferable: str
    confidence: float = 0


class AIRhythmStructure(BaseModel):
    summary: str = ""
    peak_position: str = ""
    slowdown_position: str = ""


class AIPackagingStructure(BaseModel):
    caption_density: str = ""
    title_style: str = ""
    transition_style: str = ""
    cover_style: str = ""


class AIStructureAnalysis(BaseModel):
    source: Literal["ai"] = "ai"
    headline: str
    segments: list[VideoStructureSegment]
    rhythm_structure: AIRhythmStructure = Field(default_factory=AIRhythmStructure)
    packaging_structure: AIPackagingStructure = Field(default_factory=AIPackagingStructure)
    confidence: float = 0
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Write failing evidence test**

Append to `services/api/tests/test_ai_video_structure_service.py`:

```python
from app.video_understanding.evidence_service import build_shot_evidence
from app.video_understanding.schemas import ShotVisualAnalysis


def test_build_shot_evidence_combines_shots_keyframes_transcript_and_visuals(tmp_path):
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"
    signal = detect_video_signal(fixture_path)
    keyframes = extract_keyframes(
        fixture_path,
        signal.shots[:1],
        output_dir=tmp_path / "keyframes",
        public_prefix="/keyframes/test",
    )
    visuals = [
        ShotVisualAnalysis(
            shot_index=keyframes[0].shot_index,
            visual_summary="产品特写，画面有大标题",
            packaging_signals=["大标题"],
            confidence=0.9,
        )
    ]

    evidence = build_shot_evidence(signal.shots[:1], keyframes, visuals, "开头提出痛点。")

    assert evidence[0].shot_index == 1
    assert evidence[0].keyframe_public_url.startswith("/keyframes/")
    assert evidence[0].transcript_text
    assert evidence[0].visual_summary == "产品特写，画面有大标题"
    assert "大标题" in evidence[0].packaging_signals
```

- [ ] **Step 3: Implement evidence builder**

Create `services/api/app/video_understanding/evidence_service.py`:

```python
from app.video_understanding.schemas import KeyframeEvidence, ShotEvidence, ShotVisualAnalysis, VideoShot


def build_shot_evidence(
    shots: list[VideoShot],
    keyframes: list[KeyframeEvidence],
    visual_analyses: list[ShotVisualAnalysis],
    transcript_summary: str,
) -> list[ShotEvidence]:
    keyframe_lookup = {item.shot_index: item for item in keyframes}
    visual_lookup = {item.shot_index: item for item in visual_analyses}
    transcript_parts = _split_transcript(transcript_summary, len(shots))
    evidence = []
    for index, shot in enumerate(shots):
        keyframe = keyframe_lookup.get(shot.index)
        visual = visual_lookup.get(shot.index)
        evidence.append(
            ShotEvidence(
                shot_index=shot.index,
                start=shot.start,
                end=shot.end,
                duration=shot.duration,
                keyframe_public_url=keyframe.public_url if keyframe else "",
                transcript_text=transcript_parts[index] if index < len(transcript_parts) else "",
                visual_summary=visual.visual_summary if visual else "",
                packaging_signals=visual.packaging_signals if visual else [],
            )
        )
    return evidence


def _split_transcript(transcript_summary: str, count: int) -> list[str]:
    parts = [item.strip() for item in transcript_summary.replace("?", "？").replace("!", "。").split("。") if item.strip()]
    if not parts:
        return ["" for _ in range(count)]
    if len(parts) >= count:
        return parts[:count]
    return [*parts, *["" for _ in range(count - len(parts))]]
```

- [ ] **Step 4: Write real AI structure integration test gated by API key**

Append to `services/api/tests/test_ai_video_structure_service.py`:

```python
from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai
from app.video_understanding.schemas import ShotEvidence, VideoMetadata, VideoSignal, VideoShot


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires real AI provider")
def test_decompose_video_structure_with_ai_returns_segments_with_shot_evidence():
    signal = VideoSignal(
        metadata=VideoMetadata(duration=12, fps=30, width=1080, height=1920, format_name="mp4"),
        shot_count=3,
        shots=[
            VideoShot(index=1, start=0, end=3, duration=3, keyframe_time=1.5),
            VideoShot(index=2, start=3, end=9, duration=6, keyframe_time=6),
            VideoShot(index=3, start=9, end=12, duration=3, keyframe_time=10.5),
        ],
    )
    evidence = [
        ShotEvidence(
            shot_index=1,
            start=0,
            end=3,
            duration=3,
            transcript_text="熬夜脸很垮？",
            visual_summary="人物近景，大标题字幕",
            packaging_signals=["大标题"],
        ),
        ShotEvidence(
            shot_index=2,
            start=3,
            end=9,
            duration=6,
            transcript_text="上脸清爽，第二天状态好很多。",
            visual_summary="产品特写和使用过程",
            packaging_signals=["卖点字幕"],
        ),
        ShotEvidence(
            shot_index=3,
            start=9,
            end=12,
            duration=3,
            transcript_text="现在下单还有优惠。",
            visual_summary="结尾停留，优惠信息字幕",
            packaging_signals=["CTA字幕"],
        ),
    ]

    analysis = decompose_video_structure_with_ai(
        title="护肤样例",
        signal=signal,
        evidence=evidence,
        transcript_summary="熬夜脸很垮？上脸清爽，第二天状态好很多。现在下单还有优惠。",
    )

    assert analysis.source == "ai"
    assert analysis.segments
    assert all(segment.shot_indices for segment in analysis.segments)
    assert analysis.rhythm_structure.summary
    assert analysis.packaging_structure.caption_density or analysis.packaging_structure.title_style
```

- [ ] **Step 5: Implement real AI structure call**

Create `services/api/app/video_understanding/ai_structure_service.py`:

```python
import json
import os

import httpx

from app.video_understanding.schemas import AIStructureAnalysis, ShotEvidence, VideoSignal


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def decompose_video_structure_with_ai(
    *,
    title: str,
    signal: VideoSignal,
    evidence: list[ShotEvidence],
    transcript_summary: str,
) -> AIStructureAnalysis:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for real AI video structure decomposition")
    model = os.getenv("REELSTRUCT_STRUCTURE_MODEL", "gpt-4.1-mini")
    prompt = _build_prompt(title, signal, evidence, transcript_summary)
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
    }
    response = httpx.post(
        OPENAI_RESPONSES_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    parsed = _extract_json(response.json())
    return AIStructureAnalysis.model_validate(parsed)


def _build_prompt(title: str, signal: VideoSignal, evidence: list[ShotEvidence], transcript_summary: str) -> str:
    input_payload = {
        "title": title,
        "video_signal": signal.model_dump(),
        "shot_evidence": [item.model_dump() for item in evidence],
        "transcript_summary": transcript_summary,
    }
    return (
        "你是短视频结构拆解专家。请基于真实视频证据拆解创作结构，不要按固定四段模板输出。\n"
        "要求：段落数量由证据决定；每段必须引用 shot_indices；每段必须说明 purpose、method、evidence、rhythm、packaging、required_asset、transferable_rule、non_transferable、confidence。\n"
        "输出严格 JSON，字段为 source, headline, segments, rhythm_structure, packaging_structure, confidence, warnings。\n"
        "source 必须是 ai。\n"
        f"输入证据：\n{json.dumps(input_payload, ensure_ascii=False)}"
    )


def _extract_json(payload: dict) -> dict:
    texts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(str(content.get("text") or ""))
    raw_text = "\n".join(texts).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json\n", "", 1)
    return json.loads(raw_text)
```

- [ ] **Step 6: Run tests**

Run without key:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_ai_video_structure_service.py -q
```

Expected: non-AI evidence test PASS, real AI tests SKIPPED.

Run with key:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY=$OPENAI_API_KEY PYTHONPATH=. .venv/bin/pytest tests/test_ai_video_structure_service.py -q
```

Expected: all tests PASS.

## Task 7: Adapt AI Structure To Existing TemplateStructure

**Files:**

- Create: `services/api/app/video_understanding/template_adapter.py`
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Add analysis source fields to models**

Modify `SampleAnalysisSummary` in `services/api/app/models.py`:

```python
class SampleAnalysisSummary(BaseModel):
    headline: str
    metrics: list[SampleAnalysisMetric] = Field(default_factory=list)
    narrative_beats: list[SampleAnalysisBeat] = Field(default_factory=list)
    packaging_signals: list[str] = Field(default_factory=list)
    source: Literal["rule", "ai", "fallback"] = "rule"
    confidence: float = 0
    warnings: list[str] = Field(default_factory=list)
```

Modify `StructureSlot`:

```python
class StructureSlot(BaseModel):
    ...
    evidence_shot_indices: list[int] = Field(default_factory=list)
    confidence: float = 0
```

- [ ] **Step 2: Write failing adapter test**

Append to `services/api/tests/test_structure_service.py`:

```python
from app.video_understanding.schemas import (
    AIPackagingStructure,
    AIRhythmStructure,
    AIStructureAnalysis,
    VideoStructureSegment,
)
from app.video_understanding.template_adapter import adapt_ai_structure_to_template


def test_adapt_ai_structure_to_template_preserves_segments_evidence_and_source():
    analysis = AIStructureAnalysis(
        headline="痛点种草型结构",
        segments=[
            VideoStructureSegment(
                id="seg_1",
                label="痛点 Hook",
                type="hook",
                start=0,
                end=2.8,
                shot_indices=[1, 2],
                purpose="用痛点吸引停留",
                method="痛点提问 + 大标题",
                evidence="第 1-2 个镜头出现痛点字幕",
                rhythm="快进入",
                packaging="大标题",
                required_asset="开头吸引镜头",
                transferable_rule="保留痛点提问",
                non_transferable="不复制原商品",
                confidence=0.86,
            )
        ],
        rhythm_structure=AIRhythmStructure(summary="前段快进入，中段密集。"),
        packaging_structure=AIPackagingStructure(caption_density="高", title_style="开头大标题"),
        confidence=0.84,
    )

    template = adapt_ai_structure_to_template("护肤样例", analysis)

    assert template.title == "护肤样例 的 AI 视频结构"
    assert template.script_pattern[0].id == "seg_1"
    assert template.script_pattern[0].label == "痛点 Hook"
    assert template.script_pattern[0].evidence_shot_indices == [1, 2]
    assert template.analysis_summary.source == "ai"
    assert template.analysis_summary.confidence == 0.84
    assert "字幕密度：高" in template.packaging_notes
```

- [ ] **Step 3: Implement adapter**

Create `services/api/app/video_understanding/template_adapter.py`:

```python
from app.models import (
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    StructureSlot,
    TemplateStructure,
)
from app.video_understanding.schemas import AIStructureAnalysis


def adapt_ai_structure_to_template(sample_title: str, analysis: AIStructureAnalysis) -> TemplateStructure:
    slots = [
        StructureSlot(
            id=segment.id,
            label=segment.label,
            start=round(segment.start, 1),
            duration=round(segment.end - segment.start, 1),
            purpose=segment.purpose,
            required_asset=segment.required_asset or _required_asset_for_type(segment.type),
            sample_evidence=segment.evidence,
            role=segment.type,
            method=segment.method,
            intent=segment.purpose,
            rhythm=segment.rhythm,
            transferable_rule=segment.transferable_rule,
            non_transferable=segment.non_transferable,
            packaging_intent=segment.packaging,
            evidence_shot_indices=segment.shot_indices,
            confidence=segment.confidence,
        )
        for segment in analysis.segments
    ]
    packaging_notes = _packaging_notes(analysis)
    return TemplateStructure(
        title=f"{sample_title} 的 AI 视频结构",
        script_pattern=slots,
        rhythm_summary=analysis.rhythm_structure.summary,
        packaging_notes=packaging_notes,
        analysis_summary=SampleAnalysisSummary(
            headline=analysis.headline,
            metrics=[
                SampleAnalysisMetric(label="拆解来源", value="AI 视频结构拆解"),
                SampleAnalysisMetric(label="置信度", value=f"{round(analysis.confidence * 100)}%"),
                SampleAnalysisMetric(label="结构段数", value=str(len(analysis.segments))),
            ],
            narrative_beats=[
                SampleAnalysisBeat(slot_id=segment.id, label=segment.label, evidence=segment.evidence)
                for segment in analysis.segments
            ],
            packaging_signals=packaging_notes,
            source="ai",
            confidence=analysis.confidence,
            warnings=analysis.warnings,
        ),
    )


def _packaging_notes(analysis: AIStructureAnalysis) -> list[str]:
    packaging = analysis.packaging_structure
    notes = [
        f"字幕密度：{packaging.caption_density}" if packaging.caption_density else "",
        f"标题风格：{packaging.title_style}" if packaging.title_style else "",
        f"转场风格：{packaging.transition_style}" if packaging.transition_style else "",
        f"封面风格：{packaging.cover_style}" if packaging.cover_style else "",
    ]
    return [item for item in notes if item]


def _required_asset_for_type(segment_type: str) -> str:
    asset_map = {
        "hook": "开头吸引镜头",
        "problem": "痛点呈现镜头",
        "selling_point": "商品特写镜头",
        "proof": "证明/背书镜头",
        "usage": "使用过程镜头",
        "tutorial": "使用过程镜头",
        "comparison": "对比镜头",
        "trust": "证明/背书镜头",
        "cta": "结尾 CTA 镜头",
    }
    return asset_map.get(segment_type, "结构支撑镜头")
```

- [ ] **Step 4: Run adapter test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_structure_service.py::test_adapt_ai_structure_to_template_preserves_segments_evidence_and_source -q
```

Expected: PASS.

## Task 8: Wire AI Structure Decomposition Into Preview And Demo Flow

**Files:**

- Create: `services/api/app/video_understanding/pipeline.py`
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/workflow_service.py`
- Test: `services/api/tests/test_workflow_service.py`

- [ ] **Step 1: Extend request model with uploaded sample path**

Modify `StructurePreviewRequest` in `services/api/app/models.py` to carry uploaded sample path and optional analysis mode:

```python
class StructurePreviewRequest(BaseModel):
    sample: SampleVideoInput
    content: NewContentInput
    sample_local_path: str = ""
    use_ai_structure: bool = True
    ...
```

The frontend should set `sample_local_path` from `SampleUploadResponse.local_path`.

- [ ] **Step 2: Create pipeline function**

Create `services/api/app/video_understanding/pipeline.py`:

```python
from pathlib import Path

from app.models import SampleVideoInput, TemplateStructure
from app.structure_service import extract_template_structure
from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai
from app.video_understanding.ai_vision_service import analyze_keyframe_visuals
from app.video_understanding.evidence_service import build_shot_evidence
from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.shot_detector import detect_video_signal
from app.video_understanding.template_adapter import adapt_ai_structure_to_template


def decompose_sample_video_structure(
    sample: SampleVideoInput,
    *,
    sample_local_path: str,
    keyframes_dir: Path,
) -> TemplateStructure:
    if not sample_local_path:
        fallback = extract_template_structure(sample)
        fallback.analysis_summary.source = "fallback"
        fallback.analysis_summary.warnings = ["缺少样例视频路径，无法执行 AI 视频结构拆解。"]
        return fallback
    video_path = Path(sample_local_path)
    signal = detect_video_signal(video_path)
    keyframes = extract_keyframes(
        video_path,
        signal.shots,
        output_dir=keyframes_dir / video_path.stem,
        public_prefix=f"/keyframes/{video_path.stem}",
    )
    visuals = analyze_keyframe_visuals(keyframes)
    evidence = build_shot_evidence(signal.shots, keyframes, visuals, sample.transcript_summary)
    analysis = decompose_video_structure_with_ai(
        title=sample.title,
        signal=signal,
        evidence=evidence,
        transcript_summary=sample.transcript_summary,
    )
    return adapt_ai_structure_to_template(sample.title, analysis)
```

- [ ] **Step 3: Wire preview service with explicit fallback label**

Modify `build_structure_preview` in `services/api/app/structure_service.py` signature:

```python
def build_structure_preview(
    sample: SampleVideoInput,
    content: NewContentInput,
    template_override: Optional[TemplateStructure] = None,
    ...,
    ai_template: Optional[TemplateStructure] = None,
) -> StructurePreviewResponse:
    template = (
        template_override.model_copy(deep=True)
        if template_override is not None
        else ai_template.model_copy(deep=True)
        if ai_template is not None
        else extract_template_structure(sample)
    )
```

Keep `extract_template_structure` as emergency fallback only.

- [ ] **Step 4: Wire API/workflow path**

Modify `workflow_service.create_demo_run` to build `ai_template` before calling `build_structure_preview` when `request.use_ai_structure` is true and `request.sample_local_path` is present. Use `KEYFRAMES_DIR` or pass a storage path from API context.

If real AI fails, produce fallback with `analysis_summary.source = "fallback"` and `warnings` containing the error text. The UI must display fallback, not “AI”.

- [ ] **Step 5: Write integration test for AI template injection without calling model**

Because real AI calls are tested separately, test that `build_structure_preview` uses a provided AI template:

```python
def test_build_structure_preview_uses_ai_template_when_provided():
    ai_template = TemplateStructure(
        title="AI 拆解模板",
        script_pattern=[
            StructureSlot(
                id="seg_1",
                label="AI Hook",
                start=0,
                duration=3,
                purpose="AI 判断的开头",
                required_asset="开头吸引镜头",
                sample_evidence="AI evidence shot 1",
                role="hook",
                method="AI method",
                intent="AI intent",
                rhythm="AI rhythm",
                transferable_rule="AI transferable",
                non_transferable="AI non transferable",
                packaging_intent="AI packaging",
                evidence_shot_indices=[1],
                confidence=0.9,
            )
        ],
        rhythm_summary="AI rhythm summary",
        packaging_notes=["AI packaging note"],
        analysis_summary=SampleAnalysisSummary(
            headline="AI headline",
            source="ai",
            confidence=0.9,
        ),
    )

    response = build_structure_preview(
        SampleVideoInput(title="样例", duration=10, shot_count=3),
        NewContentInput(topic="新内容", available_assets=["开头吸引镜头"]),
        ai_template=ai_template,
    )

    assert response.template.title == "AI 拆解模板"
    assert response.template.analysis_summary.source == "ai"
    assert response.template.script_pattern[0].id == "seg_1"
```

- [ ] **Step 6: Run flow tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_structure_service.py tests/test_workflow_service.py -q
```

Expected: PASS.

## Task 9: Frontend AI Decomposition Evidence Display

**Files:**

- Modify: `apps/web/src/app/ReelStructWorkspace.tsx`
- Modify: `apps/web/scripts/check-material-request-sheet.mjs`

- [ ] **Step 1: Extend frontend model types**

Modify `SampleAnalysisSummary` type inside `StructurePreviewResponse`:

```ts
analysis_summary: {
  headline: string
  metrics: Array<{ label: string; value: string; detail: string }>
  narrative_beats: Array<{ slot_id: string; label: string; evidence: string }>
  packaging_signals: string[]
  source: 'rule' | 'ai' | 'fallback'
  confidence: number
  warnings: string[]
}
```

Modify `StructureSlot`:

```ts
evidence_shot_indices: number[]
confidence: number
```

Modify run/preview requests to include:

```ts
sample_local_path: sampleUpload?.local_path || ''
use_ai_structure: true
```

- [ ] **Step 2: Add AI source panel**

In the sample analysis area, show:

```tsx
<div className="rounded-md border border-line bg-white p-3">
  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">结构拆解来源</p>
  <p className="mt-2 text-sm text-ink">
    {preview?.template.analysis_summary.source === 'ai' ? 'AI 视频结构拆解' : '基础兜底拆解'}
  </p>
  <p className="text-xs text-slate-500">
    置信度 {Math.round((preview?.template.analysis_summary.confidence || 0) * 100)}%
  </p>
</div>
```

In each slot card, add:

```tsx
<p><strong className="text-ink">证据镜头：</strong>{slot.evidence_shot_indices?.length ? `Shot ${slot.evidence_shot_indices.join(' / ')}` : '等待 AI 证据'}</p>
<p><strong className="text-ink">段落置信度：</strong>{slot.confidence ? `${Math.round(slot.confidence * 100)}%` : '未提供'}</p>
```

- [ ] **Step 3: Extend browser regression**

Modify `apps/web/scripts/check-material-request-sheet.mjs` to assert:

```js
if (!bodyTextAfterBatchRun.includes("结构拆解来源") || !bodyTextAfterBatchRun.includes("证据镜头")) {
  throw new Error("missing AI structure decomposition evidence display");
}
```

If CI/local regression does not have `OPENAI_API_KEY`, the assertion should accept fallback display:

```js
if (!bodyTextAfterBatchRun.includes("AI 视频结构拆解") && !bodyTextAfterBatchRun.includes("基础兜底拆解")) {
  throw new Error("missing decomposition source label");
}
```

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run build
```

Expected: PASS.

## Task 10: Export AI Decomposition Evidence

**Files:**

- Modify: `services/api/app/run_export_service.py`
- Test: `services/api/tests/test_workflow_service.py`

- [ ] **Step 1: Write failing export test**

Extend the export package test in `services/api/tests/test_workflow_service.py`:

```python
assert "ai-structure-analysis.txt" in names
ai_structure_text = archive.read("ai-structure-analysis.txt").decode("utf-8")
assert "结构拆解来源" in ai_structure_text
assert "证据镜头" in ai_structure_text
```

- [ ] **Step 2: Implement export text**

Modify `services/api/app/run_export_service.py`:

```python
def build_ai_structure_analysis_text(run: DemoRunResponse) -> str:
    summary = run.preview.template.analysis_summary
    lines = [
        "AI 视频结构拆解",
        "",
        f"结构拆解来源：{summary.source}",
        f"置信度：{round(summary.confidence * 100)}%",
        "",
    ]
    if summary.warnings:
        lines.extend(["Warnings:", *[f"- {item}" for item in summary.warnings], ""])
    for slot in run.preview.template.script_pattern:
        lines.extend(
            [
                f"{slot.label}（{slot.id}）",
                f"时间：{slot.start}s - {round(slot.start + slot.duration, 1)}s",
                f"证据镜头：{', '.join(str(item) for item in slot.evidence_shot_indices) or '未提供'}",
                f"手法：{slot.method}",
                f"依据：{slot.sample_evidence}",
                f"可迁移规则：{slot.transferable_rule}",
                f"不可复制：{slot.non_transferable}",
                "",
            ]
        )
    return "\n".join(lines).strip()
```

Add to `build_run_export_zip`:

```python
archive.writestr("ai-structure-analysis.txt", build_ai_structure_analysis_text(run))
```

- [ ] **Step 3: Run export tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_workflow_service.py -q
```

Expected: PASS.

## Task 11: Full Verification

**Files:**

- No new source files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/pytest tests/test_video_understanding_media.py tests/test_ai_video_structure_service.py tests/test_structure_service.py tests/test_workflow_service.py tests/test_media_api.py tests/test_fixture_asset_service.py -q
```

Expected without `OPENAI_API_KEY`: all non-AI tests PASS and real AI tests SKIPPED.

Run with real key before claiming AI completion:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY=$OPENAI_API_KEY PYTHONPATH=. .venv/bin/pytest tests/test_ai_video_structure_service.py -q
```

Expected: real AI vision and structure tests PASS.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run browser regression**

Start API:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Start frontend:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
REELSTRUCT_API_ORIGIN=http://127.0.0.1:8011 npm run dev -- --hostname 127.0.0.1 --port 3002
```

Run regression:

```bash
cd /Users/linkwind/Code/ReelStruct
/Users/linkwind/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node apps/web/scripts/check-material-request-sheet.mjs
```

Expected: `REQUEST_SHEET_OK=1`.

Stop both dev sessions after the regression. If `apps/web/next-env.d.ts` changes to `./.next/dev/types/routes.d.ts`, restore it to:

```ts
import "./.next/types/routes.d.ts";
```

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git diff --check
git status --short
```

Expected: `git diff --check` has no output. Status contains only intended feature files.

- [ ] **Step 5: Final grouped commit**

If prior stage commits were not made, create one grouped implementation commit:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app services/api/tests apps/web/src/app/ReelStructWorkspace.tsx apps/web/scripts/check-material-request-sheet.mjs
git commit -m "feat: decompose sample videos with ai structure analysis"
```

## Self-Review Checklist

- Spec coverage:
  - Real video metadata: Task 1 and Task 4.
  - Real shot detection: Task 2 and Task 4.
  - Real keyframe extraction: Task 3 and Task 4.
  - Real AI visual understanding: Task 5.
  - Real AI video structure decomposition: Task 6.
  - AI structure drives migration: Task 7 and Task 8.
  - Frontend visibility: Task 4 and Task 9.
  - Export evidence: Task 10.
  - Verification: Task 11.
- No rule-led structure decisions are introduced as a main path.
- The old fixed four-segment decomposition is retained only as explicit emergency fallback.
- Real AI completion cannot be claimed unless the `OPENAI_API_KEY` integration tests pass.
