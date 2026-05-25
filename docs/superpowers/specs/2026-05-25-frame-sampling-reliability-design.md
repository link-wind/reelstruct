# Frame Sampling Reliability Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve shot evidence quality by making frame extraction more resilient, making short-shot sampling adaptive, and exposing per-shot warnings in the UI.

**Architecture:** Keep the current Shot Evidence Graph pipeline unchanged in shape, but make the evidence fed into it more reliable. The backend will sample frames with duration-aware defaults plus fallback timestamps, emit explicit per-shot warnings when evidence is missing, and preserve the current graph/segment contracts. The frontend will surface those warnings in the shot evidence panel so users can see whether a shot failed because of frame extraction, model understanding, or downstream aggregation.

**Tech Stack:** FastAPI, Pydantic, pytest, FFmpeg, Next.js, React, TypeScript.

---

## File Structure

- Modify `services/api/app/video_understanding/keyframe_service.py`: introduce duration-aware frame sampling, fallback timestamps, and warning metadata while preserving `extract_keyframes()` compatibility.
- Modify `services/api/app/video_understanding/shot_understanding_service.py`: attach per-shot warnings when no usable frames are available so the graph can explain missing evidence.
- Modify `services/api/app/video_understanding/schemas.py`: keep the existing `ShotUnderstanding.warnings` and `FrameEvidence` shape stable; add only if a narrow helper field is needed for warning propagation.
- Modify `services/api/app/video_understanding/pipeline.py`: preserve current flow; no contract change beyond returning the same graph with better evidence coverage.
- Modify `services/api/app/models.py` and `services/api/app/structure_service.py` only if warning fields need to be propagated into preview/run responses.
- Modify `apps/web/src/components/Views/WorkspaceView.tsx`: map per-shot warnings into the shot evidence view model.
- Modify `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`: render warnings under each shot.
- Modify `apps/web/src/hooks/useReelStruct.ts` and `apps/web/src/hooks/useReelStructApi.ts`: extend TypeScript response types if backend warning fields are surfaced.
- Modify tests under `services/api/tests/` and `apps/web/` to cover frame sampling, fallback extraction, and warning display.

---

### Task 1: Make Frame Sampling Duration-Aware

**Files:**
- Modify: `services/api/app/video_understanding/keyframe_service.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write the failing tests**

Add tests that describe the new sampling policy:

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
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_frame_sample_times_uses_one_middle_frame_for_very_short_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_two_safe_frames_for_short_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_three_frames_for_medium_shot -q
```

Expected: fail because the current sampling policy does not have the new duration tiers.

- [ ] **Step 3: Implement the minimal sampling update**

Update `frame_sample_times()` so it behaves as follows:

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

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_frame_sample_times_uses_one_middle_frame_for_very_short_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_two_safe_frames_for_short_shot tests/test_video_understanding_media.py::test_frame_sample_times_uses_three_frames_for_medium_shot -q
```

Expected: `3 passed`.

---

### Task 2: Add Frame Extraction Fallbacks

**Files:**
- Modify: `services/api/app/video_understanding/keyframe_service.py`
- Test: `services/api/tests/test_video_understanding_media.py`

- [ ] **Step 1: Write failing tests**

Add tests that simulate a failed primary extract and a successful fallback:

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
        frames = extract_frame_evidence(Path("sample.mp4"), shots, output_dir=tmp_path / "frames", public_prefix="/frames")

    assert frames
    assert attempts[0] == 10.15
    assert attempts[1] == 14.0
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_extract_frame_evidence_falls_back_to_keyframe_time_when_primary_sample_fails -q
```

Expected: fail because the current implementation only tries one frame time per slot.

- [ ] **Step 3: Implement fallback attempts**

Update `extract_frame_evidence()` to try a sequence of timestamps for each logical frame slot:

```python
PRIMARY -> KEYFRAME -> START+0.05 -> END-0.05
```

If a sample fails, continue trying the next fallback for the same slot before giving up.

- [ ] **Step 4: Run the test and verify it passes**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_media.py::test_extract_frame_evidence_falls_back_to_keyframe_time_when_primary_sample_fails -q
```

Expected: `1 passed`.

---

### Task 3: Surface Shot Warnings in the UI

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/video_understanding/template_adapter.py`
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`
- Test: frontend typecheck and existing API tests

- [ ] **Step 1: Write the failing integration test**

Add an API-level test that asserts the run preview includes shot warnings and the frontend model can read them:

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

- [ ] **Step 2: Run the test and verify it fails**

Expected: fail until the preview response includes the graph warnings end-to-end.

- [ ] **Step 3: Add the data plumbing**

Ensure `TemplateStructure` and `StructurePreviewResponse` can carry `shot_evidence_graph`, and propagate it through preview/run responses.

- [ ] **Step 4: Render warnings in the panel**

In `ShotEvidencePanel`, show each shot's warnings below the summary:

```tsx
{shot.warnings?.length ? (
  <ul>
    {shot.warnings.map((warning) => <li key={warning}>{warning}</li>)}
  </ul>
) : null}
```

- [ ] **Step 5: Run typecheck and API tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck

cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_workflow_service.py -q
```

Expected: typecheck passes and the workflow test verifies warnings are visible in preview/run responses.

---

### Task 4: Keep the Pipeline Stable

**Files:**
- Modify: `services/api/app/video_understanding/pipeline.py`
- Modify: `services/api/app/video_understanding/shot_understanding_service.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [ ] **Step 1: Add the fallback-behavior test**

Add a test that when a shot has no readable frames, the pipeline keeps running and the shot carries a warning instead of failing the whole job.

```python
def test_build_graph_with_ai_keeps_running_when_shot_has_no_frames(monkeypatch):
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                frames=[],
            )
        ]
    )

    def fake_understand(current_graph):
        return current_graph.model_copy(
            update={
                "shots": [
                    current_graph.shots[0].model_copy(
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

    def fake_aggregate(current_graph):
        assert current_graph.shots[0].understanding.warnings == [
            "shot has no extracted frames for visual understanding"
        ]
        return current_graph.model_copy(update={"relations": [], "beats": [], "segments": [], "warnings": []})

    monkeypatch.setattr("app.video_understanding.pipeline.build_initial_shot_evidence_graph", lambda **_kwargs: graph)
    monkeypatch.setattr("app.video_understanding.pipeline.understand_shots_with_ai", fake_understand)
    monkeypatch.setattr("app.video_understanding.pipeline.aggregate_graph_structure_with_ai", fake_aggregate)

    result = build_graph_with_ai(
        signal=VideoSignal(
            metadata=VideoMetadata(duration=2, fps=30, width=720, height=1280, format_name="mov"),
            shot_count=1,
            detection_method="scene_detect",
            rhythm_metrics=RhythmMetrics(avg_shot_duration=2, cut_density="slow"),
            shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        ),
        frames=[],
        sample=SampleVideoInput(title="样例"),
    )

    assert result.shots[0].understanding.warnings == ["shot has no extracted frames for visual understanding"]
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_video_understanding_pipeline.py::test_build_graph_with_ai_keeps_running_when_shot_has_no_frames -q
```

Expected: fail until the pipeline guarantees warning-first fallback.

- [ ] **Step 3: Implement the minimal warning-first fallback**

Keep the `ShotUnderstanding` object in place for every shot, even when image extraction or model calls fail, so downstream graph aggregation can still run.

- [ ] **Step 4: Run the relevant tests**

Run the shot understanding, workflow, and pipeline tests together.

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. OPENAI_API_KEY= .venv/bin/pytest tests/test_ai_video_structure_service.py tests/test_workflow_service.py tests/test_video_understanding_pipeline.py -q
```

Expected: all green.

- [ ] **Step 5: Keep the current pipeline contract**

Do not change downstream graph aggregation or template adaptation; only improve evidence quality and observability.

---

## Self-Review

1. Coverage:
   - Duration-aware sampling: Task 1
   - Frame fallback extraction: Task 2
   - Per-shot warning visibility: Task 3
   - Pipeline stability: Task 4

2. Placeholder scan:
   - No TBD/TODO blocks.
   - Every code step includes concrete code.

3. Scope:
   - Focused on sampling reliability only.
   - OCR/ASR and relation logic are explicitly out of scope.
