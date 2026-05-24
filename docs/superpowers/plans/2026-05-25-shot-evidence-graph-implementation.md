# Shot Evidence Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next ReelStruct video structure decomposition layer around Shot Evidence Graph: reliable shot segmentation, multi-frame evidence, OCR/ASR alignment, shot understanding, shot relations, beat aggregation, and segment aggregation.

**Architecture:** Keep the current `VideoSignal -> AI template -> TemplateStructure -> transfer/render` contract working while adding a new intermediate `ShotEvidenceGraph`. Physical shot cutting stays algorithmic with PySceneDetect/FFmpeg fallback; AI only performs shot understanding, relation classification, beat grouping, and segment extraction from evidence. The final adapter converts graph-derived segments back into the existing `TemplateStructure` so current migration, material gaps, and rendering continue to work.

**Tech Stack:** FastAPI, Pydantic, pytest, FFmpeg/ffprobe, PySceneDetect, OpenAI-compatible Responses API, Next.js/React frontend.

---

## File Structure

- Modify `services/api/requirements.txt`: add `scenedetect` for PySceneDetect.
- Modify `services/api/app/video_understanding/schemas.py`: add `FrameEvidence`, `FrameOCRText`, `TranscriptSegment`, `ShotTextAlignment`, `ShotEvidenceNode`, `ShotRelation`, `CreativeBeat`, `EvidenceBackedSegment`, `ShotEvidenceGraph`, and validator helpers.
- Create `services/api/app/video_understanding/pyscenedetect_detector.py`: PySceneDetect wrapper returning normalized `VideoShot` values.
- Modify `services/api/app/video_understanding/shot_detector.py`: orchestrate PySceneDetect, FFmpeg, and uniform fallback; add shot normalization metadata.
- Modify `services/api/app/video_understanding/keyframe_service.py`: evolve from single keyframe extraction to multi-frame sampling while preserving the current `extract_keyframes()` compatibility wrapper.
- Create `services/api/app/video_understanding/transcript_alignment.py`: parse SRT/plain transcript segments and align them to shots by time overlap.
- Create `services/api/app/video_understanding/shot_evidence_graph.py`: combine shots, frames, OCR text, ASR text, shot understanding, relations, beats, and segments into one graph.
- Modify `services/api/app/video_understanding/ai_vision_service.py`: return OCR-aware frame/shot understanding instead of only one-frame visual summary.
- Create `services/api/app/video_understanding/ai_graph_service.py`: relation classification, beat aggregation, and segment aggregation prompts.
- Create `services/api/app/video_understanding/graph_validator.py`: validate shot references, ordering, coverage, overlap, and evidence references.
- Modify `services/api/app/video_understanding/template_adapter.py`: convert `EvidenceBackedSegment` to `TemplateStructure`.
- Modify `services/api/app/video_understanding/pipeline.py`: make graph pipeline the AI path, fallback to current behavior when graph building fails.
- Modify `services/api/app/models.py`: expose optional graph summary in sample/run responses without breaking existing fields.
- Modify `services/api/app/sample_service.py`: return normalized shot and frame evidence on upload.
- Modify `services/api/app/main.py`: preserve current endpoints; accept SRT transcript upload and route graph-driven AI decomposition.
- Create or modify tests under `services/api/tests/`: add coverage for detector selection, frame sampling, transcript alignment, graph schema, graph validation, AI graph parsing, adapter behavior, and API response compatibility.
- Modify frontend files:
  - `apps/web/src/hooks/useReelStruct.ts`: add graph fields to TypeScript response types.
  - `apps/web/src/components/Views/WorkspaceView.tsx`: derive shot evidence, relations, and graph segments.
  - Create `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`.
  - Create `apps/web/src/components/Workspace/ShotRelationPanel.tsx`.
  - Modify `apps/web/src/components/Workspace/WorkPanel.tsx`: add a "镜头证据" tab or section.
  - Modify `apps/web/scripts/check-workspace-shell.mjs`: verify graph evidence appears after upload/generation.

---

### Task 1: Add PySceneDetect Physical Shot Detection

**Files:**
- Modify: `services/api/requirements.txt`
- Create: `services/api/app/video_understanding/pyscenedetect_detector.py`
- Modify: `services/api/app/video_understanding/shot_detector.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write failing tests for PySceneDetect normalization**

Add tests to `services/api/tests/test_video_understanding_media.py`:

```python
from pathlib import Path

from app.video_understanding.pyscenedetect_detector import scenes_to_video_shots


def test_scenes_to_video_shots_normalizes_boundaries():
    shots = scenes_to_video_shots(
        scenes=[(0.0, 1.25), (1.25, 3.5), (3.5, 5.0)],
        duration=5.0,
    )

    assert [shot.index for shot in shots] == [1, 2, 3]
    assert [(shot.start, shot.end) for shot in shots] == [(0.0, 1.25), (1.25, 3.5), (3.5, 5.0)]
    assert [shot.keyframe_time for shot in shots] == [0.625, 2.375, 4.25]


def test_scenes_to_video_shots_discards_invalid_scenes():
    shots = scenes_to_video_shots(
        scenes=[(0.0, 0.02), (0.1, 1.0), (2.0, 1.5), (1.0, 3.0)],
        duration=3.0,
    )

    assert [(shot.start, shot.end) for shot in shots] == [(0.1, 1.0), (1.0, 3.0)]
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_scenes_to_video_shots_normalizes_boundaries tests/test_video_understanding_media.py::test_scenes_to_video_shots_discards_invalid_scenes -q
```

Expected: both tests fail with `ModuleNotFoundError` or missing `scenes_to_video_shots`.

- [ ] **Step 3: Add PySceneDetect dependency**

Append this dependency to `services/api/requirements.txt`:

```text
scenedetect>=0.6.4
```

- [ ] **Step 4: Create the PySceneDetect wrapper**

Create `services/api/app/video_understanding/pyscenedetect_detector.py`:

```python
from pathlib import Path
from typing import Iterable

from app.video_understanding.schemas import VideoShot

MIN_SHOT_DURATION_SECONDS = 0.05


def detect_shots_with_pyscenedetect(path: Path, *, detector: str = "adaptive") -> list[VideoShot]:
    try:
        from scenedetect import AdaptiveDetector, ContentDetector, detect
    except ImportError as exc:
        raise RuntimeError("PySceneDetect is not installed") from exc

    scene_detector = AdaptiveDetector() if detector == "adaptive" else ContentDetector()
    scenes = detect(str(path), scene_detector)
    scene_times = [
        (start.get_seconds(), end.get_seconds())
        for start, end in scenes
    ]
    duration = scene_times[-1][1] if scene_times else 0
    return scenes_to_video_shots(scene_times, duration=duration)


def scenes_to_video_shots(scenes: Iterable[tuple[float, float]], *, duration: float) -> list[VideoShot]:
    shots: list[VideoShot] = []
    for start, end in scenes:
        start = round(max(0.0, float(start)), 3)
        end = round(min(float(end), float(duration)), 3)
        shot_duration = round(end - start, 3)
        if shot_duration < MIN_SHOT_DURATION_SECONDS:
            continue
        shots.append(
            VideoShot(
                index=len(shots) + 1,
                start=start,
                end=end,
                duration=shot_duration,
                keyframe_time=round(start + shot_duration / 2, 3),
            )
        )
    return shots
```

- [ ] **Step 5: Run focused tests and verify they pass**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_scenes_to_video_shots_normalizes_boundaries tests/test_video_understanding_media.py::test_scenes_to_video_shots_discards_invalid_scenes -q
```

Expected: `2 passed`.

- [ ] **Step 6: Route `detect_video_signal()` through PySceneDetect first**

Modify `services/api/app/video_understanding/shot_detector.py`:

```python
from app.video_understanding.pyscenedetect_detector import detect_shots_with_pyscenedetect
```

Inside `detect_video_signal()`, before FFmpeg scene detection:

```python
    shots = []
    detection_method = "scene_detect"
    try:
        shots = detect_shots_with_pyscenedetect(path, detector="adaptive")
        detection_method = "pyscenedetect_adaptive"
    except RuntimeError:
        shots = []

    if not _is_usable_shot_list(shots, metadata.duration):
        try:
            shots = detect_shots_with_pyscenedetect(path, detector="content")
            detection_method = "pyscenedetect_content"
        except RuntimeError:
            shots = []

    if not _is_usable_shot_list(shots, metadata.duration):
        cuts = _detect_scene_cut_times(path, metadata.duration, threshold)
        if len(cuts) < 1 and metadata.duration > fallback_seconds * 2:
            shots = _build_uniform_shots(metadata.duration, fallback_seconds)
            detection_method = "uniform_fallback"
        else:
            shots = _shots_from_cuts(metadata.duration, cuts)
            detection_method = "ffmpeg_scene_detect"

    shots = normalize_shots(shots, duration=metadata.duration)
```

Add helper functions:

```python
def _is_usable_shot_list(shots: list[VideoShot], duration: float) -> bool:
    if not shots:
        return False
    if duration >= 12 and len(shots) < 3:
        return False
    if len(shots) > max(8, int(duration * 4)):
        return False
    return True


def normalize_shots(shots: list[VideoShot], *, duration: float, min_duration: float = 0.3) -> list[VideoShot]:
    if not shots:
        return _shots_from_boundaries([0.0, duration])

    merged: list[tuple[float, float]] = []
    for shot in shots:
        start = max(0.0, min(shot.start, duration))
        end = max(start, min(shot.end, duration))
        if not merged:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if end - start < min_duration:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return _shots_from_boundaries([merged[0][0], *[end for _start, end in merged]])
```

- [ ] **Step 7: Add detection method tests**

Add to `services/api/tests/test_video_understanding_media.py`:

```python
def test_detect_video_signal_uses_uniform_fallback_when_detectors_return_no_shots(monkeypatch, tmp_path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"video-bytes")

    class Metadata:
        duration = 15.0
        fps = 30.0
        width = 1280
        height = 720
        format_name = "mp4"

    monkeypatch.setattr("app.video_understanding.shot_detector.probe_video_metadata", lambda _path: Metadata())
    monkeypatch.setattr("app.video_understanding.shot_detector.detect_shots_with_pyscenedetect", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.video_understanding.shot_detector._detect_scene_cut_times", lambda *_args, **_kwargs: [])

    signal = detect_video_signal(video)

    assert signal.detection_method == "uniform_fallback"
    assert signal.shot_count == 5
```

- [ ] **Step 8: Run detector tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 9: Commit task**

```bash
git add services/api/requirements.txt services/api/app/video_understanding/pyscenedetect_detector.py services/api/app/video_understanding/shot_detector.py services/api/tests/test_video_understanding_media.py
git commit -m "feat: add pyscenedetect shot detection"
```

---

### Task 2: Add Multi-frame Evidence

**Files:**
- Modify: `services/api/app/video_understanding/schemas.py`
- Modify: `services/api/app/video_understanding/keyframe_service.py`
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write failing tests for frame sampling times**

Add to `services/api/tests/test_video_understanding_media.py`:

```python
from app.video_understanding.keyframe_service import frame_sample_times


def test_frame_sample_times_uses_middle_for_short_shot():
    assert frame_sample_times(start=0.0, end=1.0) == [("middle", 0.5)]


def test_frame_sample_times_uses_start_middle_end_for_medium_shot():
    assert frame_sample_times(start=2.0, end=5.0) == [
        ("start", 2.15),
        ("middle", 3.5),
        ("end", 4.85),
    ]


def test_frame_sample_times_uses_quarters_for_long_shot():
    assert frame_sample_times(start=10.0, end=18.0) == [
        ("start", 10.15),
        ("third", 12.667),
        ("two_thirds", 15.333),
        ("end", 17.85),
    ]
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_frame_sample_times_uses_middle_for_short_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_start_middle_end_for_medium_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_quarters_for_long_shot -q
```

Expected: tests fail because `frame_sample_times` does not exist.

- [ ] **Step 3: Add `FrameEvidence` schema**

In `services/api/app/video_understanding/schemas.py`, add:

```python
class FrameEvidence(BaseModel):
    shot_index: int = Field(gt=0)
    frame_index: int = Field(gt=0)
    time: float = Field(ge=0)
    role: Literal["start", "middle", "end", "third", "two_thirds"] = "middle"
    local_path: str = Field(min_length=1)
    public_url: str = Field(min_length=1)
```

- [ ] **Step 4: Implement frame sampling helpers**

In `services/api/app/video_understanding/keyframe_service.py`, add:

```python
from app.video_understanding.schemas import FrameEvidence, KeyframeEvidence, VideoShot


def frame_sample_times(*, start: float, end: float) -> list[tuple[str, float]]:
    duration = round(end - start, 3)
    if duration < 1.2:
        return [("middle", round(start + duration / 2, 3))]
    if duration < 4:
        return [
            ("start", round(start + 0.15, 3)),
            ("middle", round(start + duration / 2, 3)),
            ("end", round(end - 0.15, 3)),
        ]
    return [
        ("start", round(start + 0.15, 3)),
        ("third", round(start + duration / 3, 3)),
        ("two_thirds", round(start + duration * 2 / 3, 3)),
        ("end", round(end - 0.15, 3)),
    ]
```

- [ ] **Step 5: Add `extract_frame_evidence()`**

In `services/api/app/video_understanding/keyframe_service.py`, add a multi-frame extractor while preserving `extract_keyframes()`:

```python
def extract_frame_evidence(
    video_path: Path,
    shots: list[VideoShot],
    *,
    output_dir: Path,
    public_prefix: str,
) -> list[FrameEvidence]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[FrameEvidence] = []
    prefix = public_prefix.rstrip("/")

    for shot in shots:
        for frame_index, (role, frame_time) in enumerate(
            frame_sample_times(start=shot.start, end=shot.end),
            start=1,
        ):
            filename = f"shot_{shot.index:04d}_{frame_index:02d}_{role}_{int(frame_time * 1000):08d}.jpg"
            local_path = output_dir / filename
            if _extract_one_frame(video_path, frame_time, local_path):
                frames.append(
                    FrameEvidence(
                        shot_index=shot.index,
                        frame_index=frame_index,
                        time=frame_time,
                        role=role,
                        local_path=str(local_path),
                        public_url=f"{prefix}/{filename}" if prefix else f"/{filename}",
                    )
                )
    return frames


def _extract_one_frame(video_path: Path, frame_time: float, local_path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{frame_time:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(local_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("failed to extract frame video_path=%s time=%s reason=%s", video_path, frame_time, exc)
        return False
    if result.returncode != 0 or not local_path.is_file():
        logger.warning("failed to extract frame video_path=%s time=%s stderr=%s", video_path, frame_time, result.stderr)
        return False
    return True
```

- [ ] **Step 6: Keep backward compatibility for `extract_keyframes()`**

Modify `extract_keyframes()` to call `extract_frame_evidence()` and return the first frame per shot as `KeyframeEvidence`:

```python
def extract_keyframes(
    video_path: Path,
    shots: list[VideoShot],
    *,
    output_dir: Path,
    public_prefix: str,
) -> list[KeyframeEvidence]:
    frames = extract_frame_evidence(
        video_path,
        shots,
        output_dir=output_dir,
        public_prefix=public_prefix,
    )
    first_by_shot: dict[int, FrameEvidence] = {}
    for frame in frames:
        first_by_shot.setdefault(frame.shot_index, frame)
    return [
        KeyframeEvidence(
            shot_index=frame.shot_index,
            keyframe_time=frame.time,
            local_path=frame.local_path,
            public_url=frame.public_url,
        )
        for frame in first_by_shot.values()
    ]
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_frame_sample_times_uses_middle_for_short_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_start_middle_end_for_medium_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_quarters_for_long_shot -q
```

Expected: `3 passed`.

- [ ] **Step 8: Commit task**

```bash
git add services/api/app/video_understanding/schemas.py services/api/app/video_understanding/keyframe_service.py services/api/tests/test_video_understanding_media.py
git commit -m "feat: add multi-frame shot evidence"
```

---

### Task 3: Add OCR/ASR Text Alignment Models

**Files:**
- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/transcript_alignment.py`
- Test: `services/api/tests/test_transcript_alignment.py`

- [ ] **Step 1: Write alignment tests**

Create `services/api/tests/test_transcript_alignment.py`:

```python
from app.video_understanding.schemas import TranscriptSegment, VideoShot
from app.video_understanding.transcript_alignment import align_transcript_to_shots, parse_srt_segments


def test_parse_srt_segments_extracts_timestamps_and_text():
    raw = """1
00:00:01,000 --> 00:00:03,500
早上来不及吃饭？

2
00:00:03,500 --> 00:00:06,000
三分钟搞定早餐
"""

    segments = parse_srt_segments(raw)

    assert segments == [
        TranscriptSegment(start=1.0, end=3.5, text="早上来不及吃饭？"),
        TranscriptSegment(start=3.5, end=6.0, text="三分钟搞定早餐"),
    ]


def test_align_transcript_to_shots_uses_time_overlap():
    shots = [
        VideoShot(index=1, start=0.0, end=2.0, duration=2.0, keyframe_time=1.0),
        VideoShot(index=2, start=2.0, end=5.0, duration=3.0, keyframe_time=3.5),
    ]
    segments = [
        TranscriptSegment(start=1.0, end=3.0, text="早上来不及吃饭？"),
        TranscriptSegment(start=3.2, end=4.8, text="三分钟搞定早餐"),
    ]

    aligned = align_transcript_to_shots(shots, segments)

    assert [item.shot_index for item in aligned] == [1, 2, 2]
    assert aligned[0].overlap_ratio == 0.5
    assert aligned[1].overlap_ratio == 0.333
    assert aligned[2].text == "三分钟搞定早餐"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_transcript_alignment.py -q
```

Expected: fail because module and schemas do not exist.

- [ ] **Step 3: Add text schemas**

In `services/api/app/video_understanding/schemas.py`, add:

```python
class FrameOCRText(BaseModel):
    shot_index: int = Field(gt=0)
    frame_index: int = Field(gt=0)
    frame_time: float = Field(ge=0)
    text: str = ""
    position: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = ""

    @model_validator(mode="after")
    def validate_timing(self) -> "TranscriptSegment":
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class ShotTextAlignment(BaseModel):
    shot_index: int = Field(gt=0)
    text: str = ""
    source_start: float = Field(ge=0)
    source_end: float = Field(ge=0)
    overlap_ratio: float = Field(default=0, ge=0, le=1)
```

- [ ] **Step 4: Implement transcript alignment**

Create `services/api/app/video_understanding/transcript_alignment.py`:

```python
import re

from app.video_understanding.schemas import ShotTextAlignment, TranscriptSegment, VideoShot

_SRT_BLOCK_RE = re.compile(
    r"(?:\d+\s+)?(?P<start>\d\d:\d\d:\d\d,\d\d\d)\s+-->\s+(?P<end>\d\d:\d\d:\d\d,\d\d\d)\s+(?P<text>.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def parse_srt_segments(raw: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for match in _SRT_BLOCK_RE.finditer(raw.strip()):
        text = " ".join(line.strip() for line in match.group("text").splitlines() if line.strip())
        segments.append(
            TranscriptSegment(
                start=_parse_srt_time(match.group("start")),
                end=_parse_srt_time(match.group("end")),
                text=text,
            )
        )
    return segments


def align_transcript_to_shots(
    shots: list[VideoShot],
    segments: list[TranscriptSegment],
) -> list[ShotTextAlignment]:
    aligned: list[ShotTextAlignment] = []
    for shot in shots:
        for segment in segments:
            overlap = max(0.0, min(shot.end, segment.end) - max(shot.start, segment.start))
            if overlap <= 0:
                continue
            aligned.append(
                ShotTextAlignment(
                    shot_index=shot.index,
                    text=segment.text,
                    source_start=segment.start,
                    source_end=segment.end,
                    overlap_ratio=round(overlap / shot.duration, 3),
                )
            )
    return aligned


def _parse_srt_time(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return round(int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000, 3)
```

- [ ] **Step 5: Run alignment tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_transcript_alignment.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit task**

```bash
git add services/api/app/video_understanding/schemas.py services/api/app/video_understanding/transcript_alignment.py services/api/tests/test_transcript_alignment.py
git commit -m "feat: align transcript text to shots"
```

---

### Task 4: Build Shot Evidence Graph Schema and Validator

**Files:**
- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/shot_evidence_graph.py`
- Create: `services/api/app/video_understanding/graph_validator.py`
- Test: `services/api/tests/test_shot_evidence_graph.py`

- [ ] **Step 1: Write graph construction and validation tests**

Create `services/api/tests/test_shot_evidence_graph.py`:

```python
from app.video_understanding.graph_validator import validate_graph_segments
from app.video_understanding.schemas import (
    CreativeBeat,
    EvidenceBackedSegment,
    FrameEvidence,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotRelation,
    ShotUnderstanding,
    VideoShot,
)
from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph


def test_build_initial_shot_evidence_graph_groups_frames_by_shot():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    ]
    frames = [
        FrameEvidence(shot_index=1, frame_index=1, time=1, role="middle", local_path="/tmp/1.jpg", public_url="/k/1.jpg"),
        FrameEvidence(shot_index=2, frame_index=1, time=2.2, role="start", local_path="/tmp/2.jpg", public_url="/k/2.jpg"),
    ]

    graph = build_initial_shot_evidence_graph(shots=shots, frames=frames)

    assert [node.shot.index for node in graph.shots] == [1, 2]
    assert graph.shots[0].frames[0].public_url == "/k/1.jpg"
    assert graph.shots[1].frames[0].role == "start"


def test_validate_graph_segments_reports_missing_shot_reference():
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                frames=[],
                understanding=ShotUnderstanding(shot_index=1, visual_summary="产品出现"),
            )
        ],
        relations=[],
        beats=[
            CreativeBeat(beat_id="beat_1", label="Hook", shot_indices=[1], start=0, end=2, function="hook", reason="开场")
        ],
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="Hook",
                beat_ids=["beat_1"],
                shot_indices=[1, 2],
                start=0,
                end=3,
                purpose="吸引注意",
                method="痛点开场",
                evidence=["Shot 1 产品出现"],
                rhythm="快",
                packaging="大字幕",
                transferable_rule="先抛痛点",
                non_transferable="原商品",
                required_asset="痛点场景",
                confidence=0.7,
            )
        ],
    )

    warnings = validate_graph_segments(graph)

    assert warnings == ["segment seg_1 references missing shot 2"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_shot_evidence_graph.py -q
```

Expected: fail because graph schemas do not exist.

- [ ] **Step 3: Add graph schemas**

In `services/api/app/video_understanding/schemas.py`, add:

```python
class ShotUnderstanding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_index: int = Field(gt=0)
    visual_summary: str = ""
    text_summary: str = ""
    subject: str = ""
    scene: str = ""
    action: str = ""
    packaging_signals: list[str] = Field(default_factory=list)
    creative_function_hint: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ShotEvidenceNode(BaseModel):
    shot: VideoShot
    frames: list[FrameEvidence] = Field(default_factory=list)
    ocr_texts: list[FrameOCRText] = Field(default_factory=list)
    transcript_texts: list[ShotTextAlignment] = Field(default_factory=list)
    understanding: ShotUnderstanding = Field(default_factory=lambda: ShotUnderstanding(shot_index=1))


class ShotRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_shot: int = Field(gt=0)
    to_shot: int = Field(gt=0)
    relation_type: str = Field(min_length=1)
    relation_summary: str = ""
    rhythm_change: str = ""
    semantic_shift: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class CreativeBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    shot_indices: list[int] = Field(default_factory=list, min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    function: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    confidence: float = Field(default=0, ge=0, le=1)


class EvidenceBackedSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    beat_ids: list[str] = Field(default_factory=list)
    shot_indices: list[int] = Field(default_factory=list, min_length=1)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    purpose: str = Field(min_length=1)
    method: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list, min_length=1)
    rhythm: str = Field(min_length=1)
    packaging: str = Field(min_length=1)
    transferable_rule: str = Field(min_length=1)
    non_transferable: str = Field(min_length=1)
    required_asset: str = Field(min_length=1)
    confidence: float = Field(default=0, ge=0, le=1)


class ShotEvidenceGraph(BaseModel):
    shots: list[ShotEvidenceNode] = Field(default_factory=list)
    relations: list[ShotRelation] = Field(default_factory=list)
    beats: list[CreativeBeat] = Field(default_factory=list)
    segments: list[EvidenceBackedSegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Create graph builder**

Create `services/api/app/video_understanding/shot_evidence_graph.py`:

```python
from app.video_understanding.schemas import FrameEvidence, ShotEvidenceGraph, ShotEvidenceNode, ShotUnderstanding, VideoShot


def build_initial_shot_evidence_graph(
    *,
    shots: list[VideoShot],
    frames: list[FrameEvidence],
) -> ShotEvidenceGraph:
    frame_lookup: dict[int, list[FrameEvidence]] = {}
    for frame in frames:
        frame_lookup.setdefault(frame.shot_index, []).append(frame)

    return ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=shot,
                frames=frame_lookup.get(shot.index, []),
                understanding=ShotUnderstanding(shot_index=shot.index),
            )
            for shot in shots
        ]
    )
```

- [ ] **Step 5: Create graph validator**

Create `services/api/app/video_understanding/graph_validator.py`:

```python
from app.video_understanding.schemas import ShotEvidenceGraph


def validate_graph_segments(graph: ShotEvidenceGraph) -> list[str]:
    warnings: list[str] = []
    shot_ids = {node.shot.index for node in graph.shots}
    beat_ids = {beat.beat_id for beat in graph.beats}

    for segment in graph.segments:
        for shot_id in segment.shot_indices:
            if shot_id not in shot_ids:
                warnings.append(f"segment {segment.segment_id} references missing shot {shot_id}")
        for beat_id in segment.beat_ids:
            if beat_id not in beat_ids:
                warnings.append(f"segment {segment.segment_id} references missing beat {beat_id}")
        if segment.end <= segment.start:
            warnings.append(f"segment {segment.segment_id} has invalid time range")

    sorted_segments = sorted(graph.segments, key=lambda item: item.start)
    for previous, current in zip(sorted_segments, sorted_segments[1:]):
        if current.start < previous.end:
            warnings.append(f"segment {previous.segment_id} overlaps {current.segment_id}")

    return warnings
```

- [ ] **Step 6: Run graph tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_shot_evidence_graph.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit task**

```bash
git add services/api/app/video_understanding/schemas.py services/api/app/video_understanding/shot_evidence_graph.py services/api/app/video_understanding/graph_validator.py services/api/tests/test_shot_evidence_graph.py
git commit -m "feat: add shot evidence graph schema"
```

---

### Task 5: Add AI Graph Understanding and Aggregation

**Files:**
- Modify: `services/api/app/video_understanding/ai_vision_service.py`
- Create: `services/api/app/video_understanding/ai_graph_service.py`
- Modify: `services/api/app/video_understanding/shot_evidence_graph.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [ ] **Step 1: Write tests for graph AI JSON parsing**

Add to `services/api/tests/test_ai_video_structure_service.py`:

```python
def test_parse_graph_segments_accepts_valid_json():
    from app.video_understanding.ai_graph_service import parse_graph_segments

    payload = {
        "relations": [
            {
                "from_shot": 1,
                "to_shot": 2,
                "relation_type": "problem_to_solution",
                "relation_summary": "痛点后接解决方案",
                "rhythm_change": "faster",
                "semantic_shift": "pain -> solution",
                "confidence": 0.8,
            }
        ],
        "beats": [
            {
                "beat_id": "beat_1",
                "label": "痛点引出",
                "shot_indices": [1, 2],
                "start": 0,
                "end": 4,
                "function": "hook_setup",
                "reason": "两个镜头连续提出痛点和解决方案",
                "confidence": 0.81,
            }
        ],
        "segments": [
            {
                "segment_id": "seg_1",
                "label": "痛点 Hook",
                "beat_ids": ["beat_1"],
                "shot_indices": [1, 2],
                "start": 0,
                "end": 4,
                "purpose": "吸引注意",
                "method": "痛点加承诺",
                "evidence": ["Shot 1 提出痛点", "Shot 2 承接解决"],
                "rhythm": "快速进入",
                "packaging": "大标题",
                "transferable_rule": "先痛点再承诺",
                "non_transferable": "原商品",
                "required_asset": "痛点场景",
                "confidence": 0.82,
            }
        ],
        "warnings": [],
    }

    graph_parts = parse_graph_segments(payload)

    assert graph_parts.relations[0].relation_type == "problem_to_solution"
    assert graph_parts.beats[0].beat_id == "beat_1"
    assert graph_parts.segments[0].transferable_rule == "先痛点再承诺"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_ai_video_structure_service.py::test_parse_graph_segments_accepts_valid_json -q
```

Expected: fail because `ai_graph_service` does not exist.

- [ ] **Step 3: Add graph AI service**

Create `services/api/app/video_understanding/ai_graph_service.py`:

```python
import json
import os
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.video_understanding.ai_structure_service import _extract_output_text, _safe_response_detail
from app.video_understanding.openai_config import openai_responses_url
from app.video_understanding.schemas import CreativeBeat, EvidenceBackedSegment, ShotEvidenceGraph, ShotRelation

DEFAULT_GRAPH_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 90
_JSON_FENCE_RE = re.compile(r"^```\s*(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class GraphAggregationResult(BaseModel):
    relations: list[ShotRelation] = Field(default_factory=list)
    beats: list[CreativeBeat] = Field(default_factory=list)
    segments: list[EvidenceBackedSegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def aggregate_graph_structure_with_ai(graph: ShotEvidenceGraph) -> GraphAggregationResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for graph structure aggregation")

    model = os.getenv("REELSTRUCT_STRUCTURE_MODEL", DEFAULT_GRAPH_MODEL)
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": _build_graph_prompt(graph)}],
            }
        ],
    }

    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        try:
            response = client.post(
                openai_responses_url(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"OpenAI graph request failed with status={exc.response.status_code}: {_safe_response_detail(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI graph request failed: {exc}") from exc

    output_text = _extract_output_text(response.json())
    return parse_graph_segments(_parse_json_output(output_text))


def parse_graph_segments(payload: dict[str, Any]) -> GraphAggregationResult:
    return GraphAggregationResult.model_validate(payload)


def _parse_json_output(output_text: str) -> dict[str, Any]:
    text = output_text.strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group("body").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI graph output JSON must be an object")
    return parsed


def _build_graph_prompt(graph: ShotEvidenceGraph) -> str:
    return (
        "你是短视频结构拆解专家。请只基于 Shot Evidence Graph 输出镜头关系、beat 和可迁移 segment。\n"
        "不要跳过证据。每个 segment 的 evidence 必须引用 shot、OCR/ASR 或 relation。\n"
        "输出严格 JSON，顶层字段只包含 relations, beats, segments, warnings。\n"
        f"Shot Evidence Graph:\n{json.dumps(graph.model_dump(), ensure_ascii=False)}"
    )
```

- [ ] **Step 4: Run graph AI parse test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_ai_video_structure_service.py::test_parse_graph_segments_accepts_valid_json -q
```

Expected: `1 passed`.

- [ ] **Step 5: Add graph merge helper**

In `services/api/app/video_understanding/shot_evidence_graph.py`, add:

```python
from app.video_understanding.ai_graph_service import GraphAggregationResult


def apply_graph_aggregation(
    graph: ShotEvidenceGraph,
    aggregation: GraphAggregationResult,
) -> ShotEvidenceGraph:
    return graph.model_copy(
        update={
            "relations": aggregation.relations,
            "beats": aggregation.beats,
            "segments": aggregation.segments,
            "warnings": [*graph.warnings, *aggregation.warnings],
        }
    )
```

- [ ] **Step 6: Commit task**

```bash
git add services/api/app/video_understanding/ai_graph_service.py services/api/app/video_understanding/shot_evidence_graph.py services/api/tests/test_ai_video_structure_service.py
git commit -m "feat: aggregate shot evidence graph with ai"
```

---

### Task 6: Adapt Graph Segments Back to TemplateStructure

**Files:**
- Modify: `services/api/app/video_understanding/template_adapter.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write adapter test**

Add to `services/api/tests/test_structure_service.py`:

```python
def test_adapt_graph_segments_to_template_preserves_evidence():
    from app.video_understanding.schemas import EvidenceBackedSegment, ShotEvidenceGraph
    from app.video_understanding.template_adapter import adapt_graph_segments_to_template

    graph = ShotEvidenceGraph(
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="痛点 Hook",
                beat_ids=["beat_1"],
                shot_indices=[1, 2],
                start=0,
                end=4,
                purpose="提出痛点",
                method="痛点加结果承诺",
                evidence=["Shot 1 ASR 提出痛点", "Shot 2 OCR 给出承诺"],
                rhythm="快节奏开场",
                packaging="大标题字幕",
                transferable_rule="先痛点再承诺",
                non_transferable="原商品",
                required_asset="痛点场景",
                confidence=0.83,
            )
        ],
        warnings=["segment coverage is 80%"],
    )

    template = adapt_graph_segments_to_template("早餐样例", graph)

    slot = template.script_pattern[0]
    assert template.analysis_summary.source == "ai"
    assert template.analysis_summary.warnings == ["segment coverage is 80%"]
    assert slot.id == "seg_1"
    assert slot.evidence_shot_indices == [1, 2]
    assert slot.sample_evidence == "Shot 1 ASR 提出痛点；Shot 2 OCR 给出承诺"
    assert slot.transferable_rule == "先痛点再承诺"
```

- [ ] **Step 2: Run adapter test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_structure_service.py::test_adapt_graph_segments_to_template_preserves_evidence -q
```

Expected: fail because `adapt_graph_segments_to_template` does not exist.

- [ ] **Step 3: Implement adapter**

In `services/api/app/video_understanding/template_adapter.py`, add:

```python
from app.video_understanding.schemas import ShotEvidenceGraph


def adapt_graph_segments_to_template(sample_title: str, graph: ShotEvidenceGraph) -> TemplateStructure:
    slots = [
        StructureSlot(
            id=segment.segment_id,
            label=segment.label,
            start=round(segment.start, 1),
            duration=round(segment.end - segment.start, 1),
            purpose=segment.purpose,
            required_asset=segment.required_asset,
            sample_evidence="；".join(segment.evidence),
            role="segment",
            method=segment.method,
            intent=segment.purpose,
            rhythm=segment.rhythm,
            transferable_rule=segment.transferable_rule,
            non_transferable=segment.non_transferable,
            packaging_intent=segment.packaging,
            evidence_shot_indices=segment.shot_indices,
            confidence=segment.confidence,
        )
        for segment in graph.segments
    ]

    return TemplateStructure(
        title=f"{sample_title} 的 Shot Evidence Graph 可迁移结构",
        script_pattern=slots,
        rhythm_summary=_graph_rhythm_summary(graph),
        packaging_notes=_graph_packaging_notes(graph),
        analysis_summary=SampleAnalysisSummary(
            headline=f"{sample_title} Shot Evidence Graph 拆解",
            metrics=[
                SampleAnalysisMetric(label="来源", value="Shot Evidence Graph", detail="基于镜头、OCR、ASR、关系和 beat 聚合"),
                SampleAnalysisMetric(label="结构段", value=str(len(slots)), detail="由 evidence-backed segments 转换"),
            ],
            narrative_beats=[
                SampleAnalysisBeat(slot_id=slot.id, label=slot.label, evidence=slot.sample_evidence)
                for slot in slots
            ],
            packaging_signals=_graph_packaging_notes(graph),
            source="ai",
            confidence=_average_confidence(graph),
            warnings=graph.warnings,
        ),
    )


def _average_confidence(graph: ShotEvidenceGraph) -> float:
    if not graph.segments:
        return 0
    return round(sum(segment.confidence for segment in graph.segments) / len(graph.segments), 3)


def _graph_rhythm_summary(graph: ShotEvidenceGraph) -> str:
    if not graph.segments:
        return "暂无可用结构段。"
    return " / ".join(f"{segment.label}: {segment.rhythm}" for segment in graph.segments)


def _graph_packaging_notes(graph: ShotEvidenceGraph) -> list[str]:
    notes = []
    for segment in graph.segments:
        if segment.packaging and segment.packaging not in notes:
            notes.append(segment.packaging)
    return notes
```

- [ ] **Step 4: Run adapter test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_structure_service.py::test_adapt_graph_segments_to_template_preserves_evidence -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit task**

```bash
git add services/api/app/video_understanding/template_adapter.py services/api/tests/test_structure_service.py
git commit -m "feat: adapt graph segments to template"
```

---

### Task 7: Wire Graph Pipeline Behind Existing API

**Files:**
- Modify: `services/api/app/video_understanding/pipeline.py`
- Modify: `services/api/app/sample_service.py`
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_video_understanding_pipeline.py`
- Test: `services/api/tests/test_sample_api.py`

- [ ] **Step 1: Write pipeline orchestration test**

Add to `services/api/tests/test_video_understanding_pipeline.py`:

```python
def test_build_ai_structure_template_uses_graph_pipeline(monkeypatch, tmp_path):
    from app.models import SampleVideoInput
    from app.video_understanding.pipeline import build_ai_structure_template
    from app.video_understanding.schemas import (
        CreativeBeat,
        EvidenceBackedSegment,
        FrameEvidence,
        ShotEvidenceGraph,
        VideoMetadata,
        VideoShot,
        VideoSignal,
    )

    video = tmp_path / "sample.mp4"
    video.write_bytes(b"video")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=4, fps=30, width=1280, height=720, format_name="mp4"),
        shot_count=2,
        detection_method="pyscenedetect_adaptive",
        shots=[
            VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
            VideoShot(index=2, start=2, end=4, duration=2, keyframe_time=3),
        ],
    )
    frames = [
        FrameEvidence(shot_index=1, frame_index=1, time=1, role="middle", local_path="/tmp/1.jpg", public_url="/k/1.jpg"),
        FrameEvidence(shot_index=2, frame_index=1, time=3, role="middle", local_path="/tmp/2.jpg", public_url="/k/2.jpg"),
    ]
    graph = ShotEvidenceGraph(
        beats=[
            CreativeBeat(beat_id="beat_1", label="开场", shot_indices=[1, 2], start=0, end=4, function="hook", reason="连续开场")
        ],
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="痛点 Hook",
                beat_ids=["beat_1"],
                shot_indices=[1, 2],
                start=0,
                end=4,
                purpose="吸引注意",
                method="痛点开场",
                evidence=["Shot 1-2 开场"],
                rhythm="快",
                packaging="大标题",
                transferable_rule="先痛点",
                non_transferable="原商品",
                required_asset="痛点场景",
                confidence=0.8,
            )
        ],
    )

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", lambda _path: signal)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_frame_evidence", lambda *_args, **_kwargs: frames)
    monkeypatch.setattr("app.video_understanding.pipeline.build_graph_with_ai", lambda **_kwargs: graph)

    template = build_ai_structure_template(
        sample=SampleVideoInput(title="样例", duration=4, shot_count=2, transcript_summary=""),
        sample_local_path=str(video),
        keyframes_dir=tmp_path / "keyframes",
    )

    assert template.analysis_summary.source == "ai"
    assert template.script_pattern[0].id == "seg_1"
    assert template.script_pattern[0].evidence_shot_indices == [1, 2]
```

- [ ] **Step 2: Run pipeline test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_pipeline.py::test_build_ai_structure_template_uses_graph_pipeline -q
```

Expected: fail because graph pipeline is not wired.

- [ ] **Step 3: Add graph pipeline helper**

Modify `services/api/app/video_understanding/pipeline.py`:

```python
from app.video_understanding.ai_graph_service import aggregate_graph_structure_with_ai
from app.video_understanding.graph_validator import validate_graph_segments
from app.video_understanding.keyframe_service import extract_frame_evidence
from app.video_understanding.shot_evidence_graph import apply_graph_aggregation, build_initial_shot_evidence_graph
from app.video_understanding.template_adapter import adapt_graph_segments_to_template


def build_graph_with_ai(
    *,
    signal,
    frames,
    sample,
) -> ShotEvidenceGraph:
    graph = build_initial_shot_evidence_graph(shots=signal.shots, frames=frames)
    aggregation = aggregate_graph_structure_with_ai(graph)
    graph = apply_graph_aggregation(graph, aggregation)
    warnings = validate_graph_segments(graph)
    return graph.model_copy(update={"warnings": [*graph.warnings, *warnings]})
```

- [ ] **Step 4: Switch `build_ai_structure_template()` to graph adapter**

In `services/api/app/video_understanding/pipeline.py`, replace the old AI structure sequence with:

```python
    frames = extract_frame_evidence(
        video_path,
        signal.shots,
        output_dir=target_keyframes_dir,
        public_prefix=keyframes_public_prefix,
    )
    graph = build_graph_with_ai(signal=signal, frames=frames, sample=sample)
    return adapt_graph_segments_to_template(sample.title, graph)
```

Keep `build_fallback_structure_template()` unchanged.

- [ ] **Step 5: Run pipeline test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_pipeline.py::test_build_ai_structure_template_uses_graph_pipeline -q
```

Expected: `1 passed`.

- [ ] **Step 6: Run sample upload compatibility tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_sample_api.py tests/test_video_understanding_pipeline.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit task**

```bash
git add services/api/app/video_understanding/pipeline.py services/api/tests/test_video_understanding_pipeline.py
git commit -m "feat: wire shot evidence graph pipeline"
```

---

### Task 8: Add Frontend Shot Evidence Display and Smoke Checks

**Files:**
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`
- Create: `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`
- Create: `apps/web/src/components/Workspace/ShotRelationPanel.tsx`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: Add frontend view model types**

In `apps/web/src/hooks/useReelStruct.ts`, add response types:

```ts
type FrameEvidence = {
  shot_index: number
  frame_index: number
  time: number
  role: 'start' | 'middle' | 'end' | 'third' | 'two_thirds'
  public_url: string
}

type ShotUnderstanding = {
  shot_index: number
  visual_summary: string
  text_summary: string
  subject: string
  scene: string
  action: string
  packaging_signals: string[]
  creative_function_hint: string
  confidence: number
  warnings: string[]
}

type ShotEvidenceNode = {
  shot: VideoShot
  frames: FrameEvidence[]
  understanding: ShotUnderstanding
}

type ShotRelation = {
  from_shot: number
  to_shot: number
  relation_type: string
  relation_summary: string
  rhythm_change: string
  semantic_shift: string
  confidence: number
}
```

- [ ] **Step 2: Create `ShotEvidencePanel.tsx`**

Create `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`:

```tsx
import React from 'react'

export interface ShotEvidenceViewModel {
  shotIndex: number
  time: string
  frames: Array<{ role: string; time: number; publicUrl: string }>
  visualSummary: string
  textSummary: string
  functionHint: string
  confidence: number
}

export default function ShotEvidencePanel({ shots }: { shots: ShotEvidenceViewModel[] }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Shot evidence</p>
          <h3>镜头证据</h3>
        </div>
        <span className="status">{shots.length ? `${shots.length} shots` : '等待生成'}</span>
      </div>
      {shots.length ? (
        <div className="shot-evidence-list">
          {shots.map((shot) => (
            <section className="shot-evidence-item" key={shot.shotIndex}>
              <div className="shot-evidence-head">
                <strong>Shot {shot.shotIndex}</strong>
                <span>{shot.time}</span>
              </div>
              <div className="node-keyframes">
                {shot.frames.map((frame) => (
                  <figure key={`${shot.shotIndex}-${frame.role}-${frame.time}`}>
                    <img src={frame.publicUrl} alt={`Shot ${shot.shotIndex} ${frame.role}`} />
                    <figcaption>{frame.role} · {frame.time.toFixed(2)}s</figcaption>
                  </figure>
                ))}
              </div>
              <p>{shot.visualSummary || '等待镜头理解结果'}</p>
              {shot.textSummary ? <small>{shot.textSummary}</small> : null}
              {shot.functionHint ? <span className="status">{shot.functionHint}</span> : null}
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有镜头证据</strong>
          <span>上传并生成结构后，这里会展示每个 shot 的画面、文本和 AI 理解。</span>
        </div>
      )}
    </article>
  )
}
```

- [ ] **Step 3: Create `ShotRelationPanel.tsx`**

Create `apps/web/src/components/Workspace/ShotRelationPanel.tsx`:

```tsx
import React from 'react'

export interface ShotRelationViewModel {
  fromShot: number
  toShot: number
  relationType: string
  summary: string
  semanticShift: string
  confidence: number
}

export default function ShotRelationPanel({ relations }: { relations: ShotRelationViewModel[] }) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Shot relations</p>
          <h3>前后镜头关系</h3>
        </div>
        <span className="status">{relations.length ? `${relations.length} relations` : '等待生成'}</span>
      </div>
      {relations.length ? (
        <div className="transfer-list">
          {relations.map((relation) => (
            <section className="transfer-item" key={`${relation.fromShot}-${relation.toShot}`}>
              <div className="transfer-title">
                <strong>Shot {relation.fromShot} -> Shot {relation.toShot}</strong>
                <span>{relation.relationType}</span>
              </div>
              <p>{relation.summary}</p>
              {relation.semanticShift ? <small>{relation.semanticShift}</small> : null}
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有关系结果</strong>
          <span>AI 聚合结构后，这里会展示相邻镜头如何承接、对比或转折。</span>
        </div>
      )}
    </article>
  )
}
```

- [ ] **Step 4: Derive panel data in `WorkspaceView.tsx`**

Add view model derivation:

```tsx
const graph = run?.preview.shot_evidence_graph
const shotEvidenceItems = (graph?.shots || []).map((node) => ({
  shotIndex: node.shot.index,
  time: `${formatSeconds(node.shot.start)} - ${formatSeconds(node.shot.end)}`,
  frames: node.frames.map((frame) => ({ role: frame.role, time: frame.time, publicUrl: frame.public_url })),
  visualSummary: node.understanding.visual_summary,
  textSummary: node.understanding.text_summary,
  functionHint: node.understanding.creative_function_hint,
  confidence: node.understanding.confidence,
}))
```

- [ ] **Step 5: Add a "镜头证据" tab in `WorkPanel.tsx`**

Extend `WorkTab`:

```ts
type WorkTab = 'sample' | 'evidence' | 'structure' | 'materials' | 'output'
```

Add tab config:

```tsx
{ key: 'evidence', label: '镜头证据', meta: shotEvidence.length ? `${shotEvidence.length} shots` : '待生成' }
```

Render:

```tsx
{activeTab === 'evidence' ? (
  <div className="tab-panel">
    <ShotEvidencePanel shots={shotEvidence} />
    <ShotRelationPanel relations={shotRelations} />
  </div>
) : null}
```

- [ ] **Step 6: Add smoke checks**

Modify `apps/web/scripts/check-workspace-shell.mjs` to verify the tab exists:

```js
for (const tabLabel of ["样例解析", "镜头证据", "结构拆解", "素材补全", "结果验证"]) {
  if (!workspaceText.includes(tabLabel)) {
    throw new Error(`workspace tab is missing: ${tabLabel}`);
  }
}
```

- [ ] **Step 7: Run frontend checks**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run build
npm run typecheck
npm run check:workspace
```

Expected:

- `next build` succeeds.
- `tsc --noEmit` exits 0.
- `WORKSPACE_SHELL_OK=1`.

- [ ] **Step 8: Commit task**

```bash
git add apps/web/src/hooks/useReelStruct.ts apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/WorkPanel.tsx apps/web/src/components/Workspace/ShotEvidencePanel.tsx apps/web/src/components/Workspace/ShotRelationPanel.tsx apps/web/src/app/globals.css apps/web/scripts/check-workspace-shell.mjs
git commit -m "feat: show shot evidence graph in workspace"
```

---

## Final Verification

After all tasks are implemented, run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests -q
```

Expected: all deterministic backend tests pass; OpenAI integration tests that require a real key may skip when `OPENAI_API_KEY` is empty.

Then run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run build
npm run typecheck
npm run check:workspace
```

Expected: build and typecheck pass, and workspace smoke check prints `WORKSPACE_SHELL_OK=1`.

Finally, manually verify with a real sample video:

```bash
curl -sS -F "file=@/Users/linkwind/Downloads/3246165181.mov" http://127.0.0.1:8010/api/samples/upload
```

Expected: response includes real duration, shot count, and public media URLs. In the frontend, upload the same video and confirm the workspace shows sample analysis, shot evidence, relations, structure segments, material gaps, and result validation.

## Self-Review Notes

- Spec coverage: tasks cover PySceneDetect shot cutting, normalization, multi-frame sampling, OCR/ASR alignment data, shot graph schemas, AI relation/beat/segment aggregation, graph-to-template adapter, API pipeline wiring, and frontend evidence display.
- Scope: automatic ASR and production OCR quality are outside this implementation plan; the plan creates the time-aligned data model and graph path first.
- Compatibility: existing `TemplateStructure`, transfer plan, material gap, and render flow remain the downstream contract.
