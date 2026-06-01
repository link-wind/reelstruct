# ReelStruct 重构二期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 ReelStruct 当前行为和 API 语义的前提下，完成后端模型契约分层，把 `services/api/app/models.py` 从共享模型桶收成 `api / domain / workflow` 三层结构。

**Architecture:** 先建立新的模型分层文件，再按 `domain -> workflow -> tools -> routes` 的顺序回收 import，期间保留 `models.py` 作为短期兼容聚合出口，避免一次性替换引发导入回归。二期重点是契约归位，不做 route 改版、workflow 重写或 tool 协议重设。

**Tech Stack:** FastAPI, Pydantic, pytest

---

## File Structure

### 当前重点文件

- `services/api/app/models.py`
  当前共享模型桶，混合 API、domain、workflow、run/template/export 契约。

- `services/api/app/main.py`
  FastAPI route 聚合入口，直接依赖多类请求/响应模型。

- `services/api/app/workflow_service.py`
  workflow 主链路，当前仍从 `models.py` 取大量中间态与结果模型。

- `services/api/app/tools/analyze_structure.py`
- `services/api/app/tools/complete_materials.py`
- `services/api/app/tools/generate_result.py`
- `services/api/app/tools/run_ocr.py`
- `services/api/app/tools/run_asr.py`
  当前 tool 层入口，后续需要回收到正确模型层。

- `services/api/app/domain/structure/*.py`
  一期已拆出的 structure builder，二期应优先改成依赖 `domain_models`。

### 二期目标新增文件

- `services/api/app/api/api_models.py`
  只放 FastAPI 请求体、响应体、route 直接暴露对象。

- `services/api/app/domain/shared/domain_models.py`
  只放 structure/material/composition 等领域对象。

- `services/api/app/workflow/workflow_models.py`
  只放 workflow / tool / run 过程型模型。

- `services/api/app/api/__init__.py`
- `services/api/app/domain/shared/__init__.py`
- `services/api/app/workflow/__init__.py`
  轻量包入口，方便按层导入。

### 二期仍暂时保留的文件

- `services/api/app/models.py`
  先退化成兼容聚合层，不再新增定义。

### 核心验证命令

- 主链路回归：`cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py tests/test_workflow_service.py -q`
- 结构迁移与接口回归：`cd /Users/linkwind/Code/ReelStruct/services/api && OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py tests/test_transfer_planner.py tests/test_material_gap_builder.py -q`
- 语法与导入检查：`cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m py_compile app/structure_service.py app/domain/structure/transfer_planner.py app/domain/structure/material_gap_builder.py app/workflow_service.py app/main.py`

### 行为不变边界

- `/api/structure/preview` 等现有 route 路径不变
- agent/tool 主流程不变
- `analyze_structure / run_ocr / run_asr / complete_materials / generate_result` 契约语义不变
- run / template / export 的现有结果语义不变

## Task 1: 建立模型分层文件骨架

**Files:**
- Create: `services/api/app/api/__init__.py`
- Create: `services/api/app/api/api_models.py`
- Create: `services/api/app/domain/shared/__init__.py`
- Create: `services/api/app/domain/shared/domain_models.py`
- Create: `services/api/app/workflow/__init__.py`
- Create: `services/api/app/workflow/workflow_models.py`
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: 写失败测试，约束兼容出口仍可工作**

```python
from app.domain.shared.domain_models import StructureSlot, TemplateStructure
from app.api.api_models import StructurePreviewRequest, StructurePreviewResponse
from app.workflow.workflow_models import RunTraceEvent


def test_phase2_model_split_exports_are_available():
    assert StructureSlot.__name__ == "StructureSlot"
    assert TemplateStructure.__name__ == "TemplateStructure"
    assert StructurePreviewRequest.__name__ == "StructurePreviewRequest"
    assert StructurePreviewResponse.__name__ == "StructurePreviewResponse"
    assert RunTraceEvent.__name__ == "RunTraceEvent"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_model_split.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'app.domain.shared.domain_models'
```

- [ ] **Step 3: 建立新包和初始模型归类**

先创建最小骨架，并把下面这些类迁到对应层：

```python
# services/api/app/domain/shared/domain_models.py
from app.models import (
    CompositionSpec,
    CompositionTrack,
    MaterialGap,
    MaterialGraph,
    MaterialGraphEdge,
    MaterialGraphMatchedNode,
    MaterialGraphNode,
    MaterialGraphSearchResult,
    MaterialRequestTask,
    MaterialRetrievalCandidate,
    MaterialSupplementOption,
    NewContentInput,
    PackagingPlan,
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    SampleVideoInput,
    SlotFillDecision,
    SlotQueryProfile,
    SlotRetrievalPlan,
    StructureCoverageResult,
    StructureSlot,
    SupplementSelection,
    TemplateStructure,
    TimelinePatch,
    TimelineTrackUpdate,
    TransferExplanation,
    TransferMapping,
    TransferMappingOverride,
    TransferPlan,
    UserSlotAsset,
)
```

```python
# services/api/app/api/api_models.py
from app.models import (
    CreateTemplateFromRunRequest,
    DemoRunResponse,
    DemoVariantRunsResponse,
    MaterialEvidenceChunk,
    MaterialFitAnalysis,
    PrepareDemoAssetsResponse,
    PreviewRunRequest,
    RenderClipPreview,
    RenderDemoResponse,
    RunBatchResponse,
    RunNoteUpdateRequest,
    RunPinUpdateRequest,
    RunPreferredUpdateRequest,
    RunRecordSummary,
    SampleEvidenceRequest,
    SampleUploadResponse,
    StructurePreviewRequest,
    StructurePreviewResponse,
    StructureTemplateRecord,
    StructureTemplateSummary,
    StructureTemplateVersion,
    StructureVariantSummary,
    StructureVariantsResponse,
    TranscriptUploadResponse,
    UpdateStructureTemplateRequest,
    UpdateStructureTemplateSlotRequest,
)
```

```python
# services/api/app/workflow/workflow_models.py
from app.models import EvaluationSummary, RunTraceEvent
```

并在 `services/api/app/models.py` 里临时增加兼容 re-export：

```python
from app.api.api_models import *
from app.domain.shared.domain_models import *
from app.workflow.workflow_models import *
```

- [ ] **Step 4: 跑新测试确认通过**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_model_split.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 跑兼容验证**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py tests/test_transfer_planner.py tests/test_material_gap_builder.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 6: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/app/api /Users/linkwind/Code/ReelStruct/services/api/app/domain/shared /Users/linkwind/Code/ReelStruct/services/api/app/workflow /Users/linkwind/Code/ReelStruct/services/api/app/models.py /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase2_model_split.py
git commit -m "refactor: add phase 2 model layer skeleton"
```

## Task 2: 回收 structure domain 对 models.py 的依赖

**Files:**
- Modify: `services/api/app/domain/structure/input_normalizer.py`
- Modify: `services/api/app/domain/structure/template_builder.py`
- Modify: `services/api/app/domain/structure/transfer_planner.py`
- Modify: `services/api/app/domain/structure/material_gap_builder.py`
- Modify: `services/api/app/domain/structure/composition_builder.py`
- Test: `services/api/tests/test_input_normalizer.py`
- Test: `services/api/tests/test_template_builder.py`
- Test: `services/api/tests/test_transfer_planner.py`
- Test: `services/api/tests/test_material_gap_builder.py`
- Test: `services/api/tests/test_composition_builder.py`

- [ ] **Step 1: 写失败测试，先建立一个最小 domain import 骨架测试**

```python
from app.domain.shared.domain_models import StructureSlot, TransferPlan


def test_domain_models_exports_structure_contracts():
    assert StructureSlot.__name__ == "StructureSlot"
    assert TransferPlan.__name__ == "TransferPlan"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_domain_imports.py -q
```

Expected:

```text
如果 Task 1 尚未完成则 import fail；如果 Task 1 已完成则先 PASS，再继续做 Step 3 的导入迁移
```

- [ ] **Step 3: 最小改动回收 domain imports**

把这些文件的导入从：

```python
from app.models import ...
```

改成：

```python
from app.domain.shared.domain_models import ...
```

要求：

- 只改导入来源
- 不改 builder 逻辑
- 如果某个对象还没归类到 domain layer，先补到 `domain_models.py`

- [ ] **Step 4: 跑对应 builder 测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_input_normalizer.py tests/test_template_builder.py tests/test_transfer_planner.py tests/test_material_gap_builder.py tests/test_composition_builder.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 5: 跑 structure 主链路回归**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py tests/test_transfer_planner.py tests/test_material_gap_builder.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 6: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/app/domain/structure /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase2_domain_imports.py
git commit -m "refactor: move structure builders to domain models"
```

## Task 3: 回收 workflow_service 和 tool 层的模型依赖

**Files:**
- Modify: `services/api/app/workflow_service.py`
- Modify: `services/api/app/tools/analyze_structure.py`
- Modify: `services/api/app/tools/complete_materials.py`
- Modify: `services/api/app/tools/generate_result.py`
- Modify: `services/api/app/tools/run_ocr.py`
- Modify: `services/api/app/tools/run_asr.py`
- Modify: `services/api/app/evaluation_service.py`
- Test: `services/api/tests/test_workflow_service.py`
- Test: `services/api/tests/test_tool_executor.py`
- Test: `services/api/tests/test_agent_orchestrator.py`

- [ ] **Step 1: 写失败测试，先建立 workflow model 骨架测试**

```python
from app.workflow.workflow_models import EvaluationSummary, RunTraceEvent


def test_workflow_layer_exports_process_models():
    assert EvaluationSummary.__name__ == "EvaluationSummary"
    assert RunTraceEvent.__name__ == "RunTraceEvent"
```

- [ ] **Step 2: 跑测试确认当前约束未完全满足**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_workflow_imports.py -q
```

Expected:

```text
如果 Task 1 尚未完成则 import fail；如果 Task 1 已完成则先 PASS，再继续做 Step 3 的导入迁移
```

- [ ] **Step 3: 回收 workflow/tool 导入来源**

把 workflow / tools / evaluation service 中的：

- 过程型对象改从 `app.workflow.workflow_models` 导入
- 纯领域对象改从 `app.domain.shared.domain_models` 导入
- 仍然属于 API 契约的对象先不在这一步迁去 route 层

只做 import 归位，不改函数语义。

- [ ] **Step 4: 跑 workflow/tool 测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py tests/test_workflow_service.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 5: 跑结构链路交叉回归**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py tests/test_transfer_planner.py tests/test_material_gap_builder.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 6: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/app/workflow_service.py /Users/linkwind/Code/ReelStruct/services/api/app/evaluation_service.py /Users/linkwind/Code/ReelStruct/services/api/app/tools /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase2_workflow_imports.py
git commit -m "refactor: move workflow and tool imports to layered models"
```

## Task 4: 回收 route 层和 API 契约，并冻结 models.py

**Files:**
- Modify: `services/api/app/main.py`
- Modify: `services/api/app/sample_service.py`
- Modify: `services/api/app/sample_evidence_service.py`
- Modify: `services/api/app/material_asset_service.py`
- Modify: `services/api/app/material_evidence_service.py`
- Modify: `services/api/app/run_record_service.py`
- Modify: `services/api/app/run_export_service.py`
- Modify: `services/api/app/template_record_service.py`
- Modify: `services/api/app/models.py`
- Test: `services/api/tests/test_media_api.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: 写失败测试，先建立 api model 骨架测试**

```python
from app.api.api_models import StructurePreviewRequest, StructurePreviewResponse


def test_api_models_export_route_contracts():
    assert StructurePreviewRequest.__name__ == "StructurePreviewRequest"
    assert StructurePreviewResponse.__name__ == "StructurePreviewResponse"
```

- [ ] **Step 2: 跑测试确认失败或未完成**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_api_imports.py -q
```

Expected:

```text
如果 Task 1 尚未完成则 import fail；如果 Task 1 已完成则先 PASS，再继续做 Step 3 的 route 导入迁移
```

- [ ] **Step 3: 回收 route 与 service 的 API imports**

把 `main.py` 和直接承接 route payload 的 service 改成：

```python
from app.api.api_models import ...
```

同时把 `models.py` 缩成兼容聚合层，并在文件头加一个短注释：

```python
# Phase 2 compatibility layer. Do not add new model definitions here.
```

要求：

- 不在这一步删除 `models.py`
- 不新增业务字段
- 不改变 route 定义和响应结构

- [ ] **Step 4: 跑 route / media / structure 回归**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 5: 跑语法与导入检查**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m py_compile app/structure_service.py app/domain/structure/transfer_planner.py app/domain/structure/material_gap_builder.py app/workflow_service.py app/main.py
```

Expected:

```text
no output
```

- [ ] **Step 6: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/app/main.py /Users/linkwind/Code/ReelStruct/services/api/app/sample_service.py /Users/linkwind/Code/ReelStruct/services/api/app/sample_evidence_service.py /Users/linkwind/Code/ReelStruct/services/api/app/material_asset_service.py /Users/linkwind/Code/ReelStruct/services/api/app/material_evidence_service.py /Users/linkwind/Code/ReelStruct/services/api/app/run_record_service.py /Users/linkwind/Code/ReelStruct/services/api/app/run_export_service.py /Users/linkwind/Code/ReelStruct/services/api/app/template_record_service.py /Users/linkwind/Code/ReelStruct/services/api/app/models.py /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase2_api_imports.py
git commit -m "refactor: move route contracts to api models"
```

## Task 5: 二期收尾与兼容层决策

**Files:**
- Modify: `services/api/app/models.py`
- Modify: `docs/superpowers/specs/2026-05-31-reelstruct-refactor-phase-2-design.md`
- Modify: `docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-2.md`

- [ ] **Step 1: 统计仍然依赖 `app.models` 的文件**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
rg -n "from app\\.models import|import app\\.models" services/api/app services/api/tests
```

Expected:

```text
只剩少量兼容引用，且都能解释原因
```

- [ ] **Step 2: 根据结果做兼容层决策**

如果只剩极少量兼容引用：

```text
保持 models.py 为极薄聚合层，并在文档中标明“禁止新增定义”
```

如果仍有较多历史引用：

```text
保留 models.py 作为兼容出口，但把“继续回收剩余引用”记录为三期输入，不强行在二期清零
```

- [ ] **Step 3: 跑完整后端验证**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py tests/test_workflow_service.py -q
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py tests/test_transfer_planner.py tests/test_material_gap_builder.py -q
PYTHONPATH=. .venv/bin/python -m py_compile app/structure_service.py app/domain/structure/transfer_planner.py app/domain/structure/material_gap_builder.py app/workflow_service.py app/main.py
```

Expected:

```text
all passed
```

- [ ] **Step 4: 更新文档里的完成状态**

在 spec / plan 里补一段简短结果说明：

```text
二期完成后，models.py 已不再作为新增模型默认落点；domain / workflow / api 模型边界已建立；兼容层是否保留按最终迁移结果决定。
```

Task 5 实际结果（2026-06-01）：

- `api / domain / workflow` 三层 facade 已建立，并分别由 `test_phase2_model_split.py`、`test_phase2_domain_imports.py`、`test_phase2_workflow_imports.py`、`test_phase2_api_imports.py` 守住导入回归
- 二期完成的是“导入边界收口”和“兼容层冻结”，不是在这一轮把所有模型定义物理迁出 `app/models.py`；当前 source of truth 仍然是 `app.models`
- `main.py`、`workflow_service.py`、`tools/*`、`domain/structure/*` 的关键导入已回收到分层入口
- `models.py` 已明确标记为兼容层，不再作为新增模型默认落点
- 由于后端实现层仍有 14 处 `app.models` 兼容引用，其中 3 处是 facade 自身 re-export，11 处是后续待回收的历史实现模块，因此二期结论是“保留 `models.py` 作为薄兼容入口，剩余引用留给下一阶段”
- `test_phase2_legacy_model_inventory.py` 显式锁住了当前允许保留的 legacy `app.models` 实现层引用面，避免二期之后又把旧桶依赖扩回去

本轮统计到的后续输入主要包括：

- `structure_service.py`
- `fixture_asset_service.py`
- `material_graph_service.py`
- `material_rag_service.py`
- `material_rerank_service.py`
- `slot_profile_service.py`
- `structure_coverage_service.py`
- `timeline_patch_service.py`
- `video_understanding/pipeline.py`
- `video_understanding/template_adapter.py`
- `video_understanding/transfer_explainer_service.py`

- [ ] **Step 5: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/app/models.py /Users/linkwind/Code/ReelStruct/docs/superpowers/specs/2026-05-31-reelstruct-refactor-phase-2-design.md /Users/linkwind/Code/ReelStruct/docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-2.md
git commit -m "docs: finalize phase 2 model layering plan"
```
