# Frame Sampling Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve ReelStruct shot evidence quality by making frame extraction adaptive and fault-tolerant, and by exposing per-shot warnings in the workspace UI.

**Architecture:** Keep the current `detect_video_signal -> extract_frame_evidence -> understand_shots_with_ai -> aggregate_graph_structure_with_ai` pipeline intact. The changes stay local to frame sampling, per-shot fallback behavior, and preview/run response plumbing so downstream graph aggregation and rendering keep their current contracts.

**Tech Stack:** FastAPI, Pydantic, pytest, FFmpeg, Next.js, React, TypeScript.

---

## File Structure

- Modify `services/api/app/video_understanding/keyframe_service.py`: add duration-aware sampling tiers and fallback extraction attempts.
- Modify `services/api/app/video_understanding/shot_understanding_service.py`: preserve warning-first fallback when frame extraction or model understanding fails.
- Modify `services/api/app/video_understanding/pipeline.py`: keep graph-building stable while consuming better frame evidence.
- Modify `services/api/app/models.py`: ensure preview/run payloads can carry `shot_evidence_graph`.
- Modify `services/api/app/structure_service.py`: pass `shot_evidence_graph` through the preview response.
- Modify `services/api/app/video_understanding/template_adapter.py`: keep graph attached to AI-derived `TemplateStructure`.
- Modify `apps/web/src/hooks/useReelStruct.ts`: include per-shot warning fields in the local view model.
- Modify `apps/web/src/components/Views/WorkspaceView.tsx`: map `understanding.warnings` into `shotEvidence`.
- Modify `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`: render warnings under each shot.
- Modify `services/api/tests/test_video_understanding_media.py`: cover sampling tiers and extraction fallback.
- Modify `services/api/tests/test_ai_video_structure_service.py`: cover shot-understanding warning fallback and retry stability.
- Modify `services/api/tests/test_video_understanding_pipeline.py`: verify graph building keeps running when some shots have no frames.
- Modify `services/api/tests/test_workflow_service.py`: verify preview/run payloads include shot warnings.

---

### Task 1: Make Sampling Duration-Aware

**Files:**
- Modify: `services/api/app/video_understanding/keyframe_service.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `services/api/tests/test_video_understanding_media.py` near the existing `frame_sample_times` coverage:

```python
def test_frame_sample_times_uses_one_middle_frame_for_very_short_shot():
    assert frame_sample_times(start=0.0, end=0.7) == [("middle", 0.35)]


def test_frame_sample_times_uses_two_safe_frames_for_short_shot():
    assert frame_sample_times(start=2.0, end=3.2) == [
        ("middle", 2.6),
        ("safe_end", 3.05),
    ]


def test_frame_sample_times_uses_three_frames_for_medium_shot():
    assert frame_sample_times(start=5.0, end=8.5) == [
        ("start", 5.15),
        ("middle", 6.75),
        ("end", 8.35),
    ]
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_video_understanding_media.py::test_frame_sample_times_uses_one_middle_frame_for_very_short_shot \
  tests/test_video_understanding_media.py::test_frame_sample_times_uses_two_safe_frames_for_short_shot \
  tests/test_video_understanding_media.py::test_frame_sample_times_uses_three_frames_for_medium_shot \
  -q
```

Expected: fail because the current implementation still uses the old `<1.2 / <4 / >=4` split and has no `safe_end` role.

- [ ] **Step 3: Implement the minimal sampling update**

Update `frame_sample_times()` in `services/api/app/video_understanding/keyframe_service.py`:

```python
def frame_sample_times(*, start: float, end: float) -> list[tuple[str, float]]:
    duration = round(end - start, 3)
    if duration < 0.8:
        return [("middle", round(start + duration / 2, 3))]
    if duration < 2.0:
        return [
            ("middle", round(start + duration / 2, 3)),
            ("safe_end", round(end - 0.15, 3)),
        ]
    if duration < 4.0:
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

Also expand the `FrameEvidence.role` literal in `services/api/app/video_understanding/schemas.py` and the frontend TS equivalents to include `"safe_end"`.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_video_understanding_media.py::test_frame_sample_times_uses_one_middle_frame_for_very_short_shot \
  tests/test_video_understanding_media.py::test_frame_sample_times_uses_two_safe_frames_for_short_shot \
  tests/test_video_understanding_media.py::test_frame_sample_times_uses_three_frames_for_medium_shot \
  -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/keyframe_service.py services/api/app/video_understanding/schemas.py services/api/tests/test_video_understanding_media.py apps/web/src/hooks/useReelStruct.ts apps/web/src/hooks/useReelStructApi.ts
git commit -m "feat: add duration-aware frame sampling"
```

---

### Task 2: Add Extraction Fallback Attempts

**Files:**
- Modify: `services/api/app/video_understanding/keyframe_service.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write the failing test**

Add this test to `services/api/tests/test_video_understanding_media.py` near `test_extract_frame_evidence_writes_multiple_frames_with_roles_and_times`:

```python
def test_extract_frame_evidence_falls_back_to_keyframe_time_when_primary_sample_fails(tmp_path):
    shots = [VideoShot(index=1, start=10, end=18, duration=8, keyframe_time=14)]
    attempts = []

    def fake_run(args, **kwargs):
        attempts.append(float(args[args.index("-ss") + 1]))
        if len(attempts) == 1:
            return CompletedProcess(args=args, returncode=1, stdout="", stderr="bad input")
        Path(args[-1]).write_bytes(b"jpg")
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    with patch("app.video_understanding.keyframe_service.subprocess.run", side_effect=fake_run):
        frames = extract_frame_evidence(
            Path("sample.mp4"),
            shots,
            output_dir=tmp_path / "frames",
            public_prefix="/frames",
        )

    assert frames
    assert attempts[0] == 10.15
    assert attempts[1] == 14.0
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_video_understanding_media.py::test_extract_frame_evidence_falls_back_to_keyframe_time_when_primary_sample_fails \
  -q
```

Expected: fail because `extract_frame_evidence()` currently gives up after the first failed timestamp.

- [ ] **Step 3: Implement fallback attempts**

In `services/api/app/video_understanding/keyframe_service.py`, add a helper that returns fallback times per shot:

```python
def fallback_frame_times(shot: VideoShot, primary_time: float) -> list[float]:
    candidates = [
        primary_time,
        shot.keyframe_time,
        round(shot.start + 0.05, 3),
        round(shot.end - 0.05, 3),
    ]
    unique: list[float] = []
    for item in candidates:
        bounded = min(max(item, shot.start), shot.end)
        if bounded not in unique:
            unique.append(bounded)
    return unique
```

Then change `extract_frame_evidence()` to try each fallback time for the same logical slot before skipping it:

```python
for frame_index, (role, frame_time) in enumerate(...):
    for candidate_time in fallback_frame_times(shot, frame_time):
        filename = ...
        local_path = ...
        if _extract_one_frame(video_path, shot, candidate_time, local_path):
            frames.append(FrameEvidence(..., role=role, time=candidate_time, ...))
            break
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_video_understanding_media.py::test_extract_frame_evidence_falls_back_to_keyframe_time_when_primary_sample_fails \
  -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/keyframe_service.py services/api/tests/test_video_understanding_media.py
git commit -m "feat: add fallback frame extraction attempts"
```

---

### Task 3: Preserve Warning-First Shot Understanding

**Files:**
- Modify: `services/api/app/video_understanding/shot_understanding_service.py`
- Modify: `services/api/app/video_understanding/pipeline.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`
- Test: `services/api/tests/test_video_understanding_pipeline.py`

- [ ] **Step 1: Write the failing pipeline test**

Add this test to `services/api/tests/test_video_understanding_pipeline.py`:

```python
def test_build_graph_with_ai_keeps_running_when_shot_has_no_frames(monkeypatch):
    from app.video_understanding.pipeline import build_graph_with_ai

    signal = VideoSignal(
        metadata=VideoMetadata(duration=2, fps=30, width=720, height=1280, format_name="mov"),
        shot_count=1,
        detection_method="scene_detect",
        rhythm_metrics=RhythmMetrics(avg_shot_duration=2, cut_density="slow"),
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
    )

    def fake_understand(graph):
        return graph.model_copy(
            update={
                "shots": [
                    graph.shots[0].model_copy(
                        update={
                            "understanding": ShotUnderstanding(
                                shot_index=1,
                                warnings=["shot has no extracted frames for visual understanding"],
                            )
                        }
                    )
                ]
            }
        )

    def fake_aggregate(graph):
        assert graph.shots[0].understanding.warnings == [
            "shot has no extracted frames for visual understanding"
        ]
        return graph.model_construct(relations=[], beats=[], segments=[], warnings=[])

    monkeypatch.setattr("app.video_understanding.pipeline.understand_shots_with_ai", fake_understand)
    monkeypatch.setattr("app.video_understanding.pipeline.aggregate_graph_structure_with_ai", fake_aggregate)

    result = build_graph_with_ai(signal=signal, frames=[], sample=SampleVideoInput(title="样例"))

    assert result.shots[0].understanding.warnings == ["shot has no extracted frames for visual understanding"]
```

- [ ] **Step 2: Run the focused test and verify it fails if warning-first behavior regresses**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_video_understanding_pipeline.py::test_build_graph_with_ai_keeps_running_when_shot_has_no_frames \
  -q
```

Expected: fail if the warning-first fallback has been broken by the frame extraction changes.

- [ ] **Step 3: Keep the minimal fallback behavior**

Preserve this contract in `services/api/app/video_understanding/shot_understanding_service.py`:

```python
if not node.frames:
    return ShotUnderstanding(
        shot_index=node.shot.index,
        warnings=["shot has no extracted frames for visual understanding"],
    )
```

And keep the outer `try/except` that converts per-shot failures into `ShotUnderstanding(warnings=[...])` instead of failing the whole graph.

- [ ] **Step 4: Run the relevant backend tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_ai_video_structure_service.py \
  tests/test_video_understanding_pipeline.py \
  -q
```

Expected: all tests pass, including retry and warning behavior.

- [ ] **Step 5: Commit**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/video_understanding/shot_understanding_service.py services/api/app/video_understanding/pipeline.py services/api/tests/test_ai_video_structure_service.py services/api/tests/test_video_understanding_pipeline.py
git commit -m "feat: preserve warning-first shot understanding"
```

---

### Task 4: Surface Shot Warnings in Preview and Workspace

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/video_understanding/template_adapter.py`
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/hooks/useReelStructApi.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`
- Test: `services/api/tests/test_workflow_service.py`

- [ ] **Step 1: Write the failing API test**

Add this test to `services/api/tests/test_workflow_service.py`:

```python
def test_demo_run_returns_shot_warnings_in_preview(monkeypatch, tmp_path):
    client = TestClient(app)
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=3, duration=3, keyframe_time=1.5),
                understanding=ShotUnderstanding(
                    shot_index=1,
                    visual_summary="产品近景展示",
                    warnings=["shot understanding failed: frame missing"],
                ),
            )
        ]
    )
    ai_template = TemplateStructure(
        title="AI 拆解模板",
        script_pattern=[],
        rhythm_summary="AI 节奏",
        packaging_notes=[],
        analysis_summary=SampleAnalysisSummary(headline="AI 拆解", source="ai", confidence=0.88),
        shot_evidence_graph=graph,
    )

    monkeypatch.setattr("app.main.build_ai_or_fallback_structure_template", lambda *, sample, sample_local_path: ai_template)

    response = client.post(
        "/api/runs/demo",
        json={
            "sample": {"title": "样例", "duration": 20, "shot_count": 6},
            "sample_local_path": str(video_path),
            "use_ai_structure": True,
            "content": {"topic": "新品短视频", "available_assets": ["产品近景"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["preview"]["shot_evidence_graph"]["shots"][0]["understanding"]["warnings"] == [
        "shot understanding failed: frame missing"
    ]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_workflow_service.py::test_demo_run_returns_shot_warnings_in_preview \
  -q
```

Expected: fail until preview/run responses carry `shot_evidence_graph` end-to-end.

- [ ] **Step 3: Add the backend response plumbing**

Preserve the graph in these places:

```python
# services/api/app/models.py
class TemplateStructure(BaseModel):
    ...
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None

class StructurePreviewResponse(BaseModel):
    ...
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None
```

```python
# services/api/app/video_understanding/template_adapter.py
return TemplateStructure(
    ...,
    shot_evidence_graph=graph,
    analysis_summary=...,
)
```

```python
# services/api/app/structure_service.py
return StructurePreviewResponse(
    template=template,
    transfer_plan=transfer_plan,
    composition=composition,
    shot_evidence_graph=template.shot_evidence_graph,
)
```

- [ ] **Step 4: Render the warnings in the frontend**

Extend the local view model and panel:

```ts
// apps/web/src/components/Workspace/ShotEvidencePanel.tsx
export interface ShotEvidenceViewModel {
  ...
  warnings: string[]
}
```

```tsx
{shot.warnings.length ? (
  <ul className="shot-warning-list">
    {shot.warnings.map((warning) => (
      <li key={`${shot.shotIndex}-${warning}`}>{warning}</li>
    ))}
  </ul>
) : null}
```

And map it in `WorkspaceView.tsx`:

```ts
warnings: node.understanding?.warnings || [],
```

- [ ] **Step 5: Run typecheck and workflow tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck

cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_workflow_service.py -q
```

Expected: typecheck passes and workflow tests confirm warning visibility.

- [ ] **Step 6: Commit**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/models.py services/api/app/structure_service.py services/api/app/video_understanding/template_adapter.py apps/web/src/hooks/useReelStruct.ts apps/web/src/hooks/useReelStructApi.ts apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/ShotEvidencePanel.tsx services/api/tests/test_workflow_service.py
git commit -m "feat: show per-shot evidence warnings"
```

---

### Task 5: Final Verification

**Files:**
- Modify: none
- Test: existing suites

- [ ] **Step 1: Run backend reliability suites**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest \
  tests/test_video_understanding_media.py \
  tests/test_ai_video_structure_service.py \
  tests/test_video_understanding_pipeline.py \
  tests/test_workflow_service.py \
  -q
```

Expected: all green.

- [ ] **Step 2: Run backend full suite**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Run frontend static checks**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: pass with no TypeScript errors.

- [ ] **Step 4: Restart the backend**

Run:

```bash
pkill -f "uvicorn app.main:app --host 127.0.0.1 --port 8010" || true
cd /Users/linkwind/Code/ReelStruct/services/api
set -a
source .env
set +a
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Expected: `/health` returns `{"status":"ok"}` and the workspace UI can regenerate shot evidence with updated warnings.

---

## Self-Review

**Spec coverage:**
Task 1 covers short-shot adaptive sampling. Task 2 covers fallback extraction. Task 3 preserves per-shot warning-first behavior. Task 4 surfaces warnings in preview and the frontend. Task 5 verifies the end-to-end result.

**Placeholder scan:**
No `TBD`, `TODO`, or ellipsis placeholders remain inside implementation steps.

**Type consistency:**
`shot_evidence_graph`, `warnings`, and `safe_end` are defined consistently across backend Pydantic models and frontend TypeScript models.
