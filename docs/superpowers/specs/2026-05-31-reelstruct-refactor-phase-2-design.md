# ReelStruct 重构二期设计

日期：2026-05-31

## 1. 目标

二期的目标不是继续拆已经明显变薄的总控文件，而是把当前后端最容易继续膨胀的一层收口：

**把 `services/api/app/models.py` 从“共享模型桶”拆成明确分层的契约结构。**

这一阶段主要解决三个问题：

- API 契约、领域对象、workflow 中间态现在还混在一起，改一个模型很容易牵动整条链路。
- `structure_service` 一期虽然已经退化成装配入口，但它依赖的模型边界还不清晰。
- agent / workflow / tools 的主链路已经成形，如果继续共用一个 `models.py`，后续能力越多，模型扩散会越快。

二期完成后，希望达到四个结果：

- 能清楚回答一个模型到底属于 `api / domain / workflow` 哪一层。
- route、tool、workflow、domain service 的 import 方向更稳定，不再默认全部指向 `models.py`。
- 领域模型新增或调整时，影响面可以收敛在同一层。
- 不改变现有用户行为、不改 API 路径和主要响应语义。

## 2. 当前结构判断

经过一期重构，后端结构已经比之前清晰很多：

- `services/api/app/structure_service.py`：77 行
- `services/api/app/domain/structure/transfer_planner.py`：236 行
- `services/api/app/domain/structure/material_gap_builder.py`：426 行
- `services/api/app/domain/structure/template_builder.py`：398 行
- `services/api/app/domain/structure/composition_builder.py`：141 行

这说明“一期把结构迁移大总控拆开”已经成立。

但新的核心瓶颈也已经更清楚了：

- `services/api/app/models.py`：599 行

它仍然同时承载：

- FastAPI request / response 模型
- structure / material / composition 领域对象
- workflow / agent / tool 执行中间态
- run / template / export 结果对象

这会带来三个直接问题：

### 2.1 模型修改扩散过大

当一个字段只属于某个领域 builder 时，它仍然可能出现在 route、workflow、tool、测试里被全局 import。

这意味着：

- 修改成本难预估
- 依赖方向不清晰
- 很难判断“这是接口变更，还是内部结构调整”

### 2.2 服务边界虽然变清楚了，但契约边界还没跟上

一期已经把 `template_builder / transfer_planner / material_gap_builder / composition_builder` 拆出来了。

但这些 builder 仍然直接从同一个 `models.py` 取对象。

于是文件职责变清楚了，模型职责却还没分清。  
这会让二期之后继续演进时，又慢慢回到“文件拆了，但层次还是混的”。

### 2.3 workflow / tools 容易继续绑定领域细节

现在 agent / workflow / tools 主链路是稳定的，但如果它们继续直接拿整个 `models.py` 里的领域对象：

- tool 很容易知道太多 structure 细节
- workflow 很容易继续吞进展示或领域字段
- 后续加新 tool 时，默认还是从“大桶”里拿类型

长期看，这会让 workflow 和 domain 的边界重新变模糊。

## 3. 二期原则

### 3.1 先拆模型边界，不先改业务行为

二期的本质是“契约归位”，不是功能重写。

必须保持：

- `/api/structure/preview` 等现有 route 不改路径
- agent/tool 主流程不改交互语义
- `analyze_structure / run_ocr / run_asr / complete_materials / generate_result` 契约不主动扩写
- 现有测试表达的业务结果不回退

### 3.2 先建立分层文件，再迁 import

不要一上来就大面积替换所有引用。

正确顺序应该是：

1. 建立新的模型分层文件
2. 把模型按职责迁过去
3. 保留短期兼容出口
4. 按模块逐步回收 import
5. 最后再决定是否保留聚合入口

### 3.3 依赖方向必须单向

二期要明确下面这个方向：

- `api` 可以依赖 `domain / workflow`
- `workflow` 可以依赖 `domain`
- `domain` 不反向依赖 `api`

也就是说：

- route 层可以把领域对象装配成响应
- workflow 可以调 domain service
- domain model 不能为了 route 展示去知道 API 细节

### 3.4 控制目录扩张

二期不是为了“看起来更像标准架构”而铺很多空目录。

只引入当前真正需要的结构：

- `api/api_models.py`
- `domain/shared/domain_models.py`
- `workflow/workflow_models.py`

后续如果再有稳定增长，再继续细分。

## 4. 目标结构

### 4.1 当前后端模型结构

当前大致是：

```text
services/api/app/
  models.py
  main.py
  workflow_service.py
  structure_service.py
  agent/
  tools/
  domain/
```

问题不在目录少，而在所有层都默认指向 `models.py`。

### 4.2 二期目标结构

二期建议收成下面这样：

```text
services/api/app/
  main.py
  models.py

  api/
    api_models.py

  domain/
    shared/
      domain_models.py
    structure/
      template_builder.py
      transfer_planner.py
      material_gap_builder.py
      composition_builder.py

  workflow/
    workflow_models.py

  agent/
  tools/
```

这里每层的职责是：

- `api/api_models.py`
  放请求体、响应体、API 暴露对象、route 直接使用的模型

- `domain/shared/domain_models.py`
  放结构迁移、素材缺口、composition、template 这些领域对象

- `workflow/workflow_models.py`
  放 agent 执行、tool 调度、运行状态、中间编排对象

- `models.py`
  二期前半段先作为兼容聚合出口；后半段视迁移情况再决定是否保留

## 5. 分阶段实施范围

### 5.1 第一段：建立分层模型文件

这一段只做模型归类，不做业务逻辑改写。

目标是先把以下对象分组：

- `domain_models`
  - `StructureSlot`
  - `TemplateStructure`
  - `MaterialGap`
  - `MaterialRequestTask`
  - `TransferPlan`
  - `TransferMapping`
  - `CompositionSpec`
  - `CompositionTrack`
  - 以及和 structure/material/composition 强绑定的对象

- `workflow_models`
  - workflow / agent / tool 执行中间态
  - run trace、执行状态、过程型 payload

- `api_models`
  - FastAPI request / response
  - route 返回值包装对象

这一段允许 `models.py` 暂时继续 `re-export` 这些类型。

### 5.2 第二段：按模块回收 import

这一段不全局替换，而是按责任链回收：

1. 先回收 `domain/structure/*`
2. 再回收 `workflow_service.py`
3. 再回收 `tools/*`
4. 最后回收 `main.py` 和 route 直接使用点

这样做的原因是：

- domain builder 对模型归属最明确
- workflow 和 tools 更容易受连锁影响，应该放在后面
- route 层最后改，最稳

### 5.3 第三段：决定 `models.py` 的最终命运

这一步要根据迁移结果做选择：

- 如果外部引用已经基本回收干净：
  - 把 `models.py` 缩成极薄聚合层，或删除

- 如果还有较多跨模块引用：
  - 保留 `models.py` 作为兼容入口，但禁止继续往里新增定义

也就是说，二期重点不是“必须删除 `models.py`”，而是“它不能再是新增模型的默认落点”。

当前实现结果（2026-06-01）已经落在第二种情况：

- `api / domain / workflow` 三个 facade 已建立，并且 route、workflow、tool、structure builder 的关键导入已经回收到分层入口
- 二期没有在这一轮物理搬迁底层模型定义；三个 facade 仍然是兼容 re-export，`app.models` 继续作为当前 source of truth
- `models.py` 文件头已经明确标注为兼容层，二期内不再把它当作新增模型的默认落点
- 仍然存在一批历史兼容引用，因此二期不强行删除 `models.py`

剩余兼容引用主要分成两类：

- facade 自身的 re-export：`app/api/api_models.py`、`app/domain/shared/domain_models.py`、`app/workflow/workflow_models.py`
- 仍待后续阶段继续回收的实现层模块：`structure_service.py`、`fixture_asset_service.py`、`material_graph_service.py`、`material_rag_service.py`、`material_rerank_service.py`、`slot_profile_service.py`、`structure_coverage_service.py`、`timeline_patch_service.py`、`video_understanding/pipeline.py`、`video_understanding/template_adapter.py`、`video_understanding/transfer_explainer_service.py`

因此二期的兼容层决策是：

- 保留 `models.py` 作为薄兼容入口
- 禁止继续往 `models.py` 新增定义
- 把剩余实现层引用的回收留给下一阶段

## 6. 验证基线

二期每次迁移都应该保持下面这组验证基线：

### 6.1 后端主链路回归

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py tests/test_workflow_service.py -q
```

### 6.2 结构迁移与接口回归

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py tests/test_transfer_planner.py tests/test_material_gap_builder.py -q
```

### 6.3 语法与导入检查

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m py_compile app/structure_service.py app/domain/structure/transfer_planner.py app/domain/structure/material_gap_builder.py app/workflow_service.py app/main.py
```

如果某次迁移动到了 route、workflow、tool 任意一层，就必须补跑对应测试，不允许只跑局部 builder 单测。

## 7. 风险与控制

### 7.1 最大风险不是逻辑错误，而是引用回归

二期最容易出现的问题不是业务结果变了，而是：

- import 循环
- 模型位置迁完后仍然有旧引用
- route / workflow / tool 在不同文件里拿到不同层的同名对象

所以二期应该优先警惕“导入结构回退”，而不是只盯功能断言。

### 7.2 不做联合大重构

二期不要把下面几件事绑在一起做：

- 模型拆分
- workflow 重写
- tool 契约重设
- route payload 改版

这些事情长期都重要，但不应该在一次二期里打包。

### 7.3 允许短期兼容层

如果某一轮迁移已经完成 70%-80%，但完全移除旧入口会导致大面积回归，就应该接受“保留兼容层”的阶段性方案。

这比为了彻底而把整条链路一次性推翻更稳。

## 8. 完成标准

二期完成后，至少要满足下面这些标准：

- `models.py` 不再是新增模型的默认落点
- `domain/structure/*` 不再主要依赖 `models.py` 这个大桶入口
- `workflow / tools / routes` 对模型的依赖方向更清楚
- 结构迁移主链路、agent/tool 主链路测试保持通过
- 后续再加一个 domain builder 或 workflow 能明确知道模型应该放哪一层

## 9. 推荐执行顺序

如果进入实现阶段，我建议按下面顺序推进：

1. 先建立 `api_models.py / domain_models.py / workflow_models.py`
2. 先迁 `domain/structure/*` 的 import
3. 再迁 `workflow_service.py`
4. 再迁 `tools/*`
5. 最后迁 `main.py` 和 API 直接响应模型
6. 最后决定 `models.py` 保留还是缩成兼容出口

这条顺序的好处是：

- 先处理边界最清楚的地方
- 把高耦合链路留到后面
- 每一步都能用现有测试基线兜住

## 10. 结论

一期解决的是“大总控文件太重”。  
二期应该解决的是“模型契约还没有分层”。

如果这一层不收，后面无论继续做 structure、material、agent、workflow，最后都还是会回到 `models.py` 继续堆。

所以二期最合适的方向不是再找下一个大文件猛拆，而是把后端模型边界正式建立起来，让一期刚形成的 service 分层真正稳定下来。
