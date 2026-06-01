# ReelStruct 重构三期：video_understanding import 收口设计

日期：2026-06-01

## 1. 目标

这一轮继续沿着结构主链路往前收，只做一个窄范围动作：

**把 `services/api/app/video_understanding/pipeline.py` 和 `services/api/app/video_understanding/template_adapter.py` 对 `app.models` 的直接依赖，回收到已经建立好的分层 facade。**

这一轮不扩到 `transfer_explainer_service.py`，也不顺手处理 `fixture_asset_service.py` 或 `material_*`。

## 2. 当前现状

当前这条链路里：

- `pipeline.py` 直接从 `app.models` 导入
  - `SampleVideoInput`
  - `TemplateStructure`

- `template_adapter.py` 直接从 `app.models` 导入
  - `GraphPresentationEdge`
  - `GraphPresentationNode`
  - `GraphPresentationSummary`
  - `SampleAnalysisBeat`
  - `SampleAnalysisMetric`
  - `SampleAnalysisSummary`
  - `StructureSlot`
  - `TemplateStructure`

这两个文件都属于结构理解和模板组装的实现层，按二期建立好的边界，它们使用的这些对象都属于领域模型，而不是继续挂在 `app.models` 兼容层上。

## 3. 本轮边界

### 3.1 允许

- 调整 `pipeline.py` 和 `template_adapter.py` 的模型导入来源
- 新增针对这两个文件的定向导入测试
- 更新 legacy inventory，把这两个文件从允许保留的 `app.models` 引用名单里移除

### 3.2 不允许

- 改 `build_ai_structure_template()`、`build_fallback_structure_template()`、`build_ai_or_fallback_structure_template()` 的业务流程
- 改 `adapt_ai_structure_to_template()`、`adapt_graph_segments_to_template()` 的结构装配逻辑
- 改 `ShotEvidenceGraph`、`AIStructureAnalysis` 或其它 schema 定义
- 顺手迁移 `transfer_explainer_service.py`

## 4. 目标导入归属

这一轮目标很统一：

### 4.1 `pipeline.py`

以下对象都应该来自 `app.domain.shared.domain_models`：

- `SampleVideoInput`
- `TemplateStructure`

### 4.2 `template_adapter.py`

以下对象都应该来自 `app.domain.shared.domain_models`：

- `GraphPresentationEdge`
- `GraphPresentationNode`
- `GraphPresentationSummary`
- `SampleAnalysisBeat`
- `SampleAnalysisMetric`
- `SampleAnalysisSummary`
- `StructureSlot`
- `TemplateStructure`

原因是：

- 这些对象都服务于结构拆解、模板生成、图谱表现，是领域层内部表达
- 这一轮没有 route 直接暴露对象，因此不需要引入 `api.api_models`

## 5. 测试策略

本轮需要两层护栏：

### 5.1 video_understanding 定向导入测试

新增一个 phase3 测试，至少覆盖：

- `pipeline.py` 使用 `app.domain.shared.domain_models` 导入 `SampleVideoInput`、`TemplateStructure`
- `template_adapter.py` 使用 `app.domain.shared.domain_models` 导入 8 个目标领域对象
- 两个文件都不再包含 `app.models` 的真实导入

这里建议直接使用 AST 语义检查，不再做字符串匹配。

### 5.2 legacy inventory 更新

更新 `tests/test_phase2_legacy_model_inventory.py`：

- 把 `video_understanding/pipeline.py`
- 把 `video_understanding/template_adapter.py`

从允许继续依赖 `app.models` 的清单里移除。

## 6. 验证范围

这一轮至少跑下面几组：

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_video_understanding_pipeline.py -q
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase2_legacy_model_inventory.py -q
PYTHONPATH=. .venv/bin/python -m py_compile app/video_understanding/pipeline.py app/video_understanding/template_adapter.py
```

如果新增了单独的 phase3 import 测试，再补跑：

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_phase3_video_understanding_imports.py -q
```

## 7. 完成标准

这一轮完成后，需要同时满足：

- `pipeline.py` 不再直接依赖 `app.models`
- `template_adapter.py` 不再直接依赖 `app.models`
- `test_video_understanding_pipeline.py` 结果不变
- legacy inventory 明确反映这两个文件已完成迁移
- 不提前扩大到 `transfer_explainer_service.py`

## 8. 后续顺序

如果这轮顺利完成，推荐下一步按下面顺序继续：

1. `video_understanding/transfer_explainer_service.py`
2. `fixture_asset_service.py`
3. `material_graph_service.py` / `material_rag_service.py` / `material_rerank_service.py`
4. `slot_profile_service.py` / `structure_coverage_service.py` / `timeline_patch_service.py`

这样会继续沿着结构理解 -> 模板装配 -> 素材检索补全的路径，把剩余 legacy `app.models` 依赖逐步往外收。
