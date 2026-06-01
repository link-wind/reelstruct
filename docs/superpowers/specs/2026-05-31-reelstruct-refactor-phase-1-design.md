# ReelStruct 重构一期设计

日期：2026-05-31

## 1. 目标

这一阶段的目标不是继续加能力，而是把当前已经能跑通的 ReelStruct 收成一个更清晰、更容易扩展的系统。

本阶段只解决一个核心问题：

**把前后端已经混在一起的“工作流控制、领域逻辑、展示装配、接口契约”重新分层。**

重构完成后，希望达到三个结果：

- 能清楚回答每一层负责什么，不再靠“去大文件里找”。
- 后续继续加 agent、RAG、补全、结果生成时，不再优先修改总控文件。
- 在不改变现有产品行为的前提下，降低维护和继续演进的复杂度。

## 2. 当前结构判断

当前系统已经具备可演示闭环：

- 样例上传与解析
- 结构拆解与迁移预览
- OCR / ASR / 图谱证据
- 素材缺口识别与补全建议
- 结果生成、导出、模板沉淀
- agent/tool 工作台执行链路

问题不是“没有能力”，而是“能力已经开始堆叠到几个大文件里”。

当前最重的文件：

- `apps/web/src/hooks/useReelStruct.ts`：2374 行
- `apps/web/src/components/Views/WorkspaceView.tsx`：1139 行
- `apps/web/src/hooks/useReelStructApi.ts`：679 行
- `services/api/app/structure_service.py`：1268 行
- `services/api/app/models.py`：599 行
- `services/api/app/main.py`：498 行
- `services/api/app/workflow_service.py`：291 行

这说明当前已经出现四类结构问题：

### 2.1 前端总控过重

`useReelStruct.ts` 同时承担了：

- 页面状态容器
- 样例上传与素材上传流程
- OCR / ASR / 结构预览 / demo 生成编排
- 领域数据转换
- 一部分展示层 view model 计算
- fallback 数据与文案逻辑

这会带来两个直接问题：

- 任意一个新能力都会优先继续往这里堆。
- 很难判断某段逻辑属于“领域层”还是“页面层”。

### 2.2 页面装配和工作流控制耦合

`WorkspaceView.tsx` 已经不只是页面组件，它同时承担了：

- agent 运行态驱动
- 执行阶段推进
- 交互确认
- 多个 tab 的主装配
- 大量 view model 派生

结果是页面层知道了太多业务细节，也让后续拆组件时风险变高。

### 2.3 后端领域服务边界模糊

`structure_service.py` 已经逐渐演变成“结构迁移总装配器”，它里边混合了：

- 样例结构模板拼装
- 槽位映射
- 缺口识别
- 迁移解释
- 补全策略
- composition 生成
- fallback 图谱与展示数据

它已经不再是单一 service，而是多个子域能力的集合。

### 2.4 模型与接口契约没有分层

`models.py` 同时被用于：

- API 请求响应
- 领域对象
- 工作流输入输出
- run/template 持久化

这会让模型改动扩散得很快，也会让后续 agent tool 契约越来越臃肿。

## 3. 重构原则

本阶段只按下面四条原则推进：

### 3.1 行为不变优先

重构一期不是产品改版。

必须保持以下行为不变：

- workspace 现有执行链路可继续工作
- agent/tool 工作台保持现有用户操作方式
- 结构预览、素材补全、结果生成的接口语义不变
- run / template / export 的现有能力不回退

### 3.2 先分层，再瘦身

当前最重要的不是先删逻辑，而是先把逻辑放回正确的层。

顺序必须是：

1. 明确层级
2. 把逻辑迁回对应层
3. 再逐步缩小总控文件

### 3.3 保留现有 agent/tool 方向

这一阶段不推翻最近已经形成的 agent/tool 模型。

相反，重构要围绕它继续收口：

- 前端保留 `agent/ + hooks/ + Workspace panels`
- 后端保留 `agent/ + tools/ + domain services`

### 3.4 只做一期能收住的拆分

这一阶段不做大规模“理念正确但改不完”的重构。

重点是先把最危险的耦合点拆开，给二期和三期留出清晰通道。

## 4. 当前结构与目标结构对照

### 4.1 前端当前结构

当前前端大致是这样：

```text
app/
  page.tsx
  ReelStructWorkspace.tsx

components/
  MainApp.tsx
  Views/
    HomeView.tsx
    WorkspaceView.tsx
  Workspace/
    ...多个面板

hooks/
  useReelStruct.ts
  useReelStructApi.ts
  useAgentWorkspace.ts
  agentWorkspaceGate.mjs
  evidenceGraph.ts

agent/
  reducers.ts
  toolCatalog.ts
  executionProgress.ts
  types.ts
```

问题不在目录数量不够，而在职责还没有收干净。

### 4.2 前端目标结构

一期目标不是大换目录，而是在现有目录上把职责压清楚：

```text
apps/web/src/
  app/
    page.tsx
    ReelStructWorkspace.tsx

  agent/
    types.ts
    reducers.ts
    toolCatalog.ts
    executionProgress.ts

  hooks/
    useAgentWorkspace.ts
    useReelStructApi.ts
    useSampleWorkspace.ts
    useStructureWorkspace.ts
    useMaterialWorkspace.ts
    useResultWorkspace.ts
    useReelStruct.ts

  components/
    Views/
      HomeView.tsx
      WorkspaceView.tsx
    Workspace/
      AgentConversationPanel.tsx
      AgentConfirmationMenu.tsx
      WorkflowNav.tsx
      ...现有各阶段面板
```

这里最关键的变化有两个：

- `useReelStruct.ts` 从“全能总控”变成“组合层”
- `WorkspaceView.tsx` 从“总控页面”变成“装配层”

### 4.3 后端当前结构

当前后端大致是这样：

```text
services/api/app/
  main.py
  models.py
  structure_service.py
  workflow_service.py
  run_export_service.py
  template_record_service.py
  run_record_service.py
  material_* 系列
  video_understanding/
  agent/
  tools/
```

这套目录已经隐约分层，但还没有真正落地为稳定结构。

### 4.4 后端目标结构

一期不要求把整个后端都拆成新包，但要明确目标结构：

```text
services/api/app/
  main.py

  agent/
    models.py
    orchestrator.py
    policy.py
    tool_registry.py
    tool_executor.py

  tools/
    analyze_structure.py
    run_ocr.py
    run_asr.py
    complete_materials.py
    generate_result.py

  domain/
    sample/
    structure/
    material/
    run/

  contracts/
    api_models.py
    domain_models.py

  video_understanding/
    ...保留
```

一期不会一次性完成全部目录迁移，但会按这个目标去做第一轮抽离。

## 5. 一期重构范围

这一阶段只做三件事。

### 5.1 前端：拆 `useReelStruct`

目标：把 `useReelStruct.ts` 从大总管拆成四个子域 hook，再由一个薄组合层统一导出。

建议拆分：

- `useSampleWorkspace`
  负责样例上传、转写上传、样例基础状态

- `useStructureWorkspace`
  负责结构预览、OCR/ASR、结构图谱、slot drafts、mapping overrides

- `useMaterialWorkspace`
  负责素材上传、素材分析、缺口、request sheet、supplement 选择

- `useResultWorkspace`
  负责 run 生成、recent runs、batch、template 相关结果态

保留：

- `useReelStruct`
  只负责组合这些子 hook，并提供对页面友好的统一接口

这一刀的价值最大，因为它能立刻降低后续改动的耦合面积。

### 5.2 前端：瘦 `WorkspaceView`

目标：让 `WorkspaceView.tsx` 不再控制具体业务流程，只保留页面装配。

应该移出的内容：

- agent flow 执行细节
- 阶段推进判断
- 大块 view model 生成逻辑
- 结构标签、说明、本地化规则的领域判断

应该保留的内容：

- layout
- tab 切换
- 面板装配
- UI 级交互连接

理想状态是：

- agent 执行逻辑主要在 `useAgentWorkspace`
- 领域态主要来自拆分后的 `use*Workspace`
- `WorkspaceView` 只负责把这些东西摆到页面上

### 5.3 后端：拆 `structure_service`

目标：把 `structure_service.py` 从总装配文件收成几个明确子模块。

建议先抽出四块：

- `template_builder`
  负责样例结构模板与 fallback 结构图谱

- `transfer_planner`
  负责槽位映射、迁移解释、variant 策略

- `material_gap_builder`
  负责缺口识别、request sheet、supplement options

- `composition_builder`
  负责 composition track、timeline patch 对接、结果前预组装

一期不要求把所有实现都拆干净，但至少要把主逻辑入口改成“委托多个子模块”，而不是继续在一个文件里叠加。

## 6. 一期不做什么

为了让范围收得住，这一阶段明确不做以下内容：

- 不改产品交互模型
- 不改 agent/tool 执行协议
- 不重写 RAG / vector / graph / rerank 主逻辑
- 不重写 video_understanding
- 不统一所有历史文档
- 不做一次性目录大迁移
- 不把所有模型全部拆完

这些会留到后续阶段。

## 7. 执行顺序

推荐执行顺序如下：

### 第一步：前端状态分层

先拆 `useReelStruct.ts`。

原因：

- 风险相对可控
- 对现有行为影响最小
- 一旦拆开，页面和 agent 层都会变得更容易整理

### 第二步：页面装配收口

再瘦 `WorkspaceView.tsx`。

原因：

- 前一步做完后，页面层才有条件只保留装配职责
- 能顺手把很多 view model 计算和领域判断迁走

### 第三步：后端结构域拆分

最后拆 `structure_service.py`。

原因：

- 前端先收口后，接口消费面会更稳定
- 这样拆后端时更容易保持行为不变

## 8. 风险与控制

### 8.1 最大风险

最大风险不是“拆不动”，而是“边拆边顺手改行为”。

一旦在重构一期里同时去改：

- 状态字段
- 页面交互
- tool 契约
- 结构结果语义

整个范围就会失控。

### 8.2 风险控制方式

必须保持三条纪律：

- 每一步只做一种层级变化，不混着做
- 每次拆分后都跑现有 smoke check 和相关测试
- 新文件可以增加，但旧接口先保持兼容，最后再收缩

### 8.3 验证基线

一期每个子阶段都应该至少跑：

- 前端 `npm run typecheck`
- 前端相关 node tests
- `npm run build`
- `npm run check:workspace`
- 后端对应 pytest 子集

如果某一步需要动到 agent tool 或结构迁移主链路，就必须补跑：

- `tests/test_agent_orchestrator.py`
- `tests/test_tool_executor.py`
- `tests/test_workflow_service.py`

## 9. 一期完成后的预期结果

如果这一阶段完成，系统不会立刻多出新功能，但会有四个很实际的改善：

- 新能力不再默认加到 `useReelStruct.ts` 和 `structure_service.py`
- 页面、agent、领域、接口四层职责更容易讲清楚
- 后续做二期 RAG / 补全 / 结果链路增强时，改动范围更可控
- 这个项目从“能跑通的 MVP”更接近“可持续演进的工程结构”

## 10. 下一步建议

这份设计确认后，下一步建议不是立刻开改所有地方，而是先写“重构一期执行计划”。

执行计划应当按下面三个任务包展开：

1. 前端状态层拆分计划
2. 页面装配层收口计划
3. 后端结构域拆分计划

每个任务包都需要明确：

- 涉及文件
- 行为不变边界
- 拆分顺序
- 验证命令

这样才能保证下一阶段重构既能推进，又不会把当前可运行闭环打散。
