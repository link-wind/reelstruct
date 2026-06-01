# ReelStruct 未完成问题收敛执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前已识别的未完成问题收敛成 5 条可执行 P0 主线，优先解决结构主轴不统一、RAG 不够可信、补全不能执行、前端表达不清和缺少评估体系的问题。

**Architecture:** 本计划不引入新的大子系统，而是在现有 ReelStruct 链路上做收敛式增强。后端围绕 `segment -> unit -> shot` 主轴、结构覆盖率、多模态 evidence scoring 和可执行 timeline patch 展开；前端围绕“结构概要 / 素材供给 / 缺口补全 / 迁移结果”重构展示；测试与评估作为单独主线补齐。

**Tech Stack:** FastAPI / Pydantic v2、pytest、Next.js / React / TypeScript、现有 OCR / ASR / material graph / vector store 链路。

---

## File Structure

### 后端核心文件

- Modify: `services/api/app/models.py`
  - 扩展结构覆盖率、缺口等级、评估摘要等模型字段。
- Modify: `services/api/app/structure_service.py`
  - 串联结构主轴、缺口识别、补全决策与结果映射。
- Modify: `services/api/app/material_graph_service.py`
  - 增强多模态节点命中与 evidence scoring。
- Modify: `services/api/app/material_rerank_service.py`
  - 补充更强的 rule/AI judge 边界。
- Modify: `services/api/app/timeline_patch_service.py`
  - 让 patch 更接近结果执行层。
- Modify: `services/api/app/workflow_service.py`
  - 把补全链路结果更明确传递给前端结果视图。
- Create: `services/api/app/structure_coverage_service.py`
  - 负责结构槽位覆盖率、缺口等级、可补全性评分。
- Create: `services/api/app/evaluation_service.py`
  - 汇总结构、检索、补全、结果评估摘要。

### 后端测试

- Modify: `services/api/tests/test_structure_service.py`
- Modify: `services/api/tests/test_material_vector_store.py`
- Modify: `services/api/tests/test_workflow_service.py`
- Create: `services/api/tests/test_structure_coverage_service.py`
- Create: `services/api/tests/test_evaluation_service.py`

### 前端核心文件

- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/hooks/useReelStructApi.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`
- Modify: `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`
- Modify: `apps/web/src/components/Workspace/MaterialGapPanel.tsx`
- Modify: `apps/web/src/components/Workspace/ResultPreviewPanel.tsx`
- Modify: `apps/web/src/components/Workspace/TransferExplanationPanel.tsx`
- Modify: `apps/web/src/components/Workspace/GraphMapPanel.tsx`
- Modify: `apps/web/src/app/globals.css`
- Create: `apps/web/src/components/Workspace/StructureCoveragePanel.tsx`
- Create: `apps/web/src/components/Workspace/EvaluationSummaryPanel.tsx`

### 文档

- Reference: `docs/superpowers/specs/2026-05-29-project-open-issues.md`
- Update during execution as needed:
  - `docs/superpowers/specs/2026-05-29-project-open-issues.md`

---

### Task 1: 统一结构主轴（segment -> unit -> shot）

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/video_understanding/schemas.py`
- Modify: `services/api/app/video_understanding/ai_structure_service.py`
- Modify: `services/api/app/video_understanding/shot_evidence_graph.py`
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_service.py`
- Test: `services/api/tests/test_ai_video_structure_service.py`

- [ ] **Step 1: 写一个 failing 测试，约束结构主轴输出必须稳定暴露 segment / unit / shot 三层**

在 `services/api/tests/test_structure_service.py` 增加：

```python
def test_structure_preview_exposes_segment_unit_shot_hierarchy():
    response = build_structure_preview(
        sample=SampleVideoInput(
            title="结构样例",
            duration=24,
            shot_count=6,
            transcript_summary="开头吸引，中段卖点，结尾行动号召。",
        ),
        content=NewContentInput(topic="新品推广"),
    )

    graph = response.template.analysis_summary.shot_evidence_graph

    assert graph is not None
    assert graph.analysis_units
    assert graph.segments
    assert all(unit.shot_indices for unit in graph.analysis_units)
    assert all(segment.start <= segment.end for segment in graph.segments)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py::test_structure_preview_exposes_segment_unit_shot_hierarchy -q
```

Expected: FAIL，因为当前结构主轴暴露不完整或字段不稳定。

- [ ] **Step 3: 最小实现，统一后端主轴模型与默认构造**

实现要求：

- `shot_evidence_graph` 中的 `segments / analysis_units / shots` 必须稳定存在。
- `segment` 负责段落功能和时间范围。
- `analysis_unit` 负责 AI 理解与代表帧。
- `shot` 只保留物理镜头粒度和证据来源。

最小代码方向：

```python
def _normalize_graph_hierarchy(graph: ShotEvidenceGraph) -> ShotEvidenceGraph:
    graph.shots = graph.shots or []
    graph.analysis_units = graph.analysis_units or []
    graph.segments = graph.segments or []
    return graph
```

并在 `build_structure_preview()` 或相关 graph 汇总处统一调用。

- [ ] **Step 4: 给 unit / segment 增加稳定的职责说明字段**

要求：

- `analysis_unit` 必须有一句中文 `label / summary`
- `segment` 必须有中文 `label / purpose`
- 任何 fallback 都不能只返回空壳对象

- [ ] **Step 5: 跑结构相关测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_ai_video_structure_service.py -q
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/models.py services/api/app/video_understanding/schemas.py services/api/app/video_understanding/ai_structure_service.py services/api/app/video_understanding/shot_evidence_graph.py services/api/app/structure_service.py services/api/tests/test_structure_service.py services/api/tests/test_ai_video_structure_service.py
git commit -m "feat: unify segment unit shot hierarchy"
```

---

### Task 2: 增加结构覆盖率、缺口等级、可补全性评分

**Files:**
- Create: `services/api/app/structure_coverage_service.py`
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Test: `services/api/tests/test_structure_coverage_service.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: 写 failing 测试，约束 gaps 附带覆盖率和等级信息**

在 `services/api/tests/test_structure_coverage_service.py` 新增：

```python
from app.structure_coverage_service import score_structure_slot_coverage
from app.models import SlotQueryProfile, MaterialGraphSearchResult


def test_score_structure_slot_coverage_returns_gap_level_and_fillability():
    profile = SlotQueryProfile(
        slot_id="selling_points",
        slot_label="卖点展开",
        required_asset="商品特写镜头",
        visual_terms=["产品", "特写"],
        text_terms=["补水"],
        target_duration=3.0,
    )
    result = MaterialGraphSearchResult(
        slot_id="selling_points",
        asset_id="detail.mp4",
        chunk_id="chunk_a",
        start=1.0,
        end=3.6,
        matched_nodes=[],
        evidence_path=["命中产品特写"],
        missing=["缺少 OCR/ASR 文本证据"],
        score_breakdown={"visual": 20, "duration_fit": 14},
        confidence=0.54,
    )

    coverage = score_structure_slot_coverage(profile, [result])

    assert coverage.slot_id == "selling_points"
    assert 0 <= coverage.coverage_score <= 1
    assert coverage.gap_level in {"low", "medium", "high"}
    assert coverage.fillability in {"direct", "packaging", "reorder", "missing"}
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_coverage_service.py::test_score_structure_slot_coverage_returns_gap_level_and_fillability -q
```

Expected: FAIL，因为 service 和模型尚不存在。

- [ ] **Step 3: 在 `models.py` 中增加覆盖率结果模型**

新增：

```python
class StructureCoverageResult(BaseModel):
    slot_id: str = ""
    coverage_score: float = Field(default=0, ge=0, le=1)
    gap_level: Literal["low", "medium", "high"] = "high"
    fillability: Literal["direct", "packaging", "reorder", "missing"] = "missing"
    summary: str = ""
```

并在 `MaterialGap` 中加入：

```python
coverage_result: StructureCoverageResult = Field(default_factory=StructureCoverageResult)
```

- [ ] **Step 4: 实现 `structure_coverage_service.py`**

最小实现：

```python
from app.models import MaterialGraphSearchResult, SlotQueryProfile, StructureCoverageResult


def score_structure_slot_coverage(
    profile: SlotQueryProfile,
    results: list[MaterialGraphSearchResult],
) -> StructureCoverageResult:
    if not results:
        return StructureCoverageResult(
            slot_id=profile.slot_id,
            coverage_score=0,
            gap_level="high",
            fillability="missing",
            summary=f"{profile.slot_label or profile.slot_id} 当前没有可直接支撑的素材证据。",
        )

    best = results[0]
    coverage = round(best.confidence, 2)
    if coverage >= 0.75:
        level = "low"
        fillability = "direct"
    elif coverage >= 0.45:
        level = "medium"
        fillability = "packaging"
    else:
        level = "high"
        fillability = "reorder" if best.evidence_path else "missing"

    return StructureCoverageResult(
        slot_id=profile.slot_id,
        coverage_score=coverage,
        gap_level=level,
        fillability=fillability,
        summary=f"{profile.slot_label or profile.slot_id} 覆盖率 {round(coverage * 100)}%，缺口等级 {level}。",
    )
```

- [ ] **Step 5: 在 `build_material_gap()` 中接入覆盖率结果**

要求：

- 每个 `MaterialGap` 都要带 `coverage_result`
- `fill_strategy` 与 `slot_fill_decision` 的默认文案可参考 `coverage_result.fillability`

- [ ] **Step 6: 跑测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_coverage_service.py tests/test_structure_service.py -q
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/structure_coverage_service.py services/api/app/models.py services/api/app/structure_service.py services/api/tests/test_structure_coverage_service.py services/api/tests/test_structure_service.py
git commit -m "feat: add structure coverage scoring"
```

---

### Task 3: 强化多模态 evidence scoring 与 rerank 可解释性

**Files:**
- Modify: `services/api/app/material_graph_service.py`
- Modify: `services/api/app/material_rerank_service.py`
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_material_vector_store.py`

- [ ] **Step 1: 写 failing 测试，约束多模态命中优先于单一规则命中**

在 `services/api/tests/test_material_vector_store.py` 增加：

```python
def test_rerank_prefers_multimodal_evidence_over_single_signal():
    profile = SlotQueryProfile(
        slot_id="hook",
        slot_label="开头吸引镜头",
        visual_terms=["人物", "特写"],
        text_terms=["限时"],
        packaging_terms=["标题卡"],
        target_duration=2.5,
    )

    multimodal = MaterialGraphSearchResult(
        slot_id="hook",
        asset_id="a.mp4",
        chunk_id="chunk_a",
        start=0,
        end=2.4,
        matched_nodes=[],
        evidence_path=["视觉+OCR+包装共同命中"],
        missing=[],
        score_breakdown={"visual": 20, "ocr_asr": 25, "packaging": 15, "duration_fit": 14},
        confidence=0.62,
    )
    duration_only = MaterialGraphSearchResult(
        slot_id="hook",
        asset_id="b.mp4",
        chunk_id="chunk_b",
        start=0,
        end=2.5,
        matched_nodes=[],
        evidence_path=["只命中时长"],
        missing=["缺少画面和文本证据"],
        score_breakdown={"duration_fit": 15},
        confidence=0.7,
    )

    reranked = rerank_material_graph_results(profile, [duration_only, multimodal])

    assert reranked[0].asset_id == "a.mp4"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py::test_rerank_prefers_multimodal_evidence_over_single_signal -q
```

Expected: FAIL，如果当前 rerank 仍可能偏向单一高 confidence 结果。

- [ ] **Step 3: 调整 graph score breakdown 与 rerank bonus**

要求：

- 多模态同时命中应获得显著 bonus
- 单一 `duration_fit` 不能成为主要排序依据
- `missing` 越多，结果越应下沉

最小实现方向：

```python
def _multimodal_bonus(result: MaterialGraphSearchResult) -> int:
    present = sum(
        1
        for key in ("semantic", "visual", "ocr_asr", "packaging", "slot_hint")
        if result.score_breakdown.get(key, 0) > 0
    )
    return 12 if present >= 3 else 6 if present == 2 else 0
```

- [ ] **Step 4: 为结果补一行中文可解释摘要**

在模型或映射层增加：

```python
explanation = "命中视觉、文字和包装三类证据，可优先复用。"
```

用于前端默认显示。

- [ ] **Step 5: 跑测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_material_vector_store.py -q
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/material_graph_service.py services/api/app/material_rerank_service.py services/api/app/models.py services/api/tests/test_material_vector_store.py
git commit -m "feat: improve multimodal evidence scoring"
```

---

### Task 4: 把 timeline patch 从建议推进到结果执行映射

**Files:**
- Modify: `services/api/app/timeline_patch_service.py`
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/workflow_service.py`
- Test: `services/api/tests/test_structure_service.py`
- Test: `services/api/tests/test_workflow_service.py`

- [ ] **Step 1: 写 failing 测试，要求 patch 显式映射到结果时间线**

在 `services/api/tests/test_workflow_service.py` 增加：

```python
def test_transfer_result_contains_patch_applied_summary():
    response = build_structure_preview(
        sample=SampleVideoInput(title="样例", duration=20, shot_count=5),
        content=NewContentInput(
            topic="新品",
            uploaded_assets=[],
        ),
    )

    result = build_transfer_plan(
        template=response.template,
        content=NewContentInput(topic="新品"),
        gaps=response.transfer_plan.gaps,
    )

    assert any(mapping.fallback_strategy for mapping in result.mapping)
```

- [ ] **Step 2: 跑测试确认失败或不稳定**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_workflow_service.py::test_transfer_result_contains_patch_applied_summary -q
```

- [ ] **Step 3: 在 patch 模型中增加结果执行摘要**

在 `TimelinePatch` 加：

```python
execution_summary: str = ""
```

并在 `build_timeline_patch()` 中为三种 operation 生成明确中文摘要：

- `replace_slot_media`
- `insert_caption_card`
- `request_asset`

- [ ] **Step 4: 在 transfer mapping / result preview 中引用 patch 执行摘要**

要求：

- 用户能在结果层看到“这个槽位最终怎么处理”
- 不只是看到补全建议，而是看到已应用策略

- [ ] **Step 5: 跑测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_workflow_service.py -q
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/timeline_patch_service.py services/api/app/structure_service.py services/api/app/workflow_service.py services/api/tests/test_structure_service.py services/api/tests/test_workflow_service.py
git commit -m "feat: map timeline patch to transfer result"
```

---

### Task 5: 重构前端信息架构，增加结构覆盖率与评估摘要面板

**Files:**
- Create: `apps/web/src/components/Workspace/StructureCoveragePanel.tsx`
- Create: `apps/web/src/components/Workspace/EvaluationSummaryPanel.tsx`
- Modify: `apps/web/src/hooks/useReelStruct.ts`
- Modify: `apps/web/src/hooks/useReelStructApi.ts`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`
- Modify: `apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx`
- Modify: `apps/web/src/components/Workspace/MaterialGapPanel.tsx`
- Modify: `apps/web/src/components/Workspace/ResultPreviewPanel.tsx`
- Modify: `apps/web/src/components/Workspace/TransferExplanationPanel.tsx`
- Modify: `apps/web/src/app/globals.css`
- Test: `apps/web` typecheck

- [ ] **Step 1: 写一个前端 type 失败点，先补共享 view model 字段**

目标字段：

- `coverage_result`
- `execution_summary`
- `evaluation_summary`

在 `useReelStruct.ts` 和 `useReelStructApi.ts` 中补类型定义。

- [ ] **Step 2: 跑 typecheck 观察失败点**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: FAIL，直到新字段和面板接好。

- [ ] **Step 3: 新建 `StructureCoveragePanel.tsx`**

面板职责：

- 展示每个结构槽位的覆盖率
- 显示缺口等级
- 显示可补全性

最小组件形状：

```tsx
export default function StructureCoveragePanel({ items }: { items: Array<{
  slotId: string
  label: string
  coverageScore: number
  gapLevel: string
  fillability: string
  summary: string
}> }) {
  return null
}
```

- [ ] **Step 4: 新建 `EvaluationSummaryPanel.tsx`**

面板职责：

- 展示本次样例解析 / 素材补全 / 结果生成的摘要评估
- 默认只展示 3-5 条重点结论

- [ ] **Step 5: 重排 `WorkPanel.tsx` 信息主线**

新的展示顺序：

1. 结构概要
2. 段落时间线 / 图谱
3. 素材覆盖率
4. 素材缺口与补全
5. 迁移解释
6. 结果预览

- [ ] **Step 6: 收缩 `MaterialGapPanel.tsx` 默认信息量**

要求：

- 默认显示：槽位需求 / 覆盖率 / 推荐决策 / 已应用结果
- `graphSearchResults`、`timelinePatches`、`evidencePath` 保留在展开层

- [ ] **Step 7: 跑 typecheck**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/apps/web
npm run typecheck
```

Expected: PASS

- [ ] **Step 8: 浏览器 smoke**

验证项：

- 页面可以正常打开
- 没有 runtime overlay
- 能看到“素材覆盖率”“缺口等级”“已应用结果”三类信息

- [ ] **Step 9: 提交**

```bash
cd /Users/linkwind/Code/ReelStruct
git add apps/web/src/hooks/useReelStruct.ts apps/web/src/hooks/useReelStructApi.ts apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/components/Workspace/WorkPanel.tsx apps/web/src/components/Workspace/AnalysisSummaryPanel.tsx apps/web/src/components/Workspace/MaterialGapPanel.tsx apps/web/src/components/Workspace/ResultPreviewPanel.tsx apps/web/src/components/Workspace/TransferExplanationPanel.tsx apps/web/src/components/Workspace/StructureCoveragePanel.tsx apps/web/src/components/Workspace/EvaluationSummaryPanel.tsx apps/web/src/app/globals.css
git commit -m "feat: clarify workspace information architecture"
```

---

### Task 6: 建立最小评估体系

**Files:**
- Create: `services/api/app/evaluation_service.py`
- Modify: `services/api/app/models.py`
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/workflow_service.py`
- Create: `services/api/tests/test_evaluation_service.py`
- Modify: `services/api/tests/test_workflow_service.py`

- [ ] **Step 1: 写 failing 测试，要求 workflow 响应带评估摘要**

在 `services/api/tests/test_evaluation_service.py` 新增：

```python
from app.evaluation_service import build_evaluation_summary


def test_build_evaluation_summary_returns_compact_sections():
    summary = build_evaluation_summary(
        structure_quality="medium",
        retrieval_quality="low",
        completion_quality="medium",
        result_quality="low",
    )

    assert summary.headline
    assert len(summary.highlights) >= 3
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_evaluation_service.py::test_build_evaluation_summary_returns_compact_sections -q
```

- [ ] **Step 3: 在 `models.py` 中新增评估摘要模型**

```python
class EvaluationSummary(BaseModel):
    headline: str = ""
    highlights: list[str] = Field(default_factory=list)
    structure_quality: Literal["low", "medium", "high"] = "low"
    retrieval_quality: Literal["low", "medium", "high"] = "low"
    completion_quality: Literal["low", "medium", "high"] = "low"
    result_quality: Literal["low", "medium", "high"] = "low"
```

- [ ] **Step 4: 实现 `build_evaluation_summary()`**

要求：

- 输出中文摘要
- 能把结构、检索、补全、结果四维质量汇总成 3-5 条结论

- [ ] **Step 5: 在 preview / workflow 结果中挂出评估摘要**

要求：

- 前端拿到 `evaluation_summary`
- 不影响旧字段兼容

- [ ] **Step 6: 跑测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_evaluation_service.py tests/test_workflow_service.py -q
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd /Users/linkwind/Code/ReelStruct
git add services/api/app/evaluation_service.py services/api/app/models.py services/api/app/structure_service.py services/api/app/workflow_service.py services/api/tests/test_evaluation_service.py services/api/tests/test_workflow_service.py
git commit -m "feat: add evaluation summary pipeline"
```

---

## Self-Review

### Spec coverage

本计划覆盖了未完成问题文档中的 5 个 P0：

- 统一结构主轴
- 结构覆盖率 / 缺口等级
- 强化多模态 evidence scoring
- timeline patch 执行映射
- 前端信息架构重构
- 最小评估体系

### Placeholder scan

- 没有使用 `TODO`、`TBD`、`后续实现` 之类占位语。
- 每个任务都给出了文件、测试、命令和预期。

### Type consistency

- 统一使用：
  - `coverage_result`
  - `StructureCoverageResult`
  - `evaluation_summary`
  - `EvaluationSummary`
  - `execution_summary`

没有在不同任务中混用命名。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-project-open-issues-execution-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
