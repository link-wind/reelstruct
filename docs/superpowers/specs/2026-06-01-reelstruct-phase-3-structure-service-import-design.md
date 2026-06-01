# ReelStruct 重构三期：structure_service 导入收口设计

日期：2026-06-01

## 1. 目标

这一轮只做一个很窄的动作：

**把 `services/api/app/structure_service.py` 对 `app.models` 的直接依赖，回收到已经建立好的分层 facade。**

范围只限 `structure_service.py` 本身，不扩到 `fixture_asset_service.py`、`timeline_patch_service.py`、`structure_coverage_service.py` 等相邻实现层。

## 2. 当前现状

`structure_service.py` 当前已经是一个装配入口：

- 调 `domain/structure/*` builder 生成 template、gap、transfer plan、composition
- 调 `evaluation_service.py` 生成 `evaluation_summary`
- 在 `use_ai_transfer_explanation=True` 时调 `transfer_explainer_service.py`

但它仍然直接从 `app.models` 导入这些类型：

- `MaterialRequestTask`
- `NewContentInput`
- `SampleVideoInput`
- `StructurePreviewResponse`
- `TemplateStructure`
- `SupplementSelection`
- `TransferMappingOverride`

这让 `structure_service.py` 仍然挂在 legacy 兼容层上，和二期建立好的 `domain / api` 分层不完全一致。

## 3. 本轮边界

本轮只允许做下面这些事：

### 3.1 允许

- 把 `structure_service.py` 的类型导入改到正确 facade
- 新增或更新针对 `structure_service.py` 的导入回归测试
- 更新 legacy inventory 测试，让 `structure_service.py` 从允许保留的 `app.models` 引用名单里移除

### 3.2 不允许

- 改 `build_structure_preview()` 的执行顺序
- 改 `StructurePreviewResponse` 的字段和语义
- 改 AI explain、gap detection、composition、evaluation 的业务逻辑
- 顺手迁移 `fixture_asset_service.py` 或其它遗留模块

## 4. 目标导入归属

`structure_service.py` 这一轮应该收成下面的导入方向：

- 来自 `app.domain.shared.domain_models`
  - `MaterialRequestTask`
  - `NewContentInput`
  - `SampleVideoInput`
  - `TemplateStructure`
  - `SupplementSelection`
  - `TransferMappingOverride`

- 来自 `app.api.api_models`
  - `StructurePreviewResponse`

原因很简单：

- 前六个都是结构迁移过程中的领域对象
- `StructurePreviewResponse` 是 route 直接暴露的 API 契约对象

## 5. 测试策略

本轮需要两层护栏：

### 5.1 structure_service 定向导入测试

新增一个很小的 phase3 测试，至少断言：

- `structure_service.py` 包含 `from app.domain.shared.domain_models import ...`
- `structure_service.py` 包含 `from app.api.api_models import StructurePreviewResponse`
- `structure_service.py` 不再包含 `from app.models import` 或 `from app import models`

### 5.2 legacy inventory 更新

更新 `tests/test_phase2_legacy_model_inventory.py`：

- 把 `structure_service.py` 从允许直接引用 `app.models` 的文件清单里移除

这样可以保证：

- 这轮改动落地后，`structure_service.py` 不会再悄悄回退到旧桶
- 其它尚未处理的 legacy 依赖面仍然保持显式 inventory

## 6. 验证范围

这一轮至少跑下面几组：

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py -q
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_legacy_model_inventory.py -q
PYTHONPATH=. .venv/bin/python -m py_compile app/structure_service.py
```

如果新增了单独的 phase3 import 测试，再补跑：

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_structure_service_imports.py -q
```

## 7. 完成标准

这一轮完成后，需要同时满足：

- `structure_service.py` 不再直接依赖 `app.models`
- `build_structure_preview()` 的行为和现有测试结果不变
- legacy inventory 明确反映 `structure_service.py` 已完成迁移
- 这轮改动不会顺手扩大到其它遗留模块

## 8. 后续顺序

如果这轮顺利完成，推荐下一步继续按这个顺序推进：

1. `video_understanding/pipeline.py` 与 `template_adapter.py`
2. `transfer_explainer_service.py`
3. `fixture_asset_service.py`
4. `material_* / slot_profile / structure_coverage / timeline_patch`

这样可以沿着结构主链路，逐步把剩余 legacy `app.models` 依赖面往外收。
