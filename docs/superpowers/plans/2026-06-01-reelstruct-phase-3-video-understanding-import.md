# ReelStruct Phase 3: video_understanding Import Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `services/api/app/video_understanding/pipeline.py` 和 `services/api/app/video_understanding/template_adapter.py` 脱离对 `app.models` 的直接依赖，改为使用 `app.domain.shared.domain_models`，同时保持 AI 结构拆解和模板组装行为不变。

**Architecture:** 这一轮不改 AI 图谱生成、fallback 或 template 组装逻辑，只做导入归位和回归护栏补强。`pipeline.py` 里的 `SampleVideoInput`、`TemplateStructure` 改从 `domain.shared.domain_models` 导入；`template_adapter.py` 里的结构/分析/图谱表现对象也统一改走 `domain.shared.domain_models`。再通过 phase3 定向导入测试和 legacy inventory 把这两个文件从旧桶依赖面里移除。

**Tech Stack:** Python, Pydantic, pytest

---

## File Structure

### 本轮修改文件

- Modify: `services/api/app/video_understanding/pipeline.py`
  - 只调整 `SampleVideoInput`、`TemplateStructure` 的导入来源。

- Modify: `services/api/app/video_understanding/template_adapter.py`
  - 只调整 8 个领域对象的导入来源。

- Create: `services/api/tests/test_phase3_video_understanding_imports.py`
  - 新增 AST 级定向导入测试，锁住这两个文件的正确 facade 来源。

- Modify: `services/api/tests/test_phase2_legacy_model_inventory.py`
  - 把 `video_understanding/pipeline.py` 和 `video_understanding/template_adapter.py` 从允许继续依赖 `app.models` 的清单中移除。

### 本轮验证文件

- Test: `services/api/tests/test_video_understanding_pipeline.py`
- Test: `services/api/tests/test_phase3_video_understanding_imports.py`
- Test: `services/api/tests/test_phase2_legacy_model_inventory.py`

### 行为不变边界

- 不改 `services/api/app/video_understanding/transfer_explainer_service.py`
- 不改 `services/api/app/video_understanding/schemas.py`
- 不改 `services/api/app/structure_service.py`
- 不改 `adapt_ai_structure_to_template()`、`adapt_graph_segments_to_template()` 的函数体逻辑
- 不改 `build_ai_structure_template()` / `build_fallback_structure_template()` / `build_ai_or_fallback_structure_template()` 的业务流程

## Task 1: 为 video_understanding 导入归位建立失败测试

**Files:**
- Create: `services/api/tests/test_phase3_video_understanding_imports.py`
- Test: `services/api/tests/test_phase2_legacy_model_inventory.py`

- [ ] **Step 1: 写 AST 级导入测试**

```python
import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app" / "video_understanding"

PIPELINE_DOMAIN_NAMES = {
    "SampleVideoInput",
    "TemplateStructure",
}

TEMPLATE_ADAPTER_DOMAIN_NAMES = {
    "GraphPresentationEdge",
    "GraphPresentationNode",
    "GraphPresentationSummary",
    "SampleAnalysisBeat",
    "SampleAnalysisMetric",
    "SampleAnalysisSummary",
    "StructureSlot",
    "TemplateStructure",
}


def test_pipeline_imports_domain_models_from_split_facade():
    imported_by_module = _imports_by_module(APP_ROOT / "pipeline.py")
    assert imported_by_module.get("app.domain.shared.domain_models", set()) == PIPELINE_DOMAIN_NAMES
    _assert_no_legacy_models_import(APP_ROOT / "pipeline.py")


def test_template_adapter_imports_domain_models_from_split_facade():
    imported_by_module = _imports_by_module(APP_ROOT / "template_adapter.py")
    assert imported_by_module.get("app.domain.shared.domain_models", set()) == TEMPLATE_ADAPTER_DOMAIN_NAMES
    _assert_no_legacy_models_import(APP_ROOT / "template_adapter.py")


def _imports_by_module(path: Path) -> dict[str, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_by_module: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_by_module.setdefault(node.module, set()).update(alias.asname or alias.name for alias in node.names)
    return imported_by_module


def _assert_no_legacy_models_import(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "app.models"
            assert not (node.module == "app" and any(alias.name == "models" for alias in node.names))
        if isinstance(node, ast.Import):
            assert all(alias.name != "app.models" for alias in node.names)
```

- [ ] **Step 2: 跑新测试，确认当前失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_video_understanding_imports.py -q
```

Expected:

```text
FAIL，提示 `pipeline.py` 或 `template_adapter.py` 仍然从 `app.models` 导入
```

- [ ] **Step 3: 跑 inventory 测试，记录当前基线**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_legacy_model_inventory.py -q
```

Expected:

```text
PASS，且允许列表里当前还包含 `video_understanding/pipeline.py` 和 `video_understanding/template_adapter.py`
```

## Task 2: 迁移 pipeline / template_adapter 导入并更新 legacy inventory

**Files:**
- Modify: `services/api/app/video_understanding/pipeline.py`
- Modify: `services/api/app/video_understanding/template_adapter.py`
- Modify: `services/api/tests/test_phase2_legacy_model_inventory.py`
- Test: `services/api/tests/test_video_understanding_pipeline.py`
- Test: `services/api/tests/test_phase3_video_understanding_imports.py`

- [ ] **Step 1: 改 pipeline.py 的导入来源**

把文件头从：

```python
from app.models import SampleVideoInput, TemplateStructure
```

改成：

```python
from app.domain.shared.domain_models import SampleVideoInput, TemplateStructure
```

要求：

- 只改导入来源
- 不改函数体逻辑

- [ ] **Step 2: 改 template_adapter.py 的导入来源**

把文件头从：

```python
from app.models import (
    GraphPresentationEdge,
    GraphPresentationNode,
    GraphPresentationSummary,
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    StructureSlot,
    TemplateStructure,
)
```

改成：

```python
from app.domain.shared.domain_models import (
    GraphPresentationEdge,
    GraphPresentationNode,
    GraphPresentationSummary,
    SampleAnalysisBeat,
    SampleAnalysisMetric,
    SampleAnalysisSummary,
    StructureSlot,
    TemplateStructure,
)
```

- [ ] **Step 3: 从 legacy inventory 里移除这两个文件**

把 `services/api/tests/test_phase2_legacy_model_inventory.py` 的允许集合从：

```python
ALLOWED_LEGACY_MODEL_IMPORT_FILES = {
    "api/api_models.py",
    "domain/shared/domain_models.py",
    "fixture_asset_service.py",
    "material_graph_service.py",
    "material_rag_service.py",
    "material_rerank_service.py",
    "slot_profile_service.py",
    "structure_coverage_service.py",
    "timeline_patch_service.py",
    "video_understanding/pipeline.py",
    "video_understanding/template_adapter.py",
    "video_understanding/transfer_explainer_service.py",
    "workflow/workflow_models.py",
}
```

改成：

```python
ALLOWED_LEGACY_MODEL_IMPORT_FILES = {
    "api/api_models.py",
    "domain/shared/domain_models.py",
    "fixture_asset_service.py",
    "material_graph_service.py",
    "material_rag_service.py",
    "material_rerank_service.py",
    "slot_profile_service.py",
    "structure_coverage_service.py",
    "timeline_patch_service.py",
    "video_understanding/transfer_explainer_service.py",
    "workflow/workflow_models.py",
}
```

- [ ] **Step 4: 跑 phase3 导入测试和 inventory**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_video_understanding_imports.py tests/test_phase2_legacy_model_inventory.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: 跑 video_understanding 主链路回归**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_video_understanding_pipeline.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 6: 跑语法检查**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m py_compile app/video_understanding/pipeline.py app/video_understanding/template_adapter.py
```

Expected:

```text
no output
```

## Task 3: 做一轮组合验证并锁边界

**Files:**
- Test: `services/api/tests/test_phase3_video_understanding_imports.py`
- Test: `services/api/tests/test_phase2_legacy_model_inventory.py`
- Test: `services/api/tests/test_video_understanding_pipeline.py`

- [ ] **Step 1: 组合跑本轮全部相关测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_video_understanding_imports.py tests/test_phase2_legacy_model_inventory.py tests/test_video_understanding_pipeline.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 2: 复查两个文件不再出现在 legacy import 面**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
rg -n "from app\\.models import|from app import models" services/api/app/video_understanding/pipeline.py services/api/app/video_understanding/template_adapter.py services/api/tests/test_phase2_legacy_model_inventory.py
```

Expected:

```text
`pipeline.py` 和 `template_adapter.py` 无命中；inventory 测试文件只保留断言代码本身
```
