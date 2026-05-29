# RAG v4 Material Completion Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn RAG material completion from candidate suggestions into an executable loop: slot profile -> graph search -> rerank -> fill decision -> timeline patch -> UI explanation.

**Architecture:** Keep the existing ReelStruct preview/workflow pipeline and add narrow services around it. `SlotQueryProfile` describes what a structure slot needs, `MaterialGraphSearchResult` explains why a material chunk matches, `SlotFillDecision` references graph evidence, and `TimelinePatch` turns the decision into composition changes. Rule-based behavior is the default; AI rerank remains an interface boundary for a later phase.

**Tech Stack:** FastAPI/Pydantic v2, pytest, existing in-memory/Milvus-compatible material vector store, React/TypeScript, Next.js, `tsc --noEmit`.

---

## File Structure

- Modify `services/api/app/models.py`
  - Extend `SlotQueryProfile`.
  - Add `MaterialGraphMatchedNode`, `MaterialGraphSearchResult`, `TimelineTrackUpdate`, `TimelinePatch`.
  - Extend `SlotFillDecision` with `evidence_path` and `timeline_patch_id`.
  - Extend `MaterialGap` with `slot_query_profile`, `graph_search_results`, `timeline_patches`.
- Create `services/api/app/slot_profile_service.py`
  - Build `SlotQueryProfile` from `StructureSlot` and `NewContentInput`.
- Modify `services/api/app/material_graph_service.py`
  - Keep `build_material_graph()`.
  - Add `search_material_graph_for_slot()`.
- Create `services/api/app/material_rerank_service.py`
  - Rule rerank graph results and candidates.
  - Provide an interface-shaped function for future AI rerank.
- Create `services/api/app/timeline_patch_service.py`
  - Build executable `TimelinePatch` objects from `SlotFillDecision`.
- Modify `services/api/app/structure_service.py`
  - Wire slot profile, graph search, rerank, decision v2, timeline patches, and composition patch application.
- Modify `services/api/tests/test_material_vector_store.py`
  - Graph search evidence path tests.
- Modify `services/api/tests/test_structure_service.py`
  - Slot profile, decision v2, timeline patch, and composition integration tests.
- Modify frontend type mirrors:
  - `apps/web/src/hooks/useReelStruct.ts`
  - `apps/web/src/hooks/useReelStructApi.ts`
  - `apps/web/src/app/ReelStructWorkspace.tsx`
- Modify frontend display:
  - `apps/web/src/components/Views/WorkspaceView.tsx`
  - `apps/web/src/components/Workspace/MaterialGapPanel.tsx`
  - `apps/web/src/app/globals.css`

---

### Task 1: Backend Models For Completion Loop

**Files:**
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write failing serialization test**

Add to `services/api/tests/test_structure_service.py` near existing material gap tests:

```python
def test_material_gap_serializes_rag_v4_completion_fields():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花", "开业优惠"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap_payload = response.transfer_plan.gaps[0].model_dump()

    assert "slot_query_profile" in gap_payload
    assert "graph_search_results" in gap_payload
    assert "timeline_patches" in gap_payload
    assert "evidence_path" in gap_payload["slot_fill_decision"]
    assert "timeline_patch_id" in gap_payload["slot_fill_decision"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_serializes_rag_v4_completion_fields -q
```

Expected: FAIL because `slot_query_profile`, `graph_search_results`, `timeline_patches`, `evidence_path`, and `timeline_patch_id` do not exist yet.

- [ ] **Step 3: Extend models**

In `services/api/app/models.py`, replace the current `SlotQueryProfile` with:

```python
class SlotQueryProfile(BaseModel):
    slot_id: str = ""
    slot_label: str = ""
    required_asset: str = ""
    required_expression: str = ""
    semantic_terms: list[str] = Field(default_factory=list)
    visual_terms: list[str] = Field(default_factory=list)
    action_terms: list[str] = Field(default_factory=list)
    text_terms: list[str] = Field(default_factory=list)
    packaging_terms: list[str] = Field(default_factory=list)
    target_duration: float = 0
    min_usable_duration: float = 0
    replacement_modes: list[Literal["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"]] = Field(default_factory=list)
```

Add after `SlotQueryProfile`:

```python
class MaterialGraphMatchedNode(BaseModel):
    node_id: str = ""
    node_type: str = ""
    label: str = ""
    text: str = ""
    source_asset_id: str = ""
    chunk_id: str = ""


class MaterialGraphSearchResult(BaseModel):
    slot_id: str = ""
    asset_id: str = ""
    chunk_id: str = ""
    start: float = 0
    end: float = 0
    matched_nodes: list[MaterialGraphMatchedNode] = Field(default_factory=list)
    evidence_path: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)


class TimelineTrackUpdate(BaseModel):
    type: Literal["video", "caption", "card"]
    action: Literal["replace", "insert", "request"]
    text: str = ""
    duration: float = 0
    style_hint: str = ""


class TimelinePatch(BaseModel):
    patch_id: str = ""
    slot_id: str = ""
    operation: Literal["replace_slot_media", "insert_caption_card", "request_asset"] = "insert_caption_card"
    target_start: float = 0
    target_end: float = 0
    source_asset_id: str = ""
    source_chunk_id: str = ""
    source_start: float = 0
    source_end: float = 0
    track_updates: list[TimelineTrackUpdate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

Extend `SlotFillDecision`:

```python
    evidence_path: list[str] = Field(default_factory=list)
    timeline_patch_id: str = ""
```

Extend `MaterialGap`:

```python
    slot_query_profile: SlotQueryProfile = Field(default_factory=SlotQueryProfile)
    graph_search_results: list[MaterialGraphSearchResult] = Field(default_factory=list)
    timeline_patches: list[TimelinePatch] = Field(default_factory=list)
```

- [ ] **Step 4: Add temporary model wiring in `build_material_gap()`**

In `services/api/app/structure_service.py`, import `SlotQueryProfile` and `TimelinePatch` if they are not already imported. Then add default objects when creating `MaterialGap`:

```python
slot_query_profile=SlotQueryProfile(
    slot_id=slot.id,
    slot_label=slot.label,
    required_asset=slot.required_asset,
    required_expression=slot.purpose,
    target_duration=slot.duration,
),
graph_search_results=[],
timeline_patches=[
    TimelinePatch(
        patch_id=f"patch_{slot.id}_fallback",
        slot_id=slot.id,
        operation="insert_caption_card",
        target_start=slot.start,
        target_end=slot.start + slot.duration,
        track_updates=[
            {
                "type": "card",
                "action": "insert",
                "text": supplement_options[0].action if supplement_options else fill_strategy,
                "duration": slot.duration,
                "style_hint": "兜底字幕卡",
            }
        ],
    )
],
```

For `slot_fill_decision`, set `timeline_patch_id` in the builder:

```python
decision = build_slot_fill_decision(slot, candidates, supplement_options)
if decision.timeline_patch_id == "":
    decision = decision.model_copy(update={"timeline_patch_id": f"patch_{slot.id}_fallback"})
```

- [ ] **Step 5: Run model serialization test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_material_gap_serializes_rag_v4_completion_fields -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/models.py services/api/app/structure_service.py services/api/tests/test_structure_service.py
git commit -m "feat: add rag v4 completion models"
```

---

### Task 2: SlotQueryProfile Builder

**Files:**
- Create: `services/api/app/slot_profile_service.py`
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write failing tests for profile generation**

Add to `services/api/tests/test_structure_service.py`:

```python
def test_build_slot_query_profile_extracts_visual_text_and_packaging_terms():
    from app.slot_profile_service import build_slot_query_profile

    slot = StructureSlot(
        id="selling_points",
        label="卖点展开",
        start=3,
        duration=8,
        purpose="连续推进核心卖点，保持信息密度。",
        required_asset="商品特写镜头",
        sample_evidence="样例用产品细节特写推进卖点。",
        role="建立兴趣",
        method="利益点连续推进",
        intent="让观众快速知道核心价值",
        packaging_intent="用卖点卡片、关键词高亮和短字幕提高信息密度。",
    )
    content = NewContentInput(
        topic="新品保湿精华短视频",
        product_name="清透保湿精华",
        selling_points=["快速补水", "清爽不黏"],
    )

    profile = build_slot_query_profile(slot, content)

    assert profile.slot_id == "selling_points"
    assert profile.slot_label == "卖点展开"
    assert profile.target_duration == 8
    assert profile.min_usable_duration >= 1
    assert "商品特写镜头" in profile.required_asset
    assert {"产品", "特写"}.issubset(set(profile.visual_terms))
    assert {"快速补水", "清爽不黏"}.issubset(set(profile.text_terms))
    assert "卖点卡片" in profile.packaging_terms
    assert "reuse_with_packaging" in profile.replacement_modes
```

Add a second test for CTA:

```python
def test_build_slot_query_profile_adds_cta_defaults():
    from app.slot_profile_service import build_slot_query_profile

    slot = StructureSlot(
        id="cta",
        label="CTA",
        start=16,
        duration=4,
        purpose="收束行动号召，强化记忆点。",
        required_asset="结尾 CTA 镜头",
        sample_evidence="结尾引导到店。",
        role="推动转化",
        method="利益收束 + 行动指令",
        packaging_intent="用结尾标题卡片、行动按钮感字幕和停留画面强化 CTA。",
    )
    content = NewContentInput(topic="咖啡店开业", product_name="巷口手作咖啡", selling_points=["开业优惠"])

    profile = build_slot_query_profile(slot, content)

    assert "行动" in profile.action_terms
    assert "入口" in profile.text_terms
    assert "结尾标题卡片" in profile.packaging_terms
    assert profile.replacement_modes[-1] == "shoot_or_aigc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_structure_service.py::test_build_slot_query_profile_extracts_visual_text_and_packaging_terms \
  tests/test_structure_service.py::test_build_slot_query_profile_adds_cta_defaults -q
```

Expected: FAIL because `app.slot_profile_service` does not exist.

- [ ] **Step 3: Create `slot_profile_service.py`**

Create `services/api/app/slot_profile_service.py`:

```python
from __future__ import annotations

from app.models import NewContentInput, SlotQueryProfile, StructureSlot


def build_slot_query_profile(slot: StructureSlot, content: NewContentInput) -> SlotQueryProfile:
    defaults = _slot_defaults(slot.id)
    semantic_terms = _dedupe(
        [
            slot.id,
            slot.label,
            slot.required_asset,
            slot.purpose,
            slot.method,
            slot.role,
            slot.intent,
            content.topic,
            content.product_name,
            *content.selling_points,
            *defaults["semantic"],
        ]
    )
    visual_terms = _dedupe([*defaults["visual"], *_terms_from_required_asset(slot.required_asset)])
    action_terms = _dedupe(defaults["action"])
    text_terms = _dedupe([content.product_name, *content.selling_points, *defaults["text"]])
    packaging_terms = _dedupe([*defaults["packaging"], *_split_packaging_terms(slot.packaging_intent)])
    return SlotQueryProfile(
        slot_id=slot.id,
        slot_label=slot.label,
        required_asset=slot.required_asset,
        required_expression="；".join(_dedupe([slot.purpose, slot.intent, slot.method, slot.transferable_rule])[:4]),
        semantic_terms=semantic_terms,
        visual_terms=visual_terms,
        action_terms=action_terms,
        text_terms=text_terms,
        packaging_terms=packaging_terms,
        target_duration=slot.duration,
        min_usable_duration=max(0.8, min(slot.duration * 0.35, 2.5)),
        replacement_modes=defaults["replacement_modes"],
    )


def _slot_defaults(slot_id: str) -> dict[str, list[str]]:
    defaults = {
        "hook": {
            "semantic": ["开头", "注意力", "停留", "结果", "反差"],
            "visual": ["人物", "产品", "结果画面", "封面"],
            "action": ["展示", "对比", "吸引"],
            "text": ["标题", "利益点", "为什么"],
            "packaging": ["大标题", "封面标题", "关键词高亮"],
            "replacement_modes": ["reuse_direct", "reuse_with_packaging", "caption_only", "shoot_or_aigc"],
        },
        "selling_points": {
            "semantic": ["卖点", "利益点", "产品价值"],
            "visual": ["产品", "瓶身", "特写", "细节"],
            "action": ["展示", "对比", "局部放大"],
            "text": ["卖点", "功效", "利益"],
            "packaging": ["卖点卡片", "关键词高亮", "局部放大框"],
            "replacement_modes": ["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"],
        },
        "usage": {
            "semantic": ["使用", "过程", "场景", "证明"],
            "visual": ["手部", "人物", "场景", "过程"],
            "action": ["使用", "演示", "操作", "对比"],
            "text": ["步骤", "过程", "说明"],
            "packaging": ["步骤编号", "说明字幕", "过程标签"],
            "replacement_modes": ["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"],
        },
        "cta": {
            "semantic": ["结尾", "行动", "转化", "记忆点"],
            "visual": ["门店", "入口", "二维码", "账号", "结尾卡"],
            "action": ["行动", "引导", "停留"],
            "text": ["入口", "优惠", "地址", "关注", "到店"],
            "packaging": ["结尾标题卡片", "行动按钮", "账号导流卡"],
            "replacement_modes": ["reuse_direct", "reuse_with_packaging", "caption_only", "structure_reorder", "shoot_or_aigc"],
        },
    }
    return defaults.get(
        slot_id,
        {
            "semantic": ["素材", "表达", "补位"],
            "visual": ["主体", "画面"],
            "action": ["展示"],
            "text": ["字幕"],
            "packaging": ["标题卡片"],
            "replacement_modes": ["reuse_with_packaging", "caption_only", "shoot_or_aigc"],
        },
    )


def _terms_from_required_asset(value: str) -> list[str]:
    if "特写" in value:
        return ["产品", "特写", "细节"]
    if "使用" in value or "过程" in value:
        return ["手部", "过程", "场景"]
    if "CTA" in value or "结尾" in value:
        return ["结尾卡", "入口", "门店"]
    if "开头" in value:
        return ["封面", "人物", "产品"]
    return [value]


def _split_packaging_terms(value: str) -> list[str]:
    terms = []
    for token in ["卖点卡片", "关键词高亮", "短字幕", "标题卡片", "行动按钮", "停留画面", "说明字幕", "过程标签"]:
        if token in value:
            terms.append(token)
    return terms


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        cleaned = item.strip() if isinstance(item, str) else ""
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result
```

- [ ] **Step 4: Wire profile builder into `structure_service.py`**

In `services/api/app/structure_service.py`, import:

```python
from app.slot_profile_service import build_slot_query_profile
```

In `build_material_gap()`, replace the temporary default `SlotQueryProfile(...)` with:

```python
slot_query_profile=build_slot_query_profile(slot, NewContentInput(topic="")),
```

Then change `build_material_gap()` signature to accept content:

```python
def build_material_gap(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    content: Optional[NewContentInput] = None,
) -> MaterialGap:
    effective_content = content or NewContentInput(topic="")
```

Update call site in `detect_material_gaps()`:

```python
gaps.append(build_material_gap(slot, candidates, content))
```

Use:

```python
slot_query_profile=build_slot_query_profile(slot, effective_content),
```

- [ ] **Step 5: Run profile tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_structure_service.py::test_build_slot_query_profile_extracts_visual_text_and_packaging_terms \
  tests/test_structure_service.py::test_build_slot_query_profile_adds_cta_defaults -q
```

Expected: PASS.

- [ ] **Step 6: Run existing structure tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/slot_profile_service.py services/api/app/structure_service.py services/api/tests/test_structure_service.py
git commit -m "feat: build slot query profiles"
```

---

### Task 3: MaterialGraph Search Results With Evidence Paths

**Files:**
- Modify: `services/api/app/material_graph_service.py`
- Test: `services/api/tests/test_material_vector_store.py`

- [ ] **Step 1: Write failing graph search test**

Add to `services/api/tests/test_material_vector_store.py`:

```python
def test_search_material_graph_for_slot_returns_evidence_path():
    from app.material_graph_service import build_material_graph, search_material_graph_for_slot
    from app.models import SlotQueryProfile, UserSlotAsset

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
            ]
        },
    )
    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        required_expression="连续推进卖点",
        visual_terms=["产品", "瓶身", "特写"],
        text_terms=["快速补水"],
        packaging_terms=["卖点字幕"],
        target_duration=8,
        min_usable_duration=1,
        replacement_modes=["reuse_with_packaging", "caption_only"],
    )

    graph = build_material_graph([asset])
    results = search_material_graph_for_slot(graph, profile)

    assert results
    result = results[0]
    assert result.asset_id == "detail-shot.mp4"
    assert result.chunk_id == "chunk_detail"
    assert result.score_breakdown["visual"] > 0
    assert result.score_breakdown["ocr_asr"] > 0
    assert result.score_breakdown["packaging"] > 0
    assert any("OCR=快速补水" in item for item in result.evidence_path)
    assert any(node.node_type == "ocr_text" for node in result.matched_nodes)
```

- [ ] **Step 2: Run graph search test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_search_material_graph_for_slot_returns_evidence_path -q
```

Expected: FAIL because `search_material_graph_for_slot` does not exist.

- [ ] **Step 3: Implement graph search**

In `services/api/app/material_graph_service.py`, import:

```python
from app.models import MaterialGraphSearchResult, MaterialGraphMatchedNode, SlotQueryProfile
```

Add:

```python
def search_material_graph_for_slot(
    graph: MaterialGraph,
    profile: SlotQueryProfile,
    *,
    top_k: int = 5,
) -> list[MaterialGraphSearchResult]:
    chunk_nodes = [node for node in graph.nodes if node.node_type == "chunk"]
    results: list[MaterialGraphSearchResult] = []
    for chunk in chunk_nodes:
        evidence_nodes = _child_nodes(graph, chunk.node_id)
        matched_nodes = _matched_nodes(chunk, evidence_nodes, profile)
        score_breakdown = _graph_score_breakdown(chunk, matched_nodes, profile)
        score = sum(score_breakdown.values())
        if score <= 0:
            continue
        results.append(
            MaterialGraphSearchResult(
                slot_id=profile.slot_id,
                asset_id=chunk.source_asset_id,
                chunk_id=chunk.chunk_id,
                start=chunk.start,
                end=chunk.end,
                matched_nodes=[
                    MaterialGraphMatchedNode(
                        node_id=node.node_id,
                        node_type=node.node_type,
                        label=node.label,
                        text=node.text,
                        source_asset_id=node.source_asset_id,
                        chunk_id=node.chunk_id,
                    )
                    for node in matched_nodes
                ],
                evidence_path=_evidence_path(chunk, matched_nodes, profile),
                missing=_graph_missing(profile, score_breakdown),
                score_breakdown=score_breakdown,
                confidence=round(min(0.95, score / 100), 2),
            )
        )
    return sorted(results, key=lambda item: item.confidence, reverse=True)[:top_k]


def _child_nodes(graph: MaterialGraph, source: str) -> list[MaterialGraphNode]:
    targets = {edge.target for edge in graph.edges if edge.source == source}
    return [node for node in graph.nodes if node.node_id in targets]


def _matched_nodes(
    chunk: MaterialGraphNode,
    evidence_nodes: list[MaterialGraphNode],
    profile: SlotQueryProfile,
) -> list[MaterialGraphNode]:
    terms = _lower_terms([*profile.visual_terms, *profile.action_terms, *profile.text_terms, *profile.packaging_terms, profile.slot_label])
    matched = [chunk] if _contains_any(chunk.text, terms) else []
    for node in evidence_nodes:
        if _contains_any(" ".join([node.label, node.text]), terms):
            matched.append(node)
    return matched


def _graph_score_breakdown(
    chunk: MaterialGraphNode,
    matched_nodes: list[MaterialGraphNode],
    profile: SlotQueryProfile,
) -> dict[str, int]:
    node_types = {node.node_type for node in matched_nodes}
    score = {
        "semantic": 20 if _contains_any(chunk.text, _lower_terms(profile.semantic_terms)) else 0,
        "visual": 20 if "tag" in node_types or _contains_any(chunk.text, _lower_terms(profile.visual_terms)) else 0,
        "ocr_asr": 25 if {"ocr_text", "asr_text"} & node_types else 0,
        "packaging": 15 if "packaging_signal" in node_types else 0,
        "slot_hint": 25 if "slot_hint" in node_types else 0,
        "duration_fit": _duration_fit_score(profile.target_duration, chunk.end - chunk.start),
    }
    return score


def _duration_fit_score(target_duration: float, chunk_duration: float) -> int:
    if target_duration <= 0 or chunk_duration <= 0:
        return 0
    ratio = min(target_duration, chunk_duration) / max(target_duration, chunk_duration)
    return round(ratio * 15)


def _evidence_path(
    chunk: MaterialGraphNode,
    matched_nodes: list[MaterialGraphNode],
    profile: SlotQueryProfile,
) -> list[str]:
    path = [f"槽位 {profile.slot_label or profile.slot_id} 需要 {profile.required_asset}"]
    for node in matched_nodes:
        if node.node_type == "chunk":
            path.append(f"{chunk.chunk_id} 命中 视觉摘要={node.text}")
        elif node.node_type == "ocr_text":
            path.append(f"{chunk.chunk_id} 命中 OCR={node.text}")
        elif node.node_type == "asr_text":
            path.append(f"{chunk.chunk_id} 命中 ASR={node.text}")
        elif node.node_type == "packaging_signal":
            path.append(f"{chunk.chunk_id} 命中 包装={node.text}")
        elif node.node_type == "tag":
            path.append(f"{chunk.chunk_id} 命中 标签={node.text}")
        elif node.node_type == "slot_hint":
            path.append(f"{chunk.chunk_id} 命中 槽位提示={node.text}")
    return _dedupe(path)


def _graph_missing(profile: SlotQueryProfile, score_breakdown: dict[str, int]) -> list[str]:
    missing: list[str] = []
    if profile.visual_terms and score_breakdown.get("visual", 0) == 0:
        missing.append("缺少明确画面主体或动作证据")
    if profile.text_terms and score_breakdown.get("ocr_asr", 0) == 0:
        missing.append("缺少 OCR/ASR 文本证据")
    if profile.packaging_terms and score_breakdown.get("packaging", 0) == 0:
        missing.append("缺少包装信号")
    return missing


def _lower_terms(values: list[str]) -> list[str]:
    return [value.lower() for value in values if value]


def _contains_any(value: str, terms: list[str]) -> bool:
    normalized = value.lower()
    return any(term and term in normalized for term in terms)
```

Reuse the existing `_dedupe()` helper already in `material_graph_service.py`; if it does not exist, add the same small helper from Task 2.

- [ ] **Step 4: Run graph search test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_search_material_graph_for_slot_returns_evidence_path -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/material_graph_service.py services/api/tests/test_material_vector_store.py
git commit -m "feat: search material graph for slot evidence"
```

---

### Task 4: Rule Rerank For Graph Search Results

**Files:**
- Create: `services/api/app/material_rerank_service.py`
- Test: `services/api/tests/test_material_vector_store.py`

- [ ] **Step 1: Write failing rerank test**

Add to `services/api/tests/test_material_vector_store.py`:

```python
def test_rerank_material_graph_results_prefers_visual_and_text_evidence():
    from app.material_rerank_service import rerank_material_graph_results
    from app.models import MaterialGraphSearchResult, MaterialGraphMatchedNode, SlotQueryProfile

    profile = SlotQueryProfile(slot_id="selling_points", slot_label="卖点展开", required_asset="商品特写镜头")
    weak = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="text-only.mp4",
        chunk_id="chunk_text",
        matched_nodes=[MaterialGraphMatchedNode(node_type="ocr_text", text="快速补水")],
        evidence_path=["chunk_text 命中 OCR=快速补水"],
        score_breakdown={"ocr_asr": 25, "visual": 0, "packaging": 0, "slot_hint": 0, "duration_fit": 5},
        confidence=0.3,
    )
    strong = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="detail.mp4",
        chunk_id="chunk_detail",
        matched_nodes=[
            MaterialGraphMatchedNode(node_type="tag", text="产品"),
            MaterialGraphMatchedNode(node_type="ocr_text", text="快速补水"),
            MaterialGraphMatchedNode(node_type="packaging_signal", text="卖点字幕"),
        ],
        evidence_path=["chunk_detail 命中 标签=产品", "chunk_detail 命中 OCR=快速补水", "chunk_detail 命中 包装=卖点字幕"],
        score_breakdown={"ocr_asr": 25, "visual": 20, "packaging": 15, "slot_hint": 0, "duration_fit": 5},
        confidence=0.65,
    )

    ranked = rerank_material_graph_results(profile, [weak, strong])

    assert ranked[0].asset_id == "detail.mp4"
    assert ranked[0].confidence > strong.confidence
```

- [ ] **Step 2: Run rerank test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_rerank_material_graph_results_prefers_visual_and_text_evidence -q
```

Expected: FAIL because `app.material_rerank_service` does not exist.

- [ ] **Step 3: Implement rule rerank**

Create `services/api/app/material_rerank_service.py`:

```python
from __future__ import annotations

from app.models import MaterialGraphSearchResult, SlotQueryProfile


def rerank_material_graph_results(
    profile: SlotQueryProfile,
    results: list[MaterialGraphSearchResult],
) -> list[MaterialGraphSearchResult]:
    ranked = [_with_rule_bonus(profile, result) for result in results]
    return sorted(ranked, key=lambda item: item.confidence, reverse=True)


def _with_rule_bonus(
    profile: SlotQueryProfile,
    result: MaterialGraphSearchResult,
) -> MaterialGraphSearchResult:
    bonus = 0.0
    breakdown = result.score_breakdown
    if breakdown.get("visual", 0) > 0 and breakdown.get("ocr_asr", 0) > 0:
        bonus += 0.12
    if breakdown.get("slot_hint", 0) > 0:
        bonus += 0.08
    if breakdown.get("packaging", 0) > 0 and "reuse_with_packaging" in profile.replacement_modes:
        bonus += 0.05
    if breakdown.get("visual", 0) == 0 and breakdown.get("ocr_asr", 0) > 0:
        bonus -= 0.05
    next_confidence = round(min(0.95, max(0, result.confidence + bonus)), 2)
    return result.model_copy(update={"confidence": next_confidence})
```

- [ ] **Step 4: Run rerank test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_rerank_material_graph_results_prefers_visual_and_text_evidence -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/material_rerank_service.py services/api/tests/test_material_vector_store.py
git commit -m "feat: rerank material graph results"
```

---

### Task 5: SlotFillDecision v2 Uses Graph Evidence

**Files:**
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write failing decision v2 integration test**

Add to `services/api/tests/test_structure_service.py`:

```python
def test_slot_fill_decision_uses_graph_evidence_path_for_uploaded_chunk():
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

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    decision = gap.slot_fill_decision

    assert gap.graph_search_results
    assert decision.selected_asset_id == "detail-shot.mp4"
    assert decision.selected_chunk_id == "chunk_detail"
    assert decision.evidence_path
    assert any("OCR=快速补水" in item for item in decision.evidence_path)
    assert decision.timeline_patch_id
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_slot_fill_decision_uses_graph_evidence_path_for_uploaded_chunk -q
```

Expected: FAIL because `build_structure_preview()` does not yet feed graph search results into `MaterialGap` and `SlotFillDecision`.

- [ ] **Step 3: Wire graph search into material gap detection**

In `services/api/app/structure_service.py`, import:

```python
from app.material_graph_service import build_material_graph, search_material_graph_for_slot
from app.material_rerank_service import rerank_material_graph_results
from app.slot_profile_service import build_slot_query_profile
```

Change `detect_material_gaps()` loop:

```python
for slot in template.script_pattern:
    if slot.required_asset in assets:
        continue
    profile = build_slot_query_profile(slot, content)
    material_graph = build_material_graph(content.uploaded_assets)
    graph_results = rerank_material_graph_results(
        profile,
        search_material_graph_for_slot(material_graph, profile),
    )
    candidates = material_rag_service.retrieve_material_candidates_for_slot(slot, content)
    gaps.append(build_material_gap(slot, candidates, content, profile, graph_results))
```

Change `build_material_gap()` signature:

```python
def build_material_gap(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    content: Optional[NewContentInput] = None,
    slot_query_profile: Optional[SlotQueryProfile] = None,
    graph_search_results: Optional[list[MaterialGraphSearchResult]] = None,
) -> MaterialGap:
```

Inside `build_material_gap()`:

```python
effective_content = content or NewContentInput(topic="")
profile = slot_query_profile or build_slot_query_profile(slot, effective_content)
graph_results = graph_search_results or []
slot_fill_decision = build_slot_fill_decision(slot, candidates, supplement_options, graph_results)
```

Pass to `MaterialGap`:

```python
slot_query_profile=profile,
graph_search_results=graph_results,
```

- [ ] **Step 4: Upgrade `build_slot_fill_decision()` signature and logic**

Change signature:

```python
def build_slot_fill_decision(
    slot: StructureSlot,
    candidates: list[MaterialRetrievalCandidate],
    supplement_options: list[MaterialSupplementOption],
    graph_search_results: Optional[list[MaterialGraphSearchResult]] = None,
) -> SlotFillDecision:
```

Add before candidate fallback:

```python
graph_best = graph_search_results[0] if graph_search_results else None
if graph_best is not None and graph_best.confidence >= 0.45:
    action = f"裁切 {graph_best.asset_id} 的 {graph_best.start}s-{graph_best.end}s 放入“{slot.label}”段。"
    if graph_best.score_breakdown.get("packaging", 0) > 0:
        action = f"{action} 保留或叠加其包装信息。"
    decision_type = "reuse_direct" if graph_best.confidence >= 0.82 and not graph_best.missing else "reuse_with_packaging"
    return SlotFillDecision(
        slot_id=slot.id,
        decision_type=decision_type,
        selected_asset_id=graph_best.asset_id,
        selected_chunk_id=graph_best.chunk_id,
        start=graph_best.start,
        end=graph_best.end,
        confidence=graph_best.confidence,
        why="；".join(graph_best.evidence_path[:3]),
        missing=graph_best.missing,
        actions=[action],
        timeline_hint=f"放在“{slot.label}”段，优先使用 {graph_best.start}s-{graph_best.end}s。",
        evidence_path=graph_best.evidence_path,
        timeline_patch_id=f"patch_{slot.id}_1",
    )
```

Keep existing candidate/no-candidate logic after this block.

- [ ] **Step 5: Run decision v2 test**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_slot_fill_decision_uses_graph_evidence_path_for_uploaded_chunk -q
```

Expected: PASS.

- [ ] **Step 6: Run structure tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/structure_service.py services/api/tests/test_structure_service.py
git commit -m "feat: use graph evidence in slot fill decisions"
```

---

### Task 6: TimelinePatch Generation And Composition Execution

**Files:**
- Create: `services/api/app/timeline_patch_service.py`
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: Write failing timeline patch test**

Add to `services/api/tests/test_structure_service.py`:

```python
def test_timeline_patch_inserts_caption_card_for_missing_material():
    response = build_structure_preview(
        sample=SampleVideoInput(title="咖啡样例", duration=20, shot_count=6),
        content=NewContentInput(
            topic="咖啡店开业",
            product_name="巷口手作咖啡",
            selling_points=["手作拉花"],
            available_assets=["开头吸引镜头"],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    patch = gap.timeline_patches[0]
    slot_tracks = [track for track in response.composition.tracks if track.slot_id == "selling_points"]

    assert patch.operation == "insert_caption_card"
    assert patch.track_updates
    assert any(update.type == "card" for update in patch.track_updates)
    assert any(track.type == "card" and patch.track_updates[0].text in track.text for track in slot_tracks)
```

Add a second test for replace media:

```python
def test_timeline_patch_replaces_slot_media_for_graph_candidate():
    response = build_structure_preview(
        sample=SampleVideoInput(title="护肤样例", duration=30, shot_count=8),
        content=NewContentInput(
            topic="新品保湿精华短视频",
            product_name="清透保湿精华",
            selling_points=["快速补水"],
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
                                "subject_tags": ["产品", "瓶身"],
                                "action_tags": ["特写"],
                                "slot_hints": ["卖点展开"],
                                "modalities": ["visual", "ocr"],
                                "embedding_text": "清透保湿精华 快速补水 产品 瓶身 特写 卖点展开",
                            }
                        ],
                    },
                )
            ],
        ),
    )

    gap = {item.slot_id: item for item in response.transfer_plan.gaps}["selling_points"]
    patch = gap.timeline_patches[0]
    video_track = next(track for track in response.composition.tracks if track.slot_id == "selling_points" and track.type == "video")

    assert patch.operation == "replace_slot_media"
    assert patch.source_asset_id == "detail-shot.mp4"
    assert video_track.asset_public_url == "/materials/detail-shot.mp4"
```

- [ ] **Step 2: Run timeline patch tests to verify they fail**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_structure_service.py::test_timeline_patch_inserts_caption_card_for_missing_material \
  tests/test_structure_service.py::test_timeline_patch_replaces_slot_media_for_graph_candidate -q
```

Expected: FAIL because timeline patches are not generated from decisions and composition does not apply patches.

- [ ] **Step 3: Create timeline patch service**

Create `services/api/app/timeline_patch_service.py`:

```python
from __future__ import annotations

from app.models import SlotFillDecision, StructureSlot, TimelinePatch, TimelineTrackUpdate


def build_timeline_patch(slot: StructureSlot, decision: SlotFillDecision) -> TimelinePatch:
    patch_id = decision.timeline_patch_id or f"patch_{slot.id}_1"
    target_end = slot.start + slot.duration
    if decision.selected_asset_id:
        duration = max(decision.end - decision.start, 0)
        updates = [
            TimelineTrackUpdate(type="video", action="replace", duration=duration or slot.duration),
        ]
        if decision.decision_type == "reuse_with_packaging":
            updates.append(
                TimelineTrackUpdate(
                    type="card",
                    action="insert",
                    text=_action_text(decision),
                    duration=max(slot.duration - 1, 1),
                    style_hint="包装补全",
                )
            )
        return TimelinePatch(
            patch_id=patch_id,
            slot_id=slot.id,
            operation="replace_slot_media",
            target_start=slot.start,
            target_end=target_end,
            source_asset_id=decision.selected_asset_id,
            source_chunk_id=decision.selected_chunk_id,
            source_start=decision.start,
            source_end=decision.end,
            track_updates=updates,
            warnings=["素材片段短于目标段落，剩余时间用包装卡补足"] if duration and duration < slot.duration * 0.7 else [],
        )
    if decision.decision_type == "shoot_or_aigc":
        return TimelinePatch(
            patch_id=patch_id,
            slot_id=slot.id,
            operation="request_asset",
            target_start=slot.start,
            target_end=target_end,
            track_updates=[
                TimelineTrackUpdate(type="card", action="request", text=_action_text(decision), duration=slot.duration, style_hint="补拍/AIGC")
            ],
            warnings=decision.missing,
        )
    return TimelinePatch(
        patch_id=patch_id,
        slot_id=slot.id,
        operation="insert_caption_card",
        target_start=slot.start,
        target_end=target_end,
        track_updates=[
            TimelineTrackUpdate(type="card", action="insert", text=_action_text(decision), duration=slot.duration, style_hint="字幕补全")
        ],
        warnings=decision.missing,
    )


def _action_text(decision: SlotFillDecision) -> str:
    return decision.actions[0] if decision.actions else decision.why or "用字幕和包装元素补足表达"
```

- [ ] **Step 4: Wire patches into `build_material_gap()`**

In `services/api/app/structure_service.py`, import:

```python
from app.timeline_patch_service import build_timeline_patch
```

After `slot_fill_decision` is created:

```python
timeline_patches = [build_timeline_patch(slot, slot_fill_decision)]
slot_fill_decision = slot_fill_decision.model_copy(update={"timeline_patch_id": timeline_patches[0].patch_id})
```

Pass:

```python
timeline_patches=timeline_patches,
```

- [ ] **Step 5: Apply timeline patches in composition**

In `build_composition_spec()`, create a gap lookup before the slot loop:

```python
gap_lookup = {gap.slot_id: gap for gap in transfer_plan.gaps}
```

Inside the slot loop, before `track_payload`:

```python
gap = gap_lookup.get(slot.id)
patch = gap.timeline_patches[0] if gap and gap.timeline_patches else None
patch_asset = _uploaded_asset_for_patch(content, patch) if content and patch else None
```

Use patch asset in video track:

```python
asset_for_track = uploaded_asset or patch_asset
```

Then replace `uploaded_asset` with `asset_for_track` in `asset_local_path`, `asset_public_url`, and `material_analysis`.

After existing card text insertion, add:

```python
if patch:
    for update in patch.track_updates:
        if update.type == "card" and update.text:
            tracks.append(
                CompositionTrack(
                    type="card",
                    start=slot.start + 0.8,
                    duration=max(update.duration or slot.duration - 1, 1),
                    text=update.text,
                    slot_id=slot.id,
                )
            )
```

Add helper near `build_composition_spec()`:

```python
def _uploaded_asset_for_patch(
    content: NewContentInput,
    patch: TimelinePatch,
) -> Optional[UserSlotAsset]:
    if not patch.source_asset_id:
        return None
    for asset in content.uploaded_assets:
        asset_id = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.slot_id
        if asset_id == patch.source_asset_id:
            return asset
    return None
```

- [ ] **Step 6: Run timeline patch tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_structure_service.py::test_timeline_patch_inserts_caption_card_for_missing_material \
  tests/test_structure_service.py::test_timeline_patch_replaces_slot_media_for_graph_candidate -q
```

Expected: PASS.

- [ ] **Step 7: Run workflow tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_workflow_service.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/timeline_patch_service.py services/api/app/structure_service.py services/api/tests/test_structure_service.py
git commit -m "feat: apply timeline patches for material completion"
```

---

### Task 7: Frontend Completion Chain Display

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
type SlotQueryProfile = {
  slot_id: string
  slot_label: string
  required_asset: string
  required_expression: string
  semantic_terms: string[]
  visual_terms: string[]
  action_terms: string[]
  text_terms: string[]
  packaging_terms: string[]
  target_duration: number
  min_usable_duration: number
  replacement_modes: string[]
}

type MaterialGraphMatchedNode = {
  node_id: string
  node_type: string
  label: string
  text: string
  source_asset_id: string
  chunk_id: string
}

type MaterialGraphSearchResult = {
  slot_id: string
  asset_id: string
  chunk_id: string
  start: number
  end: number
  matched_nodes: MaterialGraphMatchedNode[]
  evidence_path: string[]
  missing: string[]
  score_breakdown: Record<string, number>
  confidence: number
}

type TimelineTrackUpdate = {
  type: 'video' | 'caption' | 'card'
  action: 'replace' | 'insert' | 'request'
  text: string
  duration: number
  style_hint: string
}

type TimelinePatch = {
  patch_id: string
  slot_id: string
  operation: 'replace_slot_media' | 'insert_caption_card' | 'request_asset'
  target_start: number
  target_end: number
  source_asset_id: string
  source_chunk_id: string
  source_start: number
  source_end: number
  track_updates: TimelineTrackUpdate[]
  warnings: string[]
}
```

Extend `SlotFillDecision`:

```ts
  evidence_path: string[]
  timeline_patch_id: string
```

Extend `MaterialGap`:

```ts
  slot_query_profile: SlotQueryProfile
  graph_search_results: MaterialGraphSearchResult[]
  timeline_patches: TimelinePatch[]
```

- [ ] **Step 2: Extend `MaterialGapViewModel`**

In `apps/web/src/components/Workspace/MaterialGapPanel.tsx`, add:

```ts
  slotQueryProfile: {
    requiredExpression: string
    visualTerms: string[]
    textTerms: string[]
    packagingTerms: string[]
    targetDuration: number
  }
  graphSearchResults: Array<{
    assetId: string
    chunkId: string
    confidence: number
    evidencePath: string[]
    missing: string[]
    scoreBreakdown: Record<string, number>
  }>
  timelinePatches: Array<{
    patchId: string
    operation: string
    targetStart: number
    targetEnd: number
    sourceAssetId: string
    sourceChunkId: string
    trackUpdates: Array<{
      type: string
      action: string
      text: string
      duration: number
      styleHint: string
    }>
    warnings: string[]
  }>
```

Extend existing `slotFillDecision` view model:

```ts
    evidencePath: string[]
    timelinePatchId: string
```

- [ ] **Step 3: Map backend fields in `WorkspaceView.tsx`**

In `gapItems` mapping, add:

```ts
slotQueryProfile: {
  requiredExpression: localizeText(gap.slot_query_profile?.required_expression || '', gap.slot_query_profile?.required_expression || ''),
  visualTerms: (gap.slot_query_profile?.visual_terms || []).map((item) => localizeText(item, item)),
  textTerms: (gap.slot_query_profile?.text_terms || []).map((item) => localizeText(item, item)),
  packagingTerms: (gap.slot_query_profile?.packaging_terms || []).map((item) => localizeText(item, item)),
  targetDuration: gap.slot_query_profile?.target_duration || 0,
},
graphSearchResults: (gap.graph_search_results || []).map((result) => ({
  assetId: result.asset_id,
  chunkId: result.chunk_id,
  confidence: result.confidence,
  evidencePath: (result.evidence_path || []).map((item) => localizeText(item, item)),
  missing: (result.missing || []).map((item) => localizeText(item, item)),
  scoreBreakdown: result.score_breakdown || {},
})),
timelinePatches: (gap.timeline_patches || []).map((patch) => ({
  patchId: patch.patch_id,
  operation: patch.operation,
  targetStart: patch.target_start,
  targetEnd: patch.target_end,
  sourceAssetId: patch.source_asset_id,
  sourceChunkId: patch.source_chunk_id,
  trackUpdates: (patch.track_updates || []).map((update) => ({
    type: update.type,
    action: update.action,
    text: localizeText(update.text || '', update.text || ''),
    duration: update.duration,
    styleHint: localizeText(update.style_hint || '', update.style_hint || ''),
  })),
  warnings: (patch.warnings || []).map((item) => localizeText(item, item)),
})),
```

Extend `slotFillDecision` mapping:

```ts
evidencePath: (gap.slot_fill_decision?.evidence_path || []).map((item) => localizeText(item, item)),
timelinePatchId: gap.slot_fill_decision?.timeline_patch_id || '',
```

- [ ] **Step 4: Render completion chain in `MaterialGapPanel.tsx`**

Under the current `.gap-fill-decision` block, add:

```tsx
{gap.timelinePatches.length ? (
  <div className="gap-completion-chain">
    <div className="gap-completion-step">
      <strong>槽位需求</strong>
      <span>{gap.slotQueryProfile.requiredExpression || gap.retrievalPlan.requiredExpression}</span>
    </div>
    {gap.graphSearchResults[0] ? (
      <div className="gap-completion-step">
        <strong>图谱命中</strong>
        <span>
          {gap.graphSearchResults[0].assetId}
          {gap.graphSearchResults[0].chunkId ? ` / ${gap.graphSearchResults[0].chunkId}` : ''}
          {' '}· {Math.round(gap.graphSearchResults[0].confidence * 100)}%
        </span>
      </div>
    ) : null}
    <div className="gap-completion-step">
      <strong>时间线结果</strong>
      <span>{patchOperationLabel(gap.timelinePatches[0].operation)} · {gap.timelinePatches[0].targetStart}s-{gap.timelinePatches[0].targetEnd}s</span>
    </div>
    {gap.timelinePatches[0].trackUpdates.length ? (
      <ul>
        {gap.timelinePatches[0].trackUpdates.slice(0, 3).map((update, index) => (
          <li key={`${gap.slotId}-patch-update-${index}`}>
            {trackUpdateLabel(update.type, update.action)}{update.text ? `：${update.text}` : ''}
          </li>
        ))}
      </ul>
    ) : null}
    {gap.slotFillDecision.evidencePath.length ? (
      <details>
        <summary>查看证据链</summary>
        <ul>
          {gap.slotFillDecision.evidencePath.slice(0, 6).map((item, index) => (
            <li key={`${gap.slotId}-evidence-path-${index}`}>{item}</li>
          ))}
        </ul>
      </details>
    ) : null}
  </div>
) : null}
```

Add helpers:

```ts
function patchOperationLabel(value: string): string {
  const labels: Record<string, string> = {
    replace_slot_media: '替换槽位画面',
    insert_caption_card: '插入字幕卡',
    request_asset: '生成素材任务',
  }
  return labels[value] || '时间线补全'
}

function trackUpdateLabel(type: string, action: string): string {
  const typeLabels: Record<string, string> = {
    video: '画面',
    caption: '字幕',
    card: '卡片',
  }
  const actionLabels: Record<string, string> = {
    replace: '替换',
    insert: '插入',
    request: '请求',
  }
  return `${actionLabels[action] || action}${typeLabels[type] || type}`
}
```

- [ ] **Step 5: Add CSS**

In `apps/web/src/app/globals.css`, add near gap styles:

```css
.gap-completion-chain {
  border: 1px solid color-mix(in oklab, var(--accent), var(--border) 52%);
  border-radius: var(--radius-md);
  background: color-mix(in oklab, var(--accent), transparent 94%);
  padding: var(--space-3);
  display: grid;
  gap: var(--space-2);
}
.gap-completion-step {
  display: grid;
  gap: 3px;
}
.gap-completion-step strong {
  color: var(--fg);
  font-size: var(--text-xs);
}
.gap-completion-step span,
.gap-completion-chain li,
.gap-completion-chain summary {
  color: var(--muted);
  font-size: var(--text-xs);
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.gap-completion-chain ul {
  margin: 0;
  padding-left: var(--space-4);
}
.gap-completion-chain details {
  display: grid;
  gap: var(--space-2);
}
.gap-completion-chain summary {
  cursor: pointer;
}
```

- [ ] **Step 6: Run typecheck**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit Task 7**

```bash
cd /Users/linkwind/Code/ReelStruct
git add apps/web/src/hooks/useReelStruct.ts apps/web/src/hooks/useReelStructApi.ts apps/web/src/app/ReelStructWorkspace.tsx apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/MaterialGapPanel.tsx apps/web/src/app/globals.css
git commit -m "feat: show material completion chain"
```

---

### Task 8: Final Verification

**Files:**
- No planned code changes.

- [ ] **Step 1: Run material and structure tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py tests/test_structure_service.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run workflow/media tests**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_media_api.py tests/test_workflow_service.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend typecheck**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: exit 0.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
git diff --check
```

Expected: exit 0.

- [ ] **Step 5: Browser smoke**

Use the in-app browser at `http://127.0.0.1:3000/`.

1. Confirm backend is running on `http://127.0.0.1:8010`.
2. Open workspace.
3. Generate a preview or demo with a sample and at least one missing material slot.
4. Open material supplement view.
5. Verify no runtime overlay appears.
6. Verify material gap cards can show one of:
   - `槽位需求`
   - `图谱命中`
   - `时间线结果`
   - `查看证据链`

Expected: no runtime errors; completion chain appears when backend returns v4 fields.

- [ ] **Step 6: Commit verification notes only if a test fixture needed adjustment**

If no files changed during verification, do not create a commit. If a fixture or test needed a real fix, commit the exact changed files:

```bash
cd /Users/linkwind/Code/ReelStruct
git add <changed-files>
git commit -m "test: stabilize rag v4 completion verification"
```

