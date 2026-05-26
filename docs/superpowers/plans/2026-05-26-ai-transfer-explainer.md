# AI Transfer Explainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the transfer explanation panel from rule-composed text to AI-grounded per-slot migration reasoning.

**Architecture:** Keep the existing structure/template and material-gap pipeline intact. Add a new AI enrichment layer after `TransferPlan` is built; this layer returns structured explanations per slot and falls back to current rule fields when OpenAI is unavailable or fails.

**Tech Stack:** FastAPI, Pydantic v2, httpx, OpenAI Responses-compatible endpoint, Next.js/React TypeScript.

---

### Task 1: Add Structured Explanation Models

**Files:**
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] Add `TransferExplanation` with `slot_id`, `source_observation`, `transferable_principle`, `target_expression`, `asset_plan`, `gap_handling`, `reasoning`, `confidence`, and `warnings`.
- [ ] Add `explanation: TransferExplanation` to `TransferMapping` with a default empty explanation.
- [ ] Add tests confirming every mapping has an explanation object and rule fallback fills `target_expression`.

### Task 2: Build AI Transfer Explainer Service

**Files:**
- Create: `services/api/app/video_understanding/transfer_explainer_service.py`
- Test: `services/api/tests/test_transfer_explainer_service.py`

- [ ] Write tests for JSON parsing, field alias normalization, OpenAI request payload, and graceful failure.
- [ ] Implement `explain_transfer_with_ai(template, content, transfer_plan, graph, variant)`.
- [ ] Keep output grounded in slot evidence, shot/unit understanding, OCR/ASR, relations, gaps, and target brief.
- [ ] If `OPENAI_API_KEY` is absent, return the original transfer plan unchanged.

### Task 3: Wire Explainer Into Preview And Demo

**Files:**
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/workflow_service.py`
- Test: `services/api/tests/test_structure_service.py`
- Test: `services/api/tests/test_workflow_service.py`

- [ ] Add `use_ai_transfer_explanation` to `StructurePreviewRequest`, defaulting to true.
- [ ] After `build_transfer_plan`, call the AI explainer with `template.shot_evidence_graph`.
- [ ] Keep render composition using `mapping.target_message` so video output behavior remains stable in v1.
- [ ] Add tests proving AI explanation appears in preview/demo and fallback does not fail generation.

### Task 4: Surface AI Explanation In Frontend

**Files:**
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/hooks/useReelStructApi.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/TransferExplanationPanel.tsx`

- [ ] Add TypeScript types for `TransferExplanation`.
- [ ] Build `transferExplanations` from `mapping.explanation` first, then old fields as fallback.
- [ ] Show AI-generated `target_expression` under “新内容表达”.
- [ ] Show warnings/confidence so reviewers can see uncertainty.

### Task 5: Verify

**Commands:**
- `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_transfer_explainer_service.py tests/test_structure_service.py tests/test_workflow_service.py -q`
- `cd /Users/linkwind/Code/ReelStruct/apps/web && npm run typecheck && npm run check:workspace`
- `cd /Users/linkwind/Code/ReelStruct && git diff --check`
