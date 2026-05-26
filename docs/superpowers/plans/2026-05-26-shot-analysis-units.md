# Shot Analysis Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an analysis-unit layer so long videos keep raw shots for rhythm while AI understanding runs on grouped units.

**Architecture:** Preserve `VideoSignal.shots` as the raw edit timeline. Build `AnalysisUnit` records after OCR/ASR alignment and before AI understanding; each unit owns contiguous shot indices, representative frames, OCR texts, transcript texts, and a unit-level understanding that is propagated back to member shots for existing aggregation. The frontend shows units first and keeps raw shots inspectable inside each unit.

**Tech Stack:** FastAPI/Pydantic, pytest, Next.js/React, TypeScript.

---

### Task 1: Backend Analysis Unit Model And Grouping

**Files:**
- Modify: `services/api/app/video_understanding/schemas.py`
- Create: `services/api/app/video_understanding/analysis_unit_service.py`
- Test: `services/api/tests/test_analysis_unit_service.py`

- [ ] Add `AnalysisUnit` and `AnalysisUnitUnderstanding` Pydantic models.
- [ ] Build contiguous units from shot evidence nodes using a target unit duration and max shot count.
- [ ] Select representative frames per unit: start, middle, end, OCR-heavy frame.
- [ ] Add tests covering many short shots compressing into fewer units and preserving shot indices.

### Task 2: Unit-First AI Understanding

**Files:**
- Modify: `services/api/app/video_understanding/shot_understanding_service.py`
- Modify: `services/api/app/video_understanding/shot_evidence_graph.py`
- Test: `services/api/tests/test_video_understanding_pipeline.py`

- [ ] Add unit understanding request path.
- [ ] Call the vision model once per unit instead of once per raw shot.
- [ ] Propagate unit understanding into each member shot with unit context warnings.
- [ ] Preserve fallback behavior when unit understanding fails.

### Task 3: Pipeline And Frontend Exposure

**Files:**
- Modify: `services/api/app/video_understanding/pipeline.py`
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/ShotEvidencePanel.tsx`
- Modify: `apps/web/src/app/globals.css`

- [ ] Attach `analysis_units` to `ShotEvidenceGraph`.
- [ ] Map units into a frontend view model.
- [ ] Display unit cards first, with raw shots nested below.
- [ ] Keep existing shot fallback display when no graph units are present.

### Task 4: Verification

- [ ] Run backend targeted tests:
  `cd services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_analysis_unit_service.py tests/test_shot_evidence_graph.py tests/test_video_understanding_pipeline.py -q`
- [ ] Run frontend typecheck:
  `cd apps/web && npm run typecheck`
- [ ] Run workspace shell check:
  `cd apps/web && npm run check:workspace`
