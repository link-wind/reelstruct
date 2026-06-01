# Slot Retrieval Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade material RAG from candidate listing to structure-slot retrieval planning, so every material gap explains required expression, matched evidence, remaining gap, and generation action.

**Architecture:** Keep the current lightweight RAG and supplement option system, but add a `SlotRetrievalPlan` object attached to each `MaterialGap`. The plan is built from `StructureSlot`, retrieved `MaterialRetrievalCandidate`s, and supplement options, then displayed in the material gap UI. This is a narrow P0 slice and does not replace the vector backend.

**Tech Stack:** FastAPI/Pydantic backend, existing ReelStruct structure service, React/TypeScript frontend, pytest, `tsc --noEmit`.

---

## File Structure

- Modify `services/api/app/models.py`: add `SlotRetrievalPlan` model and attach it to `MaterialGap`.
- Modify `services/api/app/structure_service.py`: build retrieval plans inside `build_material_gap()`.
- Modify `services/api/tests/test_structure_service.py`: add backend behavior tests for plan content with and without candidates.
- Modify `apps/web/src/hooks/useReelStruct.ts`: add frontend type for `retrieval_plan`.
- Modify `apps/web/src/app/ReelStructWorkspace.tsx`: add duplicate legacy type and display support.
- Modify `apps/web/src/components/Workspace/MaterialGapPanel.tsx`: show the retrieval plan in the material gap panel.
- Optionally modify `apps/web/src/app/globals.css`: add compact styles only if existing classes are insufficient.

---

### Task 1: Backend Slot Retrieval Plan Model

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write failing test for candidate-backed retrieval plan**

Add this test near the existing material gap tests in `services/api/tests/test_structure_service.py`:

```python
def test_material_gap_includes_slot_retrieval_plan_for_reusable_candidate():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水", "清爽不黏"],
            available_assets=["开头吸引镜头"],
            uploaded_assets=[
                UserSlotAsset(
                    slot_id="material_pool",
                    filename="detail-shot.mp4",
                    public_url="/materials/detail-shot.mp4",
                    analysis={
                        "duration": 5,
                        "shot_count": 1,
                        "evidence_chunks": [
                            {
                                "asset_id": "detail-shot.mp4",
                                "chunk_id": "chunk_detail",
                                "start": 1.2,
                                "end": 3.8,
                                "duration": 2.6,
                                "visual_summary": "清透保湿精华瓶身细节特写。",
                                "ocr_texts": ["快速补水"],
                                "packaging_signals": ["卖点字幕"],
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr", "packaging"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    plan = gap.retrieval_plan

    assert plan.slot_id == "selling_points"
    assert plan.required_expression
    assert "商品特写镜头" in plan.required_asset
    assert plan.best_candidate_id == "detail-shot.mp4::chunk_detail"
    assert plan.matched_evidence
    assert any("快速补水" in item for item in plan.matched_evidence)
    assert "裁切" in plan.generation_action
    assert plan.confidence >= 0.8
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_includes_slot_retrieval_plan_for_reusable_candidate -q
```

Expected: FAIL because `MaterialGap` has no `retrieval_plan` field.

- [ ] **Step 3: Add Pydantic model**

In `services/api/app/models.py`, add before `MaterialGap`:

```python
class SlotRetrievalPlan(BaseModel):
    slot_id: str = ""
    slot_label: str = ""
    required_asset: str = ""
    required_expression: str = ""
    query_summary: str = ""
    best_candidate_id: str = ""
    best_candidate_label: str = ""
    matched_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_method: str = ""
    generation_action: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
```

Then add to `MaterialGap`:

```python
retrieval_plan: SlotRetrievalPlan = Field(default_factory=SlotRetrievalPlan)
```

- [ ] **Step 4: Implement plan builder**

In `services/api/app/structure_service.py`, import `SlotRetrievalPlan` from `app.models` and add:

```python
def build_slot_retrieval_plan(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    supplement_options: list[MaterialSupplementOption],
) -> SlotRetrievalPlan:
    best = candidates[0] if candidates else None
    recommended = supplement_options[0] if supplement_options else None
    candidate_id = ""
    candidate_label = ""
    evidence: list[str] = []
    confidence = 0.2
    if best is not None:
        candidate_id = f"{best.asset_id}::{best.chunk_id}" if best.chunk_id else best.asset_id
        candidate_label = best.filename or best.asset_id
        evidence = best.evidence[:4] or [best.match_reason]
        confidence = min(0.95, max(0.35, best.match_score / 100))
    return SlotRetrievalPlan(
        slot_id=slot.id,
        slot_label=slot.label,
        required_asset=slot.required_asset,
        required_expression=_slot_required_expression(slot),
        query_summary=_slot_query_summary(slot),
        best_candidate_id=candidate_id,
        best_candidate_label=candidate_label,
        matched_evidence=evidence,
        missing_evidence=_slot_missing_evidence(slot, best),
        recommended_method=recommended.method if recommended else "补拍/AIGC",
        generation_action=recommended.action if recommended else f"补拍一段能直接支撑“{slot.required_asset}”的镜头。",
        confidence=round(confidence, 2),
    )
```

Also add helpers:

```python
def _slot_required_expression(slot: StructureSlot) -> str:
    parts = _dedupe([slot.purpose, slot.intent, slot.method, slot.transferable_rule])
    return "；".join(parts[:3]) or f"完成“{slot.label}”段落表达。"


def _slot_query_summary(slot: StructureSlot) -> str:
    parts = _dedupe([slot.label, slot.required_asset, slot.role, slot.packaging_intent])
    return " / ".join(parts[:4])


def _slot_missing_evidence(slot: StructureSlot, best: Optional[MaterialRetrievalCandidate]) -> list[str]:
    if best is None:
        return [f"缺少可直接支撑“{slot.required_asset}”的素材节点", "没有可追溯的 OCR、ASR 或视觉摘要命中"]
    missing: list[str] = []
    modalities = set(best.matched_modalities)
    if "visual" not in modalities:
        missing.append("缺少明确视觉摘要支撑")
    if "ocr" not in modalities and "asr" not in modalities:
        missing.append("缺少文字或语音卖点证据")
    if best.match_score < 80:
        missing.append("候选素材只能部分支撑，需要包装或字幕补足")
    return missing
```

Update `build_material_gap()` so it creates `retrieval_plan=build_slot_retrieval_plan(slot, candidates, supplement_options)`.

- [ ] **Step 5: Run backend test to verify pass**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_includes_slot_retrieval_plan_for_reusable_candidate -q
```

Expected: PASS.

---

### Task 2: Gap-backed Retrieval Plan

**Files:**
- Modify: `services/api/tests/test_structure_service.py`
- Modify: `services/api/app/structure_service.py` if test exposes gap wording issues

- [ ] **Step 1: Write failing test for no-candidate gap plan**

Add:

```python
def test_material_gap_retrieval_plan_explains_missing_evidence_without_candidates():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    plan = gap.retrieval_plan

    assert plan.slot_id == "selling_points"
    assert plan.best_candidate_id == ""
    assert plan.matched_evidence == []
    assert any("缺少" in item for item in plan.missing_evidence)
    assert plan.recommended_method in {"文案/字幕补全", "包装补全", "结构重排", "补拍/AIGC"}
    assert plan.generation_action
    assert plan.confidence <= 0.35
```

- [ ] **Step 2: Run test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_retrieval_plan_explains_missing_evidence_without_candidates -q
```

Expected: PASS if Task 1 implementation covers it. If it fails, adjust `_slot_missing_evidence()` and confidence only.

---

### Task 3: Frontend Display

**Files:**
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/app/ReelStructWorkspace.tsx`
- Modify: `apps/web/src/components/Workspace/MaterialGapPanel.tsx`

- [ ] **Step 1: Add frontend type**

In both `useReelStruct.ts` and `ReelStructWorkspace.tsx`, add:

```ts
type SlotRetrievalPlan = {
  slot_id: string
  slot_label: string
  required_asset: string
  required_expression: string
  query_summary: string
  best_candidate_id: string
  best_candidate_label: string
  matched_evidence: string[]
  missing_evidence: string[]
  recommended_method: string
  generation_action: string
  confidence: number
}
```

Add to `MaterialGap`:

```ts
retrieval_plan: SlotRetrievalPlan
```

- [ ] **Step 2: Add panel view model fields**

In `MaterialGapPanel.tsx`, add to `MaterialGapViewModel`:

```ts
retrievalPlan: {
  requiredExpression: string
  querySummary: string
  bestCandidateLabel: string
  matchedEvidence: string[]
  missingEvidence: string[]
  recommendedMethod: string
  generationAction: string
  confidence: number
}
```

- [ ] **Step 3: Map backend model to view model**

In `WorkspaceView.tsx`, where gaps are mapped to `MaterialGapViewModel`, map:

```ts
retrievalPlan: {
  requiredExpression: gap.retrieval_plan?.required_expression || '',
  querySummary: gap.retrieval_plan?.query_summary || '',
  bestCandidateLabel: gap.retrieval_plan?.best_candidate_label || '',
  matchedEvidence: gap.retrieval_plan?.matched_evidence || [],
  missingEvidence: gap.retrieval_plan?.missing_evidence || [],
  recommendedMethod: gap.retrieval_plan?.recommended_method || '',
  generationAction: gap.retrieval_plan?.generation_action || '',
  confidence: gap.retrieval_plan?.confidence || 0,
}
```

- [ ] **Step 4: Render compact plan block**

In `MaterialGapPanel.tsx`, under `.gap-rag-summary`, render:

```tsx
<div className="gap-retrieval-plan">
  <div className="gap-retrieval-row">
    <strong>槽位需求</strong>
    <span>{gap.retrievalPlan.requiredExpression || gap.fillStrategy}</span>
  </div>
  <div className="gap-retrieval-row">
    <strong>推荐动作</strong>
    <span>{gap.retrievalPlan.generationAction || gap.primarySupplement}</span>
  </div>
  {gap.retrievalPlan.bestCandidateLabel ? (
    <div className="gap-retrieval-row">
      <strong>命中素材</strong>
      <span>{gap.retrievalPlan.bestCandidateLabel} / 置信度 {Math.round(gap.retrievalPlan.confidence * 100)}%</span>
    </div>
  ) : null}
  {gap.retrievalPlan.missingEvidence.length ? (
    <ul className="gap-retrieval-missing">
      {gap.retrievalPlan.missingEvidence.slice(0, 3).map((item, index) => (
        <li key={`${gap.slotId}-missing-${index}`}>{item}</li>
      ))}
    </ul>
  ) : null}
</div>
```

- [ ] **Step 5: Add minimal CSS if needed**

If existing classes do not style the block well, add to `apps/web/src/app/globals.css`:

```css
.gap-retrieval-plan {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f8fafc;
}

.gap-retrieval-row {
  display: grid;
  gap: 4px;
  font-size: 12px;
  line-height: 1.5;
}

.gap-retrieval-row strong {
  color: #334155;
}

.gap-retrieval-row span,
.gap-retrieval-missing {
  color: #64748b;
}

.gap-retrieval-missing {
  margin: 0;
  padding-left: 16px;
  font-size: 12px;
  line-height: 1.6;
}
```

- [ ] **Step 6: Run frontend typecheck**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: exit 0.

---

### Task 4: Final Verification

**Files:**
- No code changes unless verification exposes a bug.

- [ ] **Step 1: Run focused backend tests**

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_workflow_service.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run material RAG tests**

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py tests/test_media_api.py tests/test_structure_service.py tests/test_workflow_service.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend typecheck**

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: exit 0.

- [ ] **Step 4: Run diff whitespace check**

```bash
cd /Users/linkwind/Code/ReelStruct
git diff --check
```

Expected: exit 0.

- [ ] **Step 5: Browser smoke check**

Open `http://127.0.0.1:3000/`, enter the workspace, click the material supplement tab, and verify the page contains:

- `素材缺口与补全`
- `素材库节点`
- `槽位需求` after preview data is generated

Expected: no runtime error overlay.
