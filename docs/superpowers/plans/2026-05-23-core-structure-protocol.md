# Core Structure Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade ReelStruct from simple slot segmentation to an explainable structure-migration protocol.

**Architecture:** Extend existing Pydantic models instead of introducing a separate service. `StructureSlot` will describe why a sample segment works, `TransferMapping` will describe how the method migrates, and the frontend will show a three-part "sample method -> target adaptation -> asset/package support" view.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, React, TypeScript.

---

### Task 1: Backend Protocol Fields

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] Add a failing test that asserts each slot includes `role`, `method`, `intent`, `rhythm`, `transferable_rule`, `non_transferable`, and `packaging_intent`.
- [ ] Add a failing test that asserts each mapping includes `source_method`, `target_adaptation`, `reasoning`, `asset_requirement`, `packaging_plan`, and `fallback_strategy`.
- [ ] Run the targeted tests and confirm they fail because fields are missing.
- [ ] Add model fields with defaults.
- [ ] Populate fields from deterministic slot and variant helpers.
- [ ] Run targeted tests and confirm they pass.

### Task 2: Frontend Three-Part Migration View

**Files:**
- Modify: `apps/web/src/app/ReelStructWorkspace.tsx`
- Test: `apps/web/scripts/check-material-request-sheet.mjs`

- [ ] Extend frontend types to match the backend protocol fields.
- [ ] Replace the structure preview card body with three visible columns: sample method, target migration, asset/package support.
- [ ] Keep existing editable textareas for sample evidence, target message, and asset strategy so current regeneration still works.
- [ ] Extend browser regression to assert the new explanatory labels are visible.
- [ ] Run browser regression after backend and frontend servers are running.

### Task 3: Documentation And Protocol Example

**Files:**
- Modify: `README.md`
- Modify: `docs/ai-architecture-and-delivery.md`
- Modify: `packages/protocol/structure-transfer.example.json`

- [ ] Update docs to describe the explainable structure protocol.
- [ ] Refresh protocol example so it includes the new slot and mapping fields.
- [ ] Run `git diff --check`.

### Task 4: Final Verification

**Files:**
- All modified files.

- [ ] Run backend tests.
- [ ] Run frontend build.
- [ ] Run browser regression.
- [ ] Commit the full change as one commit.
- [ ] Push `codex/bootstrap-foundation`.
