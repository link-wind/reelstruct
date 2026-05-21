# ReelStruct Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development when executing larger follow-up tasks. This bootstrap plan creates a runnable foundation, not the full product.

**Goal:** Build the first runnable ReelStruct foundation with a frontend shell, backend health/analysis API, and shared structure-transfer protocol.

**Architecture:** Keep a small monorepo layout. `apps/web` owns the product UI, `services/api` owns FastAPI endpoints and deterministic P0 demo logic, and `packages/protocol` documents the cross-layer timeline/structure schema.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS, FastAPI, Pydantic, pytest.

---

## File Structure

- `apps/web`: Next.js app with the first ReelStruct workspace screen.
- `services/api`: FastAPI service with health and deterministic structure-transfer preview endpoints.
- `packages/protocol`: shared JSON schema examples for `TemplateStructure`, `TransferPlan`, `MaterialGap`, and `CompositionSpec`.
- `docs`: planning and architecture notes.

## Tasks

### Task 1: Frontend Workspace Shell

**Files:**
- Create `apps/web/package.json`
- Create `apps/web/next.config.mjs`
- Create `apps/web/tsconfig.json`
- Create `apps/web/tailwind.config.ts`
- Create `apps/web/postcss.config.js`
- Create `apps/web/src/app/layout.tsx`
- Create `apps/web/src/app/page.tsx`
- Create `apps/web/src/app/globals.css`

Steps:

- [ ] Add a minimal Next.js 14 app.
- [ ] Build a first screen with four workflow columns: sample, structure, transfer, output.
- [ ] Keep the UI focused on the structure migration task, not a generic landing page.
- [ ] Verify with `npm install` and `npm run build` inside `apps/web`.

### Task 2: Backend API Foundation

**Files:**
- Create `services/api/requirements.txt`
- Create `services/api/app/main.py`
- Create `services/api/app/models.py`
- Create `services/api/app/structure_service.py`
- Create `services/api/tests/test_structure_service.py`

Steps:

- [ ] Add FastAPI app with `/health`.
- [ ] Add deterministic `/api/structure/preview` endpoint.
- [ ] Model `TemplateStructure`, `TransferPlan`, `MaterialGap`, and `CompositionSpec`.
- [ ] Test that a sample request produces script slots, material gaps, and timeline tracks.
- [ ] Verify with `python -m pytest` inside `services/api`.

### Task 3: Shared Protocol Example

**Files:**
- Create `packages/protocol/structure-transfer.example.json`
- Update `README.md`

Steps:

- [ ] Add an example protocol payload matching backend response shape.
- [ ] Document local frontend/backend commands.
- [ ] Explain that this is a deterministic foundation before full video upload/rendering.

### Task 4: Final Verification

Steps:

- [ ] Run frontend build.
- [ ] Run backend tests.
- [ ] Commit changes.
- [ ] Push `codex/bootstrap-foundation`.
