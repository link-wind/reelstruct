# Agent / Tool 驱动工作台设计

## 背景

ReelStruct 当前已经具备样例解析、结构拆解、OCR、ASR、素材补全、结果生成等能力，但整体仍以页面按钮和面板切换驱动为主。

这套结构适合演示功能点，但开始暴露出三个问题：

- 执行主线分散在页面、hook 和后端服务之间，难以承接自然语言控制。
- 左侧对话区更像补充说明，右侧更像结果堆叠，还没有形成统一的 agent 工作流。
- 后续如果要支持“先做 OCR、跳过 ASR、改成保守补全”这类 prompt 级控制，当前结构很难自然扩展。

本次设计目标不是简单增加一个聊天外壳，而是把 ReelStruct 升级成一个由 agent 编排、由 tool 执行的短视频结构迁移工作台。

## 目标

1. 把当前工作台升级成 `agent -> tool -> result` 的执行模型。
2. 保留现有结构拆解、RAG、渲染等底层能力，不做推倒重来。
3. 支持 prompt 影响执行顺序和阶段策略。
4. 左侧变成轻量 agent 对话区，右侧保留 tab 结构但整体更简洁。
5. 在关键步骤提供人工确认，满足人机协同要求。

## 非目标

本阶段不做以下事情：

- 不重写结构拆解、OCR、ASR、RAG 或渲染主逻辑。
- 不做复杂多任务并行调度。
- 不做通用跨产品 agent 框架。
- 不在第一版开放全部细粒度工具给前端。
- 不把自然语言改片一次做成完整自由编辑系统。

## 核心思路

### 1. 执行模型

第一版采用 `tool 驱动 + agent 编排` 的方式。

```text
用户 prompt
  -> agent 生成执行计划
  -> tool 顺序执行
  -> 关键节点等待确认
  -> workspace state 回写
  -> 左侧对话 / 右侧结果同步更新
```

这里有三层职责：

- `agent`：根据 prompt 和当前状态决定下一步做什么。
- `tool`：执行阶段级动作，不直接负责全局流程决策。
- `domain service`：继续承载结构拆解、素材补全、渲染等底层能力。

### 2. tool 粒度

第一版只对外暴露阶段级 tool，内部保留细粒度子能力。

建议的主 tool：

- `analyze_structure`
- `run_ocr`
- `run_asr`
- `complete_materials`
- `generate_result`

这样做的原因：

- 对 agent 来说，阶段级 tool 更容易规划和解释。
- 对前端来说，阶段级 tool 更容易映射成清晰的执行状态。
- 对底层实现来说，不需要打散已有后端能力。

细粒度能力例如抽帧、analysis unit 聚合、图谱聚合、rerank、timeline patch、render，仍然保留在现有 service 内部，不直接变成前端的第一层控制对象。

### 3. 人机协同策略

执行方式采用“默认自动开始，但第一次先确认一次”的模式。

一轮典型执行流如下：

1. 用户输入任务 prompt。
2. agent 生成短计划。
3. 左侧出现首次执行确认。
4. 用户确认后，agent 开始按顺序调用 tool。
5. 到关键节点时，左侧弹出确认菜单。
6. 用户选择后，agent 继续执行、跳过或重规划。

第一版只拦截高价值确认点：

- 首次执行确认
- OCR
- ASR
- 补全策略确认
- 结果生成确认

## 状态机设计

第一版采用单主线状态机，不做复杂并行调度。

状态定义：

- `idle`
- `planning`
- `awaiting_start_confirm`
- `running`
- `awaiting_tool_confirm`
- `paused`
- `completed`
- `failed`

状态流转：

```text
idle
  -> planning
  -> awaiting_start_confirm
  -> running
  -> awaiting_tool_confirm
  -> running / paused
  -> completed / failed
```

约束：

- 一次只维护一条主执行链。
- 任意时刻只允许一个 active confirmation。
- 所有执行记录都写入 event log，供左侧对话流和右侧执行区共用。

## 前端设计

### 1. 左侧：轻量 agent 对话区

左侧不再做成重面板，而是更接近对话。

保留内容：

- 用户目标
- agent 当前判断
- 执行记录
- 很轻的状态提示

不保留内容：

- 独立的“当前任务卡”
- 大量并列状态卡
- 过重的 dashboard 风格摘要

确认交互采用贴近输入框的小菜单，而不是大 modal，也不是大卡片。

菜单风格要求：

- 更像 VSCode action menu
- 更窄、更轻、更扁
- 贴着输入框上方出现
- 不遮挡右侧主执行区

### 2. 右侧：保留 tab，但整体收轻

右侧继续保留原版“分 tab 查看不同阶段”的思路，但要减少层级和卡片数量。

建议保留的 tab：

- 样例解析
- 结构拆解
- 素材补全
- 结果验证

右侧每个 tab 的结构统一为：

1. 顶部一条轻状态栏
2. 一个主内容区
3. 少量摘要 / warning / 下一步

避免继续出现：

- 多块并列大卡片
- 结果区和摘要区同时过度展开
- 同一屏铺满过多结构化面板

目标是让右侧更像“当前阶段的主工作区”，而不是结果堆栈。

## 工程结构调整

### 前端

建议新增一层 `agent/`，把执行模型从现有 UI 逻辑里抽出来。

```text
apps/web/src/
  agent/
    types.ts
    planner.ts
    reducers.ts
    toolCatalog.ts
  hooks/
    useAgentWorkspace.ts
    useReelStructApi.ts
  components/
    Workspace/
      AgentPanel/
      ExecutionPanel/
```

职责拆分：

- `agent/types.ts`
  - agent 状态、执行步骤、确认请求、tool 结果、event log
- `agent/planner.ts`
  - 根据 prompt 和当前 workspace 状态生成下一步执行计划
- `agent/reducers.ts`
  - 推进状态机
- `agent/toolCatalog.ts`
  - 描述阶段级 tool 的前端可见信息
- `useAgentWorkspace.ts`
  - 新的工作台主 hook，负责 agent 驱动流程
- `useReelStructApi.ts`
  - 保留为纯 API 层

现有 `useReelStruct.ts` 不适合继续膨胀为 agent 总控层。建议后续要么拆分、要么逐步被 `useAgentWorkspace.ts` 吸收。

### 后端

建议新增 `agent/` 和 `tools/` 两层。

```text
services/api/app/
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
```

职责拆分：

- `agent/models.py`
  - AgentPlan、ToolCall、ConfirmationRequest、ExecutionEvent
- `agent/orchestrator.py`
  - 接收 prompt 和当前状态，输出下一步执行决策
- `agent/policy.py`
  - 定义哪些动作自动执行，哪些动作必须确认
- `agent/tool_registry.py`
  - 注册阶段级 tool 及其能力说明
- `agent/tool_executor.py`
  - 执行 tool，并把结果标准化写回状态

`tools/` 层只是 agent 的稳定执行入口，不负责底层领域判断。真正的结构拆解、素材补全、渲染逻辑仍由现有 service 承担，例如：

- `structure_service.py`
- `workflow_service.py`
- `material_*`
- `video_understanding/*`

这样可以在不推翻现有实现的前提下，引入 agent 主线。

## 统一状态模型

前后端都需要围绕同一个 workspace runtime state 工作。

第一版至少包含：

- `agent_status`
- `current_plan`
- `current_step`
- `pending_confirmation`
- `tool_runs`
- `stage_results`
- `warnings`
- `errors`
- `skip_reasons`

其中：

- 左侧主要消费 `agent_status`、`current_plan`、`pending_confirmation` 和 `tool_runs`
- 右侧主要消费 `stage_results`、`warnings`、`errors`

避免“左边说正在做 OCR，右边却还停在旧状态”的问题。

## Prompt 控制策略

本阶段不追求复杂自然语言理解，只做“足够可控”的 prompt 影响执行策略。

第一版支持：

- 跳过某一步
- 改执行顺序
- 延迟结果生成
- 改成保守补全策略

例如：

- “先看结构和 OCR，不要跑 ASR”
- “先分析，不要直接生成结果”
- “补全策略保守一点”

不支持：

- 任意自然语言直接改动所有内部参数
- 复杂多轮自由规划

## 迁移路径

建议按三步落地：

### 阶段 1：抽状态和执行主线

- 建立统一 workspace runtime state
- 前端把左侧对话和右侧工作区切到统一状态源
- 后端先只加 agent 编排骨架，不改底层业务服务

### 阶段 2：接入阶段级 tool

- 把结构拆解、OCR、ASR、素材补全、结果生成包成稳定 tool
- 左侧确认菜单接入真实状态机
- prompt 开始能影响执行链

### 阶段 3：替换旧的按钮驱动主线

- 让 agent 工作台成为默认主入口
- 旧按钮逻辑退化成调试入口或兼容入口

## 风险与约束

### 1. 不能把 agent 变成聊天壳子

如果只是在现有页面外面套一层对话，而不重组执行状态和 tool 边界，这次改造会失去意义。

### 2. 不能让 agent 先于底层能力成熟度

当前结构理解、RAG 和补全逻辑仍在演进中。agent 负责放大和组织能力，不负责掩盖底层能力不足。

### 3. 第一版不要做复杂调度

单主线、单确认点、阶段级 tool 已经足够支撑第一版演示和后续扩展。

## 结论

这次改造的本质不是“加一个 agent 面板”，而是把 ReelStruct 从功能驱动工作台升级成 agent 编排的创作工作流。

建议采用：

- `tool 驱动`
- `阶段级 tool 暴露`
- `左侧轻对话 + 输入框上方小菜单`
- `右侧保留 tab，但整体简洁化`
- `中等重构，不推翻现有底层能力`

这样既能贴合课题里的人机协同、过程可视化和自然语言控制方向，也能给后续 prompt 级编辑、tool 扩展和更强 agent runtime 留出清晰结构。
