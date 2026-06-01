# ReelStruct Phase 3: structure_service Import Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `services/api/app/structure_service.py` 脱离对 `app.models` 的直接依赖，改为使用已经建立好的 `domain / api` facade，同时保持结构预览行为不变。

**Architecture:** 这一轮不改 `build_structure_preview()` 的业务流程，只做导入归位和回归护栏补强。`structure_service.py` 中的领域对象改从 `app.domain.shared.domain_models` 导入，API 返回契约改从 `app.api.api_models` 导入，再通过 inventory 测试把它从 legacy `app.models` 白名单中移除。

**Tech Stack:** Python, Pydantic, pytest

---

## File Structure

### 本轮修改文件

- Modify: `services/api/app/structure_service.py`
  - 只调整类型导入来源，不改 `build_structure_preview()` 的执行顺序和返回值装配逻辑。

- Create: `services/api/tests/test_phase3_structure_service_imports.py`
  - 新增定向导入测试，锁住 `structure_service.py` 的正确 facade 来源和错误 legacy 来源。

- Modify: `services/api/tests/test_phase2_legacy_model_inventory.py`
  - 从允许保留 `app.models` 依赖的清单里移除 `structure_service.py`。

### 本轮验证文件

- Test: `services/api/tests/test_structure_service.py`
- Test: `services/api/tests/test_phase3_structure_service_imports.py`
- Test: `services/api/tests/test_phase2_legacy_model_inventory.py`

### 行为不变边界

- 不改 `services/api/app/domain/structure/*`
- 不改 `services/api/app/video_understanding/transfer_explainer_service.py`
- 不顺手迁移 `fixture_asset_service.py`、`timeline_patch_service.py`、`structure_coverage_service.py`
- 不改 `StructurePreviewResponse` 的字段和序列化语义

## Task 1: 为 structure_service 导入归位建立失败测试

**Files:**
- Create: `services/api/tests/test_phase3_structure_service_imports.py`
- Test: `services/api/tests/test_phase2_legacy_model_inventory.py`

- [ ] **Step 1: 写 structure_service 定向导入测试**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "app"


def test_phase3_structure_service_imports_use_split_facades():
    source = (ROOT / "structure_service.py").read_text(encoding="utf-8")

    assert "from app.domain.shared.domain_models import (" in source
    assert "MaterialRequestTask" in source
    assert "NewContentInput" in source
    assert "SampleVideoInput" in source
    assert "TemplateStructure" in source
    assert "SupplementSelection" in source
    assert "TransferMappingOverride" in source

    assert "from app.api.api_models import StructurePreviewResponse" in source

    assert "from app.models import" not in source
    assert "from app import models" not in source
```

- [ ] **Step 2: 跑新测试，确认当前失败**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_structure_service_imports.py -q
```

Expected:

```text
FAIL，提示 `structure_service.py` 仍然包含 `from app.models import`
```

- [ ] **Step 3: 先跑 inventory 测试，记录当前基线**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_legacy_model_inventory.py -q
```

Expected:

```text
PASS，且允许列表里当前还包含 `structure_service.py`
```

- [ ] **Step 4: 提交失败测试**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase3_structure_service_imports.py
git commit -m "test: add structure_service import regression guard"
```

## Task 2: 迁移 structure_service 导入并更新 legacy inventory

**Files:**
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/tests/test_phase2_legacy_model_inventory.py`
- Test: `services/api/tests/test_structure_service.py`
- Test: `services/api/tests/test_phase3_structure_service_imports.py`

- [ ] **Step 1: 改 structure_service.py 的导入来源**

把文件头的模型导入改成下面这样：

```python
from typing import Optional

from app.api.api_models import StructurePreviewResponse
from app.domain.shared.domain_models import (
    MaterialRequestTask,
    NewContentInput,
    SampleVideoInput,
    SupplementSelection,
    TemplateStructure,
    TransferMappingOverride,
)
from app.domain.structure.composition_builder import build_composition_spec
from app.domain.structure.input_normalizer import (
    apply_delivered_material_tasks_to_content,
    apply_uploaded_slot_assets_to_content,
)
from app.domain.structure.material_gap_builder import detect_material_gaps
from app.domain.structure.template_builder import (
    apply_slot_level_overrides,
    apply_variant_to_template,
    extract_template_structure,
)
from app.domain.structure.transfer_planner import build_transfer_plan
from app.evaluation_service import build_preview_evaluation_summary
from app.video_understanding.transfer_explainer_service import explain_transfer_with_ai
```

要求：

- 删除 `from app.models import (...)`
- `build_structure_preview()` 函数体保持原样

- [ ] **Step 2: 从 legacy inventory 里移除 structure_service.py**

把 `services/api/tests/test_phase2_legacy_model_inventory.py` 里的允许集合从：

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
    "structure_service.py",
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
    "video_understanding/pipeline.py",
    "video_understanding/template_adapter.py",
    "video_understanding/transfer_explainer_service.py",
    "workflow/workflow_models.py",
}
```

- [ ] **Step 3: 跑定向导入与 inventory 测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_structure_service_imports.py tests/test_phase2_legacy_model_inventory.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 4: 跑 structure_service 主链路回归**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 5: 跑语法检查**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m py_compile app/structure_service.py
```

Expected:

```text
no output
```

- [ ] **Step 6: 提交导入迁移**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/app/structure_service.py /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase3_structure_service_imports.py /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase2_legacy_model_inventory.py
git commit -m "refactor: move structure_service imports to layered models"
```

## Task 3: 做一轮 phase3 收尾验证

**Files:**
- Test: `services/api/tests/test_phase3_structure_service_imports.py`
- Test: `services/api/tests/test_phase2_legacy_model_inventory.py`
- Test: `services/api/tests/test_structure_service.py`

- [ ] **Step 1: 组合跑本轮全部相关测试**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_structure_service_imports.py tests/test_phase2_legacy_model_inventory.py tests/test_structure_service.py -q
```

Expected:

```text
all passed
```

- [ ] **Step 2: 复查 structure_service 不再出现在 legacy import 面**

Run:

```bash
cd /Users/linkwind/Code/ReelStruct
rg -n "from app\\.models import|from app import models" services/api/app/structure_service.py services/api/tests/test_phase2_legacy_model_inventory.py
```

Expected:

```text
`structure_service.py` 无命中；inventory 测试文件只保留断言代码本身
```

- [ ] **Step 3: 提交收尾验证记录**

```bash
git add /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase2_legacy_model_inventory.py /Users/linkwind/Code/ReelStruct/services/api/tests/test_phase3_structure_service_imports.py /Users/linkwind/Code/ReelStruct/services/api/app/structure_service.py
git commit -m "test: lock structure_service legacy model boundary"
```
