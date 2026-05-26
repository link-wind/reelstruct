# Faster Whisper ASR Evidence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lightweight local ASR with faster-whisper as a first-class evidence producer for ReelStruct shot evidence graphs.

**Architecture:** ASR is added in the video understanding evidence layer, after shot detection and frame extraction and before graph construction. The service extracts audio from the sample video, transcribes it into timed `TranscriptSegment` rows, aligns those rows to shots as `ShotTextAlignment`, and stores them on each `ShotEvidenceNode`. Shot understanding and the frontend then consume the aligned transcript evidence without owning ASR model logic.

**Tech Stack:** FastAPI, Pydantic, pytest, FFmpeg, faster-whisper, Next.js, React, TypeScript.

---

## File Structure

- Create `services/api/app/video_understanding/asr_service.py`: local faster-whisper provider, audio extraction, ASR config, failure warnings, and segment normalization.
- Modify `services/api/app/video_understanding/shot_evidence_graph.py`: accept `transcript_texts` and attach them to `ShotEvidenceNode.transcript_texts`.
- Modify `services/api/app/video_understanding/pipeline.py`: run ASR after frame extraction, align transcript segments to shots, pass aligned text into graph construction, and keep ASR failures non-blocking.
- Modify `services/api/app/video_understanding/shot_understanding_service.py`: include aligned ASR text in the shot understanding prompt.
- Modify `services/api/requirements.txt`: add faster-whisper.
- Create `services/api/tests/test_asr_service.py`: focused ASR service tests with mocked FFmpeg and faster-whisper.
- Modify `services/api/tests/test_shot_evidence_graph.py`: verify transcript alignment attaches to the correct shot nodes.
- Modify `services/api/tests/test_video_understanding_pipeline.py`: verify pipeline ASR ordering, alignment, warning behavior, and graph consumption.
- Modify `services/api/tests/test_ai_video_structure_service.py`: verify shot understanding prompt includes transcript evidence.
- Modify `apps/web/src/components/Views/WorkspaceView.tsx`: map `transcript_texts` into the shot evidence view model.
- Modify `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`: render aligned ASR transcript text per shot.

---

### Task 1: Add Faster Whisper ASR Service

**Files:**
- Create: `services/api/app/video_understanding/asr_service.py`
- Modify: `services/api/requirements.txt`
- Test: `services/api/tests/test_asr_service.py`

- [ ] **Step 1: Add dependency**

Append this line to `services/api/requirements.txt`:

```txt
faster-whisper>=1.1.1
```

- [ ] **Step 2: Write failing config and disabled-mode tests**

Create `services/api/tests/test_asr_service.py`:

```python
from pathlib import Path

from app.video_understanding.asr_service import asr_is_enabled, load_asr_config, transcribe_video_with_asr


def test_asr_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("REELSTRUCT_ASR_ENABLED", raising=False)

    assert asr_is_enabled() is False


def test_asr_config_defaults_to_lightweight_chinese_cpu(monkeypatch):
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    monkeypatch.delenv("REELSTRUCT_ASR_MODEL", raising=False)
    monkeypatch.delenv("REELSTRUCT_ASR_LANGUAGE", raising=False)
    monkeypatch.delenv("REELSTRUCT_ASR_DEVICE", raising=False)
    monkeypatch.delenv("REELSTRUCT_ASR_COMPUTE_TYPE", raising=False)

    config = load_asr_config()

    assert config.enabled is True
    assert config.model_name == "small"
    assert config.language == "zh"
    assert config.device == "cpu"
    assert config.compute_type == "int8"


def test_transcribe_video_returns_empty_when_asr_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "false")

    result = transcribe_video_with_asr(Path("sample.mp4"), work_dir=tmp_path)

    assert result.segments == []
    assert result.warnings == []
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_asr_service.py -q
```

Expected: fail because `app.video_understanding.asr_service` does not exist.

- [ ] **Step 4: Implement config, result models, and disabled mode**

Create `services/api/app/video_understanding/asr_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from app.video_understanding.schemas import TranscriptSegment


@dataclass(frozen=True)
class ASRConfig:
    enabled: bool
    model_name: str
    language: str
    device: str
    compute_type: str


@dataclass(frozen=True)
class ASRResult:
    segments: list[TranscriptSegment]
    warnings: list[str]


def asr_is_enabled() -> bool:
    return os.getenv("REELSTRUCT_ASR_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def load_asr_config() -> ASRConfig:
    return ASRConfig(
        enabled=asr_is_enabled(),
        model_name=os.getenv("REELSTRUCT_ASR_MODEL", "small").strip() or "small",
        language=os.getenv("REELSTRUCT_ASR_LANGUAGE", "zh").strip() or "zh",
        device=os.getenv("REELSTRUCT_ASR_DEVICE", "cpu").strip() or "cpu",
        compute_type=os.getenv("REELSTRUCT_ASR_COMPUTE_TYPE", "int8").strip() or "int8",
    )


def transcribe_video_with_asr(video_path: Path, *, work_dir: Path) -> ASRResult:
    config = load_asr_config()
    if not config.enabled:
        return ASRResult(segments=[], warnings=[])
    raise NotImplementedError("faster-whisper ASR is not implemented yet")
```

- [ ] **Step 5: Run config tests and verify they pass**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_asr_service.py::test_asr_is_disabled_by_default \
  tests/test_asr_service.py::test_asr_config_defaults_to_lightweight_chinese_cpu \
  tests/test_asr_service.py::test_transcribe_video_returns_empty_when_asr_disabled \
  -q
```

Expected: `3 passed`.

- [ ] **Step 6: Write failing audio extraction test**

Add to `services/api/tests/test_asr_service.py`:

```python
from subprocess import CompletedProcess
from unittest.mock import patch


def test_transcribe_video_extracts_audio_with_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    commands = []

    def fake_run(args, **kwargs):
        commands.append(args)
        Path(args[-1]).write_bytes(b"wav")
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio_path, *, language, task, vad_filter):
            assert Path(audio_path).is_file()
            return [], object()

    with (
        patch("app.video_understanding.asr_service.subprocess.run", side_effect=fake_run),
        patch("app.video_understanding.asr_service.WhisperModel", FakeModel),
    ):
        result = transcribe_video_with_asr(video_path, work_dir=tmp_path / "asr")

    assert result.segments == []
    assert result.warnings == []
    command = commands[0]
    assert command[:4] == ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    assert "-vn" in command
    assert "-ar" in command
    assert "16000" in command
```

- [ ] **Step 7: Run the new test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_asr_service.py::test_transcribe_video_extracts_audio_with_ffmpeg -q
```

Expected: fail because enabled ASR still raises `NotImplementedError`.

- [ ] **Step 8: Implement FFmpeg audio extraction and lazy faster-whisper import**

Replace `services/api/app/video_understanding/asr_service.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Any

from app.video_understanding.schemas import TranscriptSegment

FFMPEG_TIMEOUT_SECONDS = 60
ASR_TIMEOUT_WARNING = "ASR 未完成：音频提取超时"

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ASRConfig:
    enabled: bool
    model_name: str
    language: str
    device: str
    compute_type: str


@dataclass(frozen=True)
class ASRResult:
    segments: list[TranscriptSegment]
    warnings: list[str]


def asr_is_enabled() -> bool:
    return os.getenv("REELSTRUCT_ASR_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def load_asr_config() -> ASRConfig:
    return ASRConfig(
        enabled=asr_is_enabled(),
        model_name=os.getenv("REELSTRUCT_ASR_MODEL", "small").strip() or "small",
        language=os.getenv("REELSTRUCT_ASR_LANGUAGE", "zh").strip() or "zh",
        device=os.getenv("REELSTRUCT_ASR_DEVICE", "cpu").strip() or "cpu",
        compute_type=os.getenv("REELSTRUCT_ASR_COMPUTE_TYPE", "int8").strip() or "int8",
    )


def transcribe_video_with_asr(video_path: Path, *, work_dir: Path) -> ASRResult:
    config = load_asr_config()
    if not config.enabled:
        return ASRResult(segments=[], warnings=[])

    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = work_dir / f"{video_path.stem or 'sample'}-asr.wav"
    warnings = _extract_audio(video_path, audio_path)
    if warnings:
        return ASRResult(segments=[], warnings=warnings)

    if WhisperModel is None:
        return ASRResult(segments=[], warnings=["ASR 未完成：faster-whisper 未安装"])

    model = WhisperModel(config.model_name, device=config.device, compute_type=config.compute_type)
    raw_segments, _info = model.transcribe(
        str(audio_path),
        language=config.language,
        task="transcribe",
        vad_filter=True,
    )
    return ASRResult(segments=_normalize_segments(raw_segments), warnings=[])


def _extract_audio(video_path: Path, audio_path: Path) -> list[str]:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-y",
                str(audio_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return ["ASR 未完成：ffmpeg executable not found"]
    except subprocess.TimeoutExpired:
        return [ASR_TIMEOUT_WARNING]

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        suffix = f"：{stderr}" if stderr else ""
        return [f"ASR 未完成：音频提取失败{suffix}"]
    if not audio_path.is_file():
        return ["ASR 未完成：音频文件未生成"]
    return []


def _normalize_segments(raw_segments: Any) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for item in raw_segments:
        text = str(getattr(item, "text", "")).strip()
        start = round(float(getattr(item, "start", 0)), 3)
        end = round(float(getattr(item, "end", 0)), 3)
        if not text or end <= start:
            continue
        segments.append(TranscriptSegment(start=start, end=end, text=text))
    return segments
```

- [ ] **Step 9: Run ASR service tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_asr_service.py -q
```

Expected: all tests in `test_asr_service.py` pass.

- [ ] **Step 10: Write segment normalization and failure tests**

Add to `services/api/tests/test_asr_service.py`:

```python
from types import SimpleNamespace


def test_transcribe_video_normalizes_faster_whisper_segments(monkeypatch, tmp_path):
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")

    def fake_run(args, **kwargs):
        Path(args[-1]).write_bytes(b"wav")
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    class FakeModel:
        def __init__(self, model_name, *, device, compute_type):
            assert model_name == "small"
            assert device == "cpu"
            assert compute_type == "int8"

        def transcribe(self, audio_path, *, language, task, vad_filter):
            assert language == "zh"
            assert task == "transcribe"
            assert vad_filter is True
            return [
                SimpleNamespace(start=0.12, end=1.56, text=" 早上来不及吃饭？ "),
                SimpleNamespace(start=1.56, end=1.56, text="invalid"),
                SimpleNamespace(start=2.0, end=3.0, text=""),
            ], object()

    with (
        patch("app.video_understanding.asr_service.subprocess.run", side_effect=fake_run),
        patch("app.video_understanding.asr_service.WhisperModel", FakeModel),
    ):
        result = transcribe_video_with_asr(video_path, work_dir=tmp_path / "asr")

    assert result.warnings == []
    assert result.segments == [TranscriptSegment(start=0.12, end=1.56, text="早上来不及吃饭？")]


def test_transcribe_video_returns_warning_when_audio_extraction_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("REELSTRUCT_ASR_ENABLED", "true")
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")

    with patch(
        "app.video_understanding.asr_service.subprocess.run",
        return_value=CompletedProcess(args=["ffmpeg"], returncode=1, stdout="", stderr="bad input"),
    ):
        result = transcribe_video_with_asr(video_path, work_dir=tmp_path / "asr")

    assert result.segments == []
    assert result.warnings == ["ASR 未完成：音频提取失败：bad input"]
```

- [ ] **Step 11: Run ASR service tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_asr_service.py -q
```

Expected: all tests pass.

- [ ] **Step 12: Commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/asr_service.py services/api/tests/test_asr_service.py services/api/requirements.txt
git commit -m "feat: add faster whisper asr service"
```

---

### Task 2: Attach ASR Transcript Evidence To Shot Graph

**Files:**
- Modify: `services/api/app/video_understanding/shot_evidence_graph.py`
- Test: `services/api/tests/test_shot_evidence_graph.py`

- [ ] **Step 1: Write failing graph attachment test**

Add to `services/api/tests/test_shot_evidence_graph.py`:

```python
from app.video_understanding.schemas import ShotTextAlignment


def test_build_initial_graph_attaches_transcript_texts_to_matching_shots():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=4, duration=2, keyframe_time=3),
    ]
    transcript_texts = [
        ShotTextAlignment(shot_index=2, text="三分钟搞定早餐", source_start=2.2, source_end=3.8, overlap_ratio=0.8)
    ]

    graph = build_initial_shot_evidence_graph(shots=shots, frames=[], transcript_texts=transcript_texts)

    assert graph.shots[0].transcript_texts == []
    assert graph.shots[1].transcript_texts == transcript_texts
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_shot_evidence_graph.py::test_build_initial_graph_attaches_transcript_texts_to_matching_shots -q
```

Expected: fail because `build_initial_shot_evidence_graph()` does not accept `transcript_texts`.

- [ ] **Step 3: Update graph builder signature and grouping**

Update `services/api/app/video_understanding/shot_evidence_graph.py`:

```python
from app.video_understanding.schemas import (
    FrameEvidence,
    GraphAggregationResult,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotTextAlignment,
    ShotUnderstanding,
    VideoShot,
)


def build_initial_shot_evidence_graph(
    *,
    shots: list[VideoShot],
    frames: list[FrameEvidence],
    transcript_texts: list[ShotTextAlignment] | None = None,
) -> ShotEvidenceGraph:
    frame_lookup: dict[int, list[FrameEvidence]] = {}
    for frame in frames:
        frame_lookup.setdefault(frame.shot_index, []).append(frame)

    transcript_lookup: dict[int, list[ShotTextAlignment]] = {}
    for item in transcript_texts or []:
        transcript_lookup.setdefault(item.shot_index, []).append(item)

    return ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=shot,
                frames=frame_lookup.get(shot.index, []),
                transcript_texts=transcript_lookup.get(shot.index, []),
                understanding=ShotUnderstanding(shot_index=shot.index),
            )
            for shot in shots
        ]
    )
```

Keep the existing `apply_graph_aggregation()` unchanged.

- [ ] **Step 4: Run graph tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_shot_evidence_graph.py -q
```

Expected: all graph tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/shot_evidence_graph.py services/api/tests/test_shot_evidence_graph.py
git commit -m "feat: attach transcript evidence to shot graph"
```

---

### Task 3: Wire ASR Into Video Understanding Pipeline

**Files:**
- Modify: `services/api/app/video_understanding/pipeline.py`
- Test: `services/api/tests/test_video_understanding_pipeline.py`

- [ ] **Step 1: Write failing pipeline ordering test**

Update `test_build_ai_structure_template_uses_graph_pipeline()` in `services/api/tests/test_video_understanding_pipeline.py` so it expects ASR to run between frame extraction and graph construction:

```python
from app.video_understanding.schemas import TranscriptSegment, ShotTextAlignment
```

Add these fakes inside the test:

```python
    asr_segments = [TranscriptSegment(start=0.5, end=1.8, text="早上来不及吃饭？")]

    def fake_transcribe(path, *, work_dir):
        calls.append(f"asr:{path.name}:{work_dir.name}")
        return type("FakeASRResult", (), {"segments": asr_segments, "warnings": []})()

    def fake_align(shots, segments):
        calls.append(f"align:{len(shots)}:{len(segments)}")
        return [
            ShotTextAlignment(
                shot_index=1,
                text="早上来不及吃饭？",
                source_start=0.5,
                source_end=1.8,
                overlap_ratio=0.65,
            )
        ]

    def fake_build_graph_with_ai(*, signal, frames, sample, transcript_texts):
        calls.append(f"graph:{signal.shot_count}:{len(frames)}:{len(transcript_texts)}:{sample.title}")
        return graph
```

Patch the functions:

```python
    monkeypatch.setattr("app.video_understanding.pipeline.transcribe_video_with_asr", fake_transcribe)
    monkeypatch.setattr("app.video_understanding.pipeline.align_transcript_to_shots", fake_align)
```

Update expected calls:

```python
    assert calls == [
        "detect:sample.mp4",
        "frames:2:/keyframes/test",
        "asr:sample.mp4:sample",
        "align:2:1",
        "graph:2:2:1:样例",
    ]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_video_understanding_pipeline.py::test_build_ai_structure_template_uses_graph_pipeline -q
```

Expected: fail because the pipeline does not import or call ASR yet.

- [ ] **Step 3: Update pipeline to run ASR and alignment**

Modify `services/api/app/video_understanding/pipeline.py` imports:

```python
from app.video_understanding.asr_service import transcribe_video_with_asr
from app.video_understanding.schemas import FrameEvidence, ShotEvidenceGraph, ShotTextAlignment, VideoSignal
from app.video_understanding.transcript_alignment import align_transcript_to_shots
```

Update `build_ai_structure_template()` after frame extraction:

```python
    asr_result = transcribe_video_with_asr(
        video_path,
        work_dir=target_keyframes_dir,
    )
    transcript_texts = align_transcript_to_shots(signal.shots, asr_result.segments)
    graph = build_graph_with_ai(
        signal=signal,
        frames=frames,
        transcript_texts=transcript_texts,
        sample=sample,
    )
    if asr_result.warnings:
        graph = graph.model_copy(update={"warnings": [*asr_result.warnings, *graph.warnings]})
```

Update `build_graph_with_ai()` signature and graph construction:

```python
def build_graph_with_ai(
    *,
    signal: VideoSignal,
    frames: list[FrameEvidence],
    transcript_texts: list[ShotTextAlignment] | None = None,
    sample: SampleVideoInput,
) -> ShotEvidenceGraph:
    graph = build_initial_shot_evidence_graph(
        shots=signal.shots,
        frames=frames,
        transcript_texts=transcript_texts or [],
    )
```

- [ ] **Step 4: Run pipeline test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_video_understanding_pipeline.py::test_build_ai_structure_template_uses_graph_pipeline -q
```

Expected: pass.

- [ ] **Step 5: Write ASR warning propagation test**

Add to `services/api/tests/test_video_understanding_pipeline.py`:

```python
def test_build_ai_structure_template_preserves_asr_warnings(monkeypatch, tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    signal = VideoSignal(
        metadata=VideoMetadata(duration=2, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=1,
        detection_method="scene_detect",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=2, cut_density="slow"),
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
    )
    graph = ShotEvidenceGraph(
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="开场",
                shot_indices=[1],
                start=0,
                end=2,
                confidence=0.8,
            )
        ]
    )

    monkeypatch.setattr("app.video_understanding.pipeline.detect_video_signal", lambda path: signal)
    monkeypatch.setattr("app.video_understanding.pipeline.extract_frame_evidence", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.video_understanding.pipeline.transcribe_video_with_asr",
        lambda path, *, work_dir: type("FakeASRResult", (), {"segments": [], "warnings": ["ASR 未完成：音频提取失败"]})(),
    )
    monkeypatch.setattr("app.video_understanding.pipeline.align_transcript_to_shots", lambda shots, segments: [])
    monkeypatch.setattr("app.video_understanding.pipeline.build_graph_with_ai", lambda **kwargs: graph)

    template = build_ai_structure_template(
        sample=SampleVideoInput(title="样例"),
        sample_local_path=str(video_path),
        keyframes_dir=tmp_path / "keyframes",
    )

    assert template.shot_evidence_graph.warnings[0] == "ASR 未完成：音频提取失败"
    assert template.analysis_summary.warnings[0] == "ASR 未完成：音频提取失败"
```

- [ ] **Step 6: Run pipeline tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_video_understanding_pipeline.py -q
```

Expected: all pipeline tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/pipeline.py services/api/tests/test_video_understanding_pipeline.py
git commit -m "feat: wire asr evidence into graph pipeline"
```

---

### Task 4: Feed ASR Text Into Shot Understanding

**Files:**
- Modify: `services/api/app/video_understanding/shot_understanding_service.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [ ] **Step 1: Write failing prompt test**

Add to `services/api/tests/test_ai_video_structure_service.py` near the shot understanding prompt tests:

```python
def test_shot_understanding_prompt_includes_transcript_texts():
    from app.video_understanding.schemas import ShotEvidenceNode, ShotTextAlignment, VideoShot
    from app.video_understanding.shot_understanding_service import _build_prompt

    node = ShotEvidenceNode(
        shot=VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
        transcript_texts=[
            ShotTextAlignment(
                shot_index=2,
                text="三分钟搞定早餐",
                source_start=2.1,
                source_end=4.2,
                overlap_ratio=0.7,
            )
        ],
    )

    prompt = _build_prompt(node)

    assert "transcript_texts" in prompt
    assert "三分钟搞定早餐" in prompt
    assert "source_start" in prompt
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_ai_video_structure_service.py::test_shot_understanding_prompt_includes_transcript_texts -q
```

Expected: fail because `_build_prompt()` currently only includes frame metadata.

- [ ] **Step 3: Update shot understanding prompt**

Modify `_build_prompt()` in `services/api/app/video_understanding/shot_understanding_service.py`:

```python
    transcript_notes = [
        {
            "text": item.text,
            "source_start": item.source_start,
            "source_end": item.source_end,
            "overlap_ratio": item.overlap_ratio,
        }
        for item in node.transcript_texts
        if item.text.strip()
    ]
```

Update the returned prompt text:

```python
        "你会看到同一个 shot 的多帧图片、时间信息和可选口播转写文本，请基于这些证据理解这个镜头。"
        "text_summary 优先综合画面中可见字幕和 transcript_texts 里的口播文本；没有文字证据就留空。"
        f"\nshot_index={node.shot.index}, start={node.shot.start}, end={node.shot.end}, "
        f"duration={node.shot.duration}, frames={json.dumps(frame_notes, ensure_ascii=False)}, "
        f"transcript_texts={json.dumps(transcript_notes, ensure_ascii=False)}"
```

- [ ] **Step 4: Run focused prompt test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_ai_video_structure_service.py::test_shot_understanding_prompt_includes_transcript_texts -q
```

Expected: pass.

- [ ] **Step 5: Run shot understanding tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_ai_video_structure_service.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/shot_understanding_service.py services/api/tests/test_ai_video_structure_service.py
git commit -m "feat: include asr text in shot understanding"
```

---

### Task 5: Show ASR Transcript Text In Shot Evidence UI

**Files:**
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`

- [ ] **Step 1: Extend shot evidence view model**

Update `ShotEvidenceViewModel` in `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`:

```ts
export interface ShotEvidenceViewModel {
  shotIndex: number
  time: string
  frames: Array<{ role: string; time: number; publicUrl: string }>
  transcriptTexts: Array<{ text: string; sourceStart: number; sourceEnd: number; overlapRatio: number }>
  visualSummary: string
  textSummary: string
  functionHint: string
  confidence: number
  warnings: string[]
}
```

- [ ] **Step 2: Map transcript texts from graph**

In `apps/web/src/components/Views/WorkspaceView.tsx`, update shot evidence mapping for graph-backed shots:

```ts
        transcriptTexts: (node.transcript_texts || []).map((item) => ({
          text: item.text,
          sourceStart: item.source_start,
          sourceEnd: item.source_end,
          overlapRatio: item.overlap_ratio,
        })),
```

In fallback sample-upload mapping, add:

```ts
        transcriptTexts: [],
```

If TypeScript does not know `transcript_texts`, add it to the local `ShotEvidenceNode` type in `apps/web/src/hooks/useReelStruct.ts`:

```ts
type ShotTextAlignment = {
  shot_index: number
  text: string
  source_start: number
  source_end: number
  overlap_ratio: number
}

type ShotEvidenceNode = {
  shot: VideoShot
  frames: FrameEvidence[]
  transcript_texts: ShotTextAlignment[]
  understanding: ShotUnderstanding
}
```

- [ ] **Step 3: Render transcript text in shot evidence panel**

In `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`, render transcript text after text summary:

```tsx
              {shot.transcriptTexts.length ? (
                <div className="shot-transcript-list">
                  <strong>口播文本</strong>
                  {shot.transcriptTexts.map((item) => (
                    <small key={`${shot.shotIndex}-${item.sourceStart}-${item.sourceEnd}`}>
                      {item.text}
                    </small>
                  ))}
                </div>
              ) : null}
```

- [ ] **Step 4: Add minimal CSS if needed**

If the panel needs spacing, add to `apps/web/src/app/globals.css`:

```css
.shot-transcript-list {
  display: grid;
  gap: var(--space-1);
}

.shot-transcript-list strong {
  font-size: var(--text-xs);
  color: var(--muted);
}
```

- [ ] **Step 5: Run frontend typecheck**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: `tsc --noEmit` exits `0`.

- [ ] **Step 6: Commit**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git add apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/ShotEvidencePanel.tsx apps/web/src/hooks/useReelStruct.ts apps/web/src/app/globals.css
git commit -m "feat: show asr transcripts in shot evidence"
```

---

## Final Verification

After all tasks are complete, run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_asr_service.py \
  tests/test_transcript_alignment.py \
  tests/test_shot_evidence_graph.py \
  tests/test_video_understanding_pipeline.py \
  tests/test_ai_video_structure_service.py \
  -q
```

Expected: all selected backend tests pass.

Then run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: `tsc --noEmit` exits `0`.

Finally run:

```bash
cd /Users/linkwind/Code/ReelStruct
git diff --check
```

Expected: no output and exit `0`.

## Scope Exclusions

- No realtime ASR.
- No speaker diarization.
- No word-level timestamps.
- No ASR result editor.
- No OCR implementation in this plan.
- No queue/worker split for long videos.
- No automatic model download UX beyond faster-whisper's normal behavior.

## Self-Review

- Spec coverage: covers faster-whisper service, FFmpeg audio extraction, ASR disabled mode, warning behavior, transcript alignment, graph attachment, shot understanding prompt consumption, and frontend display.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: `TranscriptSegment`, `ShotTextAlignment`, `transcript_texts`, `ASRResult`, and `build_initial_shot_evidence_graph()` names are consistent across tasks.
