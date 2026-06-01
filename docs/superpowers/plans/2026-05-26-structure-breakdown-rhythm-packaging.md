# Structure Breakdown Rhythm And Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade task 2 structure breakdown so rhythm structure and packaging structure are explicit, evidence-backed, and visible in the workspace.

**Architecture:** Extend `ShotEvidenceGraph` with structured rhythm and packaging fields. AI graph aggregation returns these fields, while the adapter derives fallback rhythm and packaging from shot timing, OCR, and packaging signals when AI fields are missing. The frontend reads analysis metrics and renders rhythm/packaging cards in the structure breakdown tab.

**Tech Stack:** FastAPI/Pydantic, Pytest, Next.js/React, TypeScript, CSS modules through global workspace styles.

---

### Task 1: Back-End Schema And Graph Aggregation

**Files:**
- Modify: `services/api/app/video_understanding/schemas.py`
- Modify: `services/api/app/video_understanding/ai_graph_service.py`
- Modify: `services/api/app/video_understanding/shot_evidence_graph.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [x] Add `GraphRhythmStructure`, `RhythmCurvePoint`, `SegmentRhythmNote`, `GraphPackagingStructure`, and `PackagingTimelineItem`.
- [x] Add `rhythm_structure` and `packaging_structure` to `ShotEvidenceGraph` and `GraphAggregationResult`.
- [x] Normalize AI output for the new graph fields.
- [x] Preserve the fields when applying `GraphAggregationResult` to an existing graph.
- [x] Update the graph prompt so AI must output the new fields.

### Task 2: Adapter Fallbacks And Analysis Summary

**Files:**
- Modify: `services/api/app/video_understanding/template_adapter.py`
- Test: `services/api/tests/test_structure_service.py`

- [x] Use graph `rhythm_structure.summary` as `TemplateStructure.rhythm_summary`.
- [x] Convert graph packaging fields into `template.packaging_notes`.
- [x] Add `节奏结构` and `包装结构` metrics to `SampleAnalysisSummary`.
- [x] Derive fallback rhythm from shot durations when AI structure fields are missing.
- [x] Derive fallback packaging from OCR density, text positions, and `packaging_signals`.

### Task 3: Front-End Structure Breakdown Display

**Files:**
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`
- Modify: `apps/web/src/app/globals.css`

- [x] Extract rhythm and packaging metrics from `analysis_summary`.
- [x] Render dedicated rhythm and packaging cards in the structure breakdown panel.
- [x] Keep existing metric and packaging tag displays for compatibility.
- [x] Add responsive styling so cards collapse cleanly on mobile.

### Task 4: Verification

**Commands:**
- [ ] `cd services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_ai_video_structure_service.py tests/test_structure_service.py tests/test_video_understanding_pipeline.py -q`
- [ ] `cd apps/web && npm run typecheck`
- [ ] `cd apps/web && npm run check:workspace`
- [ ] `git diff --check`

**Expected Result:** Backend tests pass, frontend typecheck passes, workspace shell check passes, and no whitespace errors remain.
