# RAG v3 Slot Fill Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build structure-slot-driven material completion decisions so each material gap explains what matched, what is missing, and how to reuse/package/reorder/caption assets.

**Architecture:** Add a narrow RAG v3 layer on top of the existing material evidence chunks, vector retrieval, `SlotRetrievalPlan`, and supplement options. The new layer introduces `MaterialGraph`, `SlotQueryProfile`, and `SlotFillDecision`, then wires the decision into `MaterialGap`, transfer mapping, and the material supplement UI. AI rerank is introduced as a swappable interface with rule-based default behavior in this phase.

**Tech Stack:** FastAPI/Pydantic, existing ReelStruct services, pytest, React/TypeScript, Next.js, `tsc --noEmit`.

---

## File Structure

- Modify `services/api/app/models.py`: add `MaterialGraphNode`, `MaterialGraphEdge`, `MaterialGraph`, `SlotQueryProfile`, `SlotFillDecision`, and `MaterialGap.slot_fill_decision`.
- Create `services/api/app/material_graph_service.py`: build graph nodes/edges from `UserSlotAsset.analysis.evidence_chunks`.
- Modify `services/api/app/material_rag_service.py`: use `SlotQueryProfile`, `MaterialGraph`, and hybrid score breakdown when retrieving candidates.
- Modify `services/api/app/structure_service.py`: build slot query profiles, slot fill decisions, and use decisions in material gaps and transfer mappings.
- Modify `services/api/tests/test_material_vector_store.py`: test graph construction and hybrid score breakdown.
- Modify `services/api/tests/test_structure_service.py`: test slot fill decisions for reusable and missing material cases.
- Modify `apps/web/src/hooks/useReelStruct.ts`, `apps/web/src/hooks/useReelStructApi.ts`, and `apps/web/src/app/ReelStructWorkspace.tsx`: add frontend types for `slot_fill_decision`.
- Modify `apps/web/src/components/Views/WorkspaceView.tsx`: map backend decision to the material gap view model.
- Modify `apps/web/src/components/Workspace/MaterialGapPanel.tsx`: render the decision summary.
- Modify `apps/web/src/app/globals.css`: add compact decision UI styles.

---

### Task 1: Backend Models

**Files:**
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write failing model serialization test**

Add near existing material gap tests in `services/api/tests/test_structure_service.py`:

```python
def test_material_gap_serializes_empty_slot_fill_decision():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap_payload = response.transfer_plan.gaps[0].model_dump()

    assert "slot_fill_decision" in gap_payload
    assert gap_payload["slot_fill_decision"]["slot_id"]
    assert gap_payload["slot_fill_decision"]["actions"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_serializes_empty_slot_fill_decision -q
```

Expected: FAIL because `slot_fill_decision` is not present.

- [ ] **Step 3: Add Pydantic models**

In `services/api/app/models.py`, add after `MaterialEvidenceChunk`:

```python
class MaterialGraphNode(BaseModel):
    node_id: str
    node_type: Literal["asset", "chunk", "frame", "ocr_text", "asr_text", "packaging_signal", "tag", "slot_hint"]
    label: str = ""
    source_asset_id: str = ""
    chunk_id: str = ""
    start: float = 0
    end: float = 0
    text: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class MaterialGraphEdge(BaseModel):
    source: str
    target: str
    relation: Literal["contains", "has_evidence", "supports_slot", "needs_packaging"]
    weight: float = Field(default=1, ge=0, le=1)


class MaterialGraph(BaseModel):
    material_id: str = ""
    nodes: list[MaterialGraphNode] = Field(default_factory=list)
    edges: list[MaterialGraphEdge] = Field(default_factory=list)
```

Add before `MaterialGap`:

```python
class SlotQueryProfile(BaseModel):
    slot_id: str = ""
    required_asset: str = ""
    required_expression: str = ""
    semantic_terms: list[str] = Field(default_factory=list)
    visual_terms: list[str] = Field(default_factory=list)
    text_terms: list[str] = Field(default_factory=list)
    packaging_terms: list[str] = Field(default_factory=list)
    target_duration: float = 0


class SlotFillDecision(BaseModel):
    slot_id: str = ""
    decision_type: Literal["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"] = "caption_only"
    selected_asset_id: str = ""
    selected_chunk_id: str = ""
    start: float = 0
    end: float = 0
    confidence: float = Field(default=0, ge=0, le=1)
    why: str = ""
    missing: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    timeline_hint: str = ""
```

Then add to `MaterialGap`:

```python
slot_fill_decision: SlotFillDecision = Field(default_factory=SlotFillDecision)
```

- [ ] **Step 4: Implement temporary decision builder in `structure_service.py`**

In `services/api/app/structure_service.py`, add `SlotFillDecision` import and a simple builder used by `build_material_gap()`:

```python
def build_slot_fill_decision(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    supplement_options: list[MaterialSupplementOption],
) -> SlotFillDecision:
    best = candidates[0] if candidates else None
    recommended = supplement_options[0] if supplement_options else None
    if best is None:
        action = recommended.action if recommended else f"用字幕补足“{slot.required_asset}”的信息表达。"
        return SlotFillDecision(
            slot_id=slot.id,
            decision_type="caption_only" if recommended and recommended.method == "文案/字幕补全" else "shoot_or_aigc",
            confidence=0.2,
            why=f"素材库没有可直接支撑“{slot.required_asset}”的候选素材。",
            missing=[f"缺少“{slot.required_asset}”", "缺少可追溯的素材证据"],
            actions=[action],
            timeline_hint=f"在“{slot.label}”段使用字幕或补拍素材占位。",
        )
    action = recommended.action if recommended else best.reuse_strategy
    decision_type = "reuse_direct" if best.match_score >= 82 else "reuse_with_packaging"
    return SlotFillDecision(
        slot_id=slot.id,
        decision_type=decision_type,
        selected_asset_id=best.asset_id,
        selected_chunk_id=best.chunk_id,
        start=best.start,
        end=best.end,
        confidence=round(min(0.95, max(0.35, best.match_score / 100)), 2),
        why=best.match_reason,
        missing=_slot_missing_evidence(slot, best),
        actions=[action],
        timeline_hint=_slot_timeline_hint(slot, best),
    )
```

Add helper:

```python
def _slot_timeline_hint(slot: StructureSlot, candidate: MaterialRetrievalCandidate) -> str:
    if candidate.chunk_id and candidate.end > candidate.start:
        return f"放在“{slot.label}”段，优先使用 {candidate.start}s-{candidate.end}s。"
    return f"放在“{slot.label}”段，按 {round(slot.duration, 1)} 秒节奏重新裁切。"
```

Update `build_material_gap()` by inserting `slot_fill_decision` after `retrieval_plan` and passing it into `MaterialGap`:

```python
supplement_options = _material_supplement_options(slot, candidates, base_strategy)
retrieval_plan = build_slot_retrieval_plan(slot, candidates, supplement_options)
slot_fill_decision = build_slot_fill_decision(slot, candidates, supplement_options)

return MaterialGap(
    slot_id=slot.id,
    missing_asset=slot.required_asset,
    impact=f"{slot.label} 缺少直接画面支撑，表达会变弱。",
    fill_strategy=fill_strategy,
    suggested_asset_type=_suggested_asset_type_for_slot(slot.id),
    suggested_shots=_suggested_shots_for_slot(slot.id),
    pickup_checklist=_pickup_checklist_for_slot(slot.id),
    retrieval_status=retrieval_status,
    candidates=candidates,
    retrieval_reason=retrieval_reason,
    primary_supplement=supplement_options[0].action if supplement_options else fill_strategy,
    supplement_options=supplement_options,
    retrieval_plan=retrieval_plan,
    slot_fill_decision=slot_fill_decision,
)
```

- [ ] **Step 5: Run test to verify pass**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_serializes_empty_slot_fill_decision -q
```

Expected: PASS.

---

### Task 2: MaterialGraph Builder

**Files:**
- Create: `services/api/app/material_graph_service.py`
- Modify: `services/api/tests/test_material_vector_store.py`

- [ ] **Step 1: Write failing graph builder test**

Add to `services/api/tests/test_material_vector_store.py`:

```python
def test_build_material_graph_creates_nodes_and_edges_from_evidence_chunks():
    from app.material_graph_service import build_material_graph
    from app.models import UserSlotAsset

    asset = UserSlotAsset(
        slot_id="material_pool",
        filename="detail-shot.mp4",
        public_url="/materials/detail-shot.mp4",
        analysis={
            "evidence_chunks": [
                {
                    "asset_id": "detail-shot.mp4",
                    "chunk_id": "chunk_detail",
                    "start": 1.2,
                    "end": 3.8,
                    "visual_summary": "清透保湿精华瓶身细节特写。",
                    "ocr_texts": ["快速补水"],
                    "asr_texts": ["质地很清爽"],
                    "packaging_signals": ["卖点字幕"],
                    "subject_tags": ["产品", "瓶身"],
                    "action_tags": ["特写"],
                    "slot_hints": ["卖点展开"],
                    "modalities": ["visual", "ocr", "asr", "packaging"],
                    "embedding_text": "清透保湿精华 快速补水 质地清爽 产品 特写 卖点展开",
                }
            ]
        },
    )

    graph = build_material_graph([asset])
    node_types = {node.node_type for node in graph.nodes}
    relations = {edge.relation for edge in graph.edges}

    assert graph.material_id == "material_pool"
    assert {"asset", "chunk", "ocr_text", "asr_text", "packaging_signal", "tag", "slot_hint"}.issubset(node_types)
    assert {"contains", "has_evidence", "supports_slot"}.issubset(relations)
    assert any(node.text == "快速补水" for node in graph.nodes)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_build_material_graph_creates_nodes_and_edges_from_evidence_chunks -q
```

Expected: FAIL because `material_graph_service.py` does not exist.

- [ ] **Step 3: Create `material_graph_service.py`**

Create file:

```python
from __future__ import annotations

from app.models import MaterialGraph, MaterialGraphEdge, MaterialGraphNode, UserSlotAsset


def build_material_graph(assets: list[UserSlotAsset]) -> MaterialGraph:
    graph = MaterialGraph(material_id=_graph_material_id(assets))
    for asset in assets:
        asset_id = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.slot_id
        asset_node_id = f"asset::{asset_id}"
        graph.nodes.append(
            MaterialGraphNode(
                node_id=asset_node_id,
                node_type="asset",
                label=asset.filename or asset.slot_id,
                source_asset_id=asset_id,
                text=asset.analysis.visual_summary,
            )
        )
        for chunk in asset.analysis.evidence_chunks:
            chunk_id = chunk.chunk_id or "full"
            chunk_node_id = f"chunk::{asset_id}::{chunk_id}"
            graph.nodes.append(
                MaterialGraphNode(
                    node_id=chunk_node_id,
                    node_type="chunk",
                    label=chunk_id,
                    source_asset_id=asset_id,
                    chunk_id=chunk_id,
                    start=chunk.start,
                    end=chunk.end,
                    text=chunk.visual_summary or chunk.embedding_text,
                )
            )
            graph.edges.append(MaterialGraphEdge(source=asset_node_id, target=chunk_node_id, relation="contains"))
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "ocr_text", chunk.ocr_texts)
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "asr_text", chunk.asr_texts)
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "packaging_signal", chunk.packaging_signals)
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "tag", [*chunk.subject_tags, *chunk.action_tags])
            for index, slot_hint in enumerate(chunk.slot_hints):
                node_id = f"slot_hint::{asset_id}::{chunk_id}::{index}"
                graph.nodes.append(
                    MaterialGraphNode(
                        node_id=node_id,
                        node_type="slot_hint",
                        label=slot_hint,
                        source_asset_id=asset_id,
                        chunk_id=chunk_id,
                        text=slot_hint,
                    )
                )
                graph.edges.append(MaterialGraphEdge(source=chunk_node_id, target=node_id, relation="supports_slot"))
    return graph


def _append_text_nodes(
    graph: MaterialGraph,
    chunk_node_id: str,
    asset_id: str,
    chunk_id: str,
    node_type: str,
    values: list[str],
) -> None:
    for index, value in enumerate(values):
        if not value:
            continue
        node_id = f"{node_type}::{asset_id}::{chunk_id}::{index}"
        graph.nodes.append(
            MaterialGraphNode(
                node_id=node_id,
                node_type=node_type,
                label=value,
                source_asset_id=asset_id,
                chunk_id=chunk_id,
                text=value,
            )
        )
        graph.edges.append(MaterialGraphEdge(source=chunk_node_id, target=node_id, relation="has_evidence"))


def _graph_material_id(assets: list[UserSlotAsset]) -> str:
    if len(assets) == 1:
        return assets[0].slot_id
    return "material_graph"
```

- [ ] **Step 4: Run graph test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_build_material_graph_creates_nodes_and_edges_from_evidence_chunks -q
```

Expected: PASS.

---

### Task 3: Hybrid Score Breakdown

**Files:**
- Modify: `services/api/app/material_rag_service.py`
- Modify: `services/api/tests/test_material_vector_store.py`

- [ ] **Step 1: Write failing score breakdown test**

Add to `services/api/tests/test_material_vector_store.py`:

```python
def test_material_retrieval_candidate_exposes_hybrid_score_breakdown():
    from app.material_rag_service import retrieve_material_candidates_for_slot
    from app.models import NewContentInput, StructureSlot, UserSlotAsset

    slot = StructureSlot(
        id="selling_points",
        label="卖点展开",
        start=3,
        duration=8,
        purpose="展示快速补水卖点",
        required_asset="商品特写镜头",
        sample_evidence="产品细节特写",
    )
    content = NewContentInput(
        topic="新品保湿精华短视频",
        product_name="清透保湿精华",
        selling_points=["快速补水"],
        uploaded_assets=[
            UserSlotAsset(
                slot_id="material_pool",
                filename="detail-shot.mp4",
                public_url="/materials/detail-shot.mp4",
                analysis={
                    "evidence_chunks": [
                        {
                            "asset_id": "detail-shot.mp4",
                            "chunk_id": "chunk_detail",
                            "start": 1.2,
                            "end": 3.8,
                            "visual_summary": "清透保湿精华瓶身细节特写。",
                            "ocr_texts": ["快速补水"],
                            "packaging_signals": ["卖点字幕"],
                            "subject_tags": ["产品", "瓶身"],
                            "action_tags": ["特写"],
                            "slot_hints": ["卖点展开"],
                            "modalities": ["visual", "ocr", "packaging"],
                            "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                        }
                    ]
                },
            )
        ],
    )

    candidate = retrieve_material_candidates_for_slot(slot, content)[0]

    assert {"semantic", "visual", "ocr_asr", "packaging", "slot_hint", "duration_fit"}.issubset(candidate.score_breakdown)
    assert candidate.score_breakdown["ocr_asr"] > 0
    assert candidate.score_breakdown["visual"] > 0
    assert candidate.score_breakdown["slot_hint"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_material_retrieval_candidate_exposes_hybrid_score_breakdown -q
```

Expected: FAIL because vector candidates only expose `vector` score or incomplete score breakdown.

- [ ] **Step 3: Add hybrid score helper**

In `services/api/app/material_rag_service.py`, add:

```python
def _hybrid_score_breakdown(
    slot: StructureSlot,
    content: NewContentInput,
    chunk: MaterialEvidenceChunk,
    vector_score: int,
) -> dict[str, int]:
    text_terms = _dedupe([content.product_name, *content.selling_points, slot.required_asset, slot.label])
    chunk_text = " ".join([chunk.visual_summary, *chunk.ocr_texts, *chunk.asr_texts, chunk.embedding_text])
    ocr_asr_score = 25 if any(term and term in chunk_text for term in text_terms) else 0
    visual_terms = set([*chunk.subject_tags, *chunk.action_tags])
    visual_score = 20 if visual_terms else 0
    packaging_score = 15 if chunk.packaging_signals else 0
    slot_hint_score = 25 if slot.label in chunk.slot_hints or slot.id in chunk.slot_hints else 0
    duration_score = _duration_fit_score(slot.duration, chunk.duration or max(chunk.end - chunk.start, 0))
    return {
        "semantic": vector_score,
        "visual": visual_score,
        "ocr_asr": ocr_asr_score,
        "packaging": packaging_score,
        "slot_hint": slot_hint_score,
        "duration_fit": duration_score,
    }
```

Add:

```python
def _duration_fit_score(slot_duration: float, chunk_duration: float) -> int:
    if slot_duration <= 0 or chunk_duration <= 0:
        return 0
    ratio = min(slot_duration, chunk_duration) / max(slot_duration, chunk_duration)
    return round(ratio * 15)
```

Update `_vector_result_to_candidate()` to call `_hybrid_score_breakdown(slot, content, chunk, score)` and set `match_score` to `min(100, round(sum(score_breakdown.values()) / 1.35))`. This requires passing `content` into `_vector_result_to_candidate()` from `_vector_candidates_for_slot()`.

- [ ] **Step 4: Run score breakdown test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_material_retrieval_candidate_exposes_hybrid_score_breakdown -q
```

Expected: PASS.

---

### Task 4: SlotFillDecision Quality

**Files:**
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write decision test with candidate**

Add to `services/api/tests/test_structure_service.py`:

```python
def test_slot_fill_decision_reuses_candidate_with_packaging_actions():
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

    decision = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"].slot_fill_decision

    assert decision.decision_type in {"reuse_direct", "reuse_with_packaging"}
    assert decision.selected_asset_id == "detail-shot.mp4"
    assert decision.selected_chunk_id == "chunk_detail"
    assert decision.actions
    assert "卖点" in " ".join(decision.actions) or "裁切" in " ".join(decision.actions)
    assert decision.timeline_hint
```

- [ ] **Step 2: Run decision test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_slot_fill_decision_reuses_candidate_with_packaging_actions -q
```

Expected: PASS if Task 1 implementation covers it. If it fails due to weak action text, update `build_slot_fill_decision()` only.

- [ ] **Step 3: Write no-candidate decision test**

Add:

```python
def test_slot_fill_decision_falls_back_to_caption_when_no_candidate():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    decision = {gap.slot_id: gap for gap in response.transfer_plan.gaps}["selling_points"].slot_fill_decision

    assert decision.selected_asset_id == ""
    assert decision.decision_type in {"caption_only", "shoot_or_aigc"}
    assert decision.missing
    assert decision.actions
    assert decision.confidence <= 0.35
```

- [ ] **Step 4: Run no-candidate test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_slot_fill_decision_falls_back_to_caption_when_no_candidate -q
```

Expected: PASS.

---

### Task 5: Decision Affects Transfer Mapping

**Files:**
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write mapping integration test**

Add:

```python
def test_slot_fill_decision_updates_mapping_gap_handling():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            selling_points=["手作咖啡"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    mapping = {item.slot_id: item for item in response.transfer_plan.mappings}["selling_points"]

    assert gap.slot_fill_decision.actions[0] in mapping.asset_strategy
    assert gap.slot_fill_decision.actions[0] in mapping.explanation.gap_handling
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_slot_fill_decision_updates_mapping_gap_handling -q
```

Expected: FAIL if mapping still uses older fill strategy.

- [ ] **Step 3: Update mapping strategy**

In `services/api/app/structure_service.py`, update `build_asset_strategy()` to use decision action when no override or selected supplement exists:

```python
if gap and gap.slot_fill_decision.actions:
    return f"采用“{gap.slot_fill_decision.decision_type}”：{gap.slot_fill_decision.actions[0]}"
```

Update `build_transfer_plan()` by defining `gap` and `decision_action` inside the slot loop, then use them consistently:

```python
for slot in template.script_pattern:
    override = override_lookup.get(slot.id)
    gap = gap_lookup.get(slot.id)
    decision_action = gap.slot_fill_decision.actions[0] if gap and gap.slot_fill_decision.actions else ""
    target_message = (
        override.target_message.strip()
        if override and override.target_message.strip()
        else _target_message_for_slot(slot.id, content, variant)
    )
    selected_supplement = _selected_supplement_option(gap, supplement_lookup.get(slot.id))
    asset_strategy = build_asset_strategy(slot, gap, override, selected_supplement)
    packaging = _packaging_plan_for_slot(slot, content, target_message, variant)
    mapping = TransferMapping(
        slot_id=slot.id,
        source_label=slot.label,
        target_message=target_message,
        asset_strategy=asset_strategy,
        source_method=slot.method,
        target_adaptation=_target_adaptation_for_slot(slot, content, target_message),
        reasoning=_transfer_reasoning_for_slot(slot),
        asset_requirement=slot.required_asset,
        packaging_plan=_packaging_plan_summary(packaging, slot.packaging_intent),
        packaging=packaging,
        fallback_strategy=selected_supplement.action if selected_supplement else decision_action or gap.fill_strategy if gap else asset_strategy,
    )
    mappings.append(
        mapping.model_copy(
            update={
                "explanation": build_fallback_transfer_explanation(
                    mapping=mapping,
                    source_observation=slot.method or slot.sample_evidence,
                    transferable_principle=slot.transferable_rule,
                    gap_handling=selected_supplement.action if selected_supplement else decision_action or gap.fill_strategy if gap else "",
                )
            }
        )
    )
```

- [ ] **Step 4: Run mapping test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_slot_fill_decision_updates_mapping_gap_handling -q
```

Expected: PASS.

---

### Task 6: Frontend Decision Display

**Files:**
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/hooks/useReelStructApi.ts`
- Modify: `apps/web/src/app/ReelStructWorkspace.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/MaterialGapPanel.tsx`
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Add frontend types**

In all three type mirrors, add:

```ts
type SlotFillDecision = {
  slot_id: string
  decision_type: 'reuse_direct' | 'reuse_with_packaging' | 'caption_only' | 'structure_reorder' | 'shoot_or_aigc'
  selected_asset_id: string
  selected_chunk_id: string
  start: number
  end: number
  confidence: number
  why: string
  missing: string[]
  actions: string[]
  timeline_hint: string
}
```

Add to `MaterialGap`:

```ts
slot_fill_decision: SlotFillDecision
```

- [ ] **Step 2: Extend view model**

In `MaterialGapPanel.tsx`, add to `MaterialGapViewModel`:

```ts
slotFillDecision: {
  decisionType: string
  selectedAssetId: string
  selectedChunkId: string
  start: number
  end: number
  confidence: number
  why: string
  missing: string[]
  actions: string[]
  timelineHint: string
}
```

- [ ] **Step 3: Map decision in `WorkspaceView.tsx`**

Add to gap mapping:

```ts
slotFillDecision: {
  decisionType: gap.slot_fill_decision?.decision_type || '',
  selectedAssetId: gap.slot_fill_decision?.selected_asset_id || '',
  selectedChunkId: gap.slot_fill_decision?.selected_chunk_id || '',
  start: gap.slot_fill_decision?.start || 0,
  end: gap.slot_fill_decision?.end || 0,
  confidence: gap.slot_fill_decision?.confidence || 0,
  why: localizeText(gap.slot_fill_decision?.why || '', gap.slot_fill_decision?.why || ''),
  missing: (gap.slot_fill_decision?.missing || []).map((item) => localizeText(item, item)),
  actions: (gap.slot_fill_decision?.actions || []).map((item) => localizeText(item, item)),
  timelineHint: localizeText(gap.slot_fill_decision?.timeline_hint || '', gap.slot_fill_decision?.timeline_hint || ''),
}
```

- [ ] **Step 4: Render decision summary**

In `MaterialGapPanel.tsx`, render under retrieval plan:

```tsx
{gap.slotFillDecision.actions.length ? (
  <div className="gap-fill-decision">
    <div className="gap-fill-decision-head">
      <strong>{decisionTypeLabel(gap.slotFillDecision.decisionType)}</strong>
      <span>{Math.round(gap.slotFillDecision.confidence * 100)}%</span>
    </div>
    {gap.slotFillDecision.selectedAssetId ? (
      <p>命中素材：{gap.slotFillDecision.selectedAssetId}{gap.slotFillDecision.selectedChunkId ? ` / ${gap.slotFillDecision.selectedChunkId}` : ''}</p>
    ) : null}
    {gap.slotFillDecision.why ? <p>{gap.slotFillDecision.why}</p> : null}
    <ul>
      {gap.slotFillDecision.actions.slice(0, 3).map((item, index) => (
        <li key={`${gap.slotId}-decision-action-${index}`}>{item}</li>
      ))}
    </ul>
    {gap.slotFillDecision.timelineHint ? <em>{gap.slotFillDecision.timelineHint}</em> : null}
  </div>
) : null}
```

Add helper in same file:

```ts
function decisionTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    reuse_direct: '直接复用',
    reuse_with_packaging: '包装后复用',
    caption_only: '字幕补全',
    structure_reorder: '结构重排',
    shoot_or_aigc: '补拍/AIGC',
  }
  return labels[value] || '推荐决策'
}
```

- [ ] **Step 5: Add CSS**

Add to `apps/web/src/app/globals.css`:

```css
.gap-fill-decision {
  border: 1px solid color-mix(in oklab, var(--success), var(--border) 50%);
  border-radius: var(--radius-md);
  background: color-mix(in oklab, var(--success), transparent 92%);
  padding: var(--space-3);
  display: grid;
  gap: var(--space-2);
}

.gap-fill-decision-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  color: var(--fg);
  font-size: var(--text-sm);
}

.gap-fill-decision p,
.gap-fill-decision li,
.gap-fill-decision em {
  color: var(--muted);
  font-size: var(--text-xs);
  line-height: 1.55;
  font-style: normal;
  overflow-wrap: anywhere;
}

.gap-fill-decision ul {
  margin: 0;
  padding-left: var(--space-4);
}
```

- [ ] **Step 6: Run typecheck**

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: exit 0.

---

### Task 7: Final Verification

**Files:**
- No code changes unless tests expose bugs.

- [ ] **Step 1: Run focused backend tests**

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py tests/test_structure_service.py tests/test_workflow_service.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader material/media workflow tests**

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

- [ ] **Step 4: Run whitespace check**

```bash
cd /Users/linkwind/Code/ReelStruct
git diff --check
```

Expected: exit 0.

- [ ] **Step 5: Browser smoke check**

Use the in-app browser at `http://127.0.0.1:3000/`:

1. Enter workspace.
2. Open material supplement tab.
3. Verify page renders without runtime overlay.
4. If preview data exists, verify decision labels appear: `推荐决策`, `命中素材`, or `下一步动作`.

Expected: no runtime errors.
