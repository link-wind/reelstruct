# ReelStruct 重构一期 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变当前用户行为的前提下，完成 ReelStruct 一期结构重构，把前端状态总控、页面装配总控和后端结构迁移总装配器拆成更清晰的分层结构。

**Architecture:** 先拆前端状态层，再收口页面装配层，最后拆后端结构域。整个过程保持 agent/tool 协议、workspace 主流程、run/template/export 语义不变，采用兼容式迁移而不是一次性替换。

**Tech Stack:** Next.js, React, TypeScript, FastAPI, Pydantic, pytest, Node test runner

---

## File Structure

### 前端现有重点文件

- `apps/web/src/hooks/useReelStruct.ts`
  当前前端状态、编排、view model 和 fallback 逻辑总控。

- `apps/web/src/components/Views/WorkspaceView.tsx`
  当前页面装配、agent flow、阶段推进和大量派生展示数据总控。

- `apps/web/src/hooks/useAgentWorkspace.ts`
  当前 agent 工作流控制入口，后续应承接更多执行编排职责。

- `apps/web/src/hooks/useReelStructApi.ts`
  当前 API helper 层，应继续保持为纯接口访问层。

### 前端目标新增文件

- `apps/web/src/hooks/useSampleWorkspace.ts`
  样例上传、转写上传、样例基础状态。

- `apps/web/src/hooks/useStructureWorkspace.ts`
  结构预览、OCR / ASR、图谱和 slot draft 相关状态。

- `apps/web/src/hooks/useMaterialWorkspace.ts`
  素材上传、素材分析、缺口、request sheet、supplement 选择。

- `apps/web/src/hooks/useResultWorkspace.ts`
  run 生成、run 记录、batch、template 结果态。

### 后端现有重点文件

- `services/api/app/structure_service.py`
  当前结构迁移、缺口识别、composition 和 fallback 展示逻辑总装配文件。

- `services/api/app/main.py`
  当前 route 聚合入口，暂不作为一期核心拆分对象，但相关调用要保持兼容。

- `services/api/app/models.py`
  当前 API / domain / workflow 共享模型集合，一期先避免继续膨胀。

### 后端目标新增文件

- `services/api/app/domain/structure/template_builder.py`
  样例结构模板和 fallback 图谱相关逻辑。

- `services/api/app/domain/structure/transfer_planner.py`
  槽位映射、variant 策略、迁移解释。

- `services/api/app/domain/structure/material_gap_builder.py`
  缺口识别、request sheet、supplement options。

- `services/api/app/domain/structure/composition_builder.py`
  composition track 生成、timeline patch 对接、结果前预组装。

### 核心验证命令

- 前端类型检查：`cd /Users/linkwind/Code/ReelStruct/apps/web && npm run typecheck`
- 前端 node tests：`cd /Users/linkwind/Code/ReelStruct/apps/web && node --test src/hooks/__tests__/useReelStructApi.test.mjs src/hooks/__tests__/useAgentWorkspace.test.mjs src/hooks/__tests__/evidenceGraph.test.mjs src/agent/__tests__/reducers.test.ts src/agent/__tests__/executionProgress.test.ts`
- 前端构建：`cd /Users/linkwind/Code/ReelStruct/apps/web && npm run build`
- workspace smoke：`cd /Users/linkwind/Code/ReelStruct/apps/web && npm run check:workspace`
- 后端核心测试：`cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py tests/test_workflow_service.py -q`

### 行为不变边界

- workspace 页面操作流不变
- agent/tool 主流程不变
- `analyze_structure / run_ocr / run_asr / complete_materials / generate_result` 契约不变
- run / template / export 结果语义不变

## Task 1: 写前端状态层拆分方案骨架

**Files:**
- Modify: `docs/superpowers/specs/2026-05-31-reelstruct-refactor-phase-1-design.md`
- Create: `docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md`

- [ ] **Step 1: 列出现有 `useReelStruct.ts` 的职责清单**

记录以下四类职责，并标明对应代码段：

- 样例输入职责
- 结构预览职责
- 素材补全职责
- 结果生成职责

预期输出：

```text
sample: uploadSample / uploadTranscript / sampleUpload / transcriptUpload
structure: generateStructurePreview / generateOcrEvidence / generateAsrEvidence / slotDrafts
material: uploadMaterialAsset / generateMaterialEvidence / requestSheet / supplementSelection
result: runDemo / runDemoVariants / recentRuns / template state
```

- [ ] **Step 2: 标明四个新 hook 的文件边界**

在计划文档里写明：

- `apps/web/src/hooks/useSampleWorkspace.ts`
- `apps/web/src/hooks/useStructureWorkspace.ts`
- `apps/web/src/hooks/useMaterialWorkspace.ts`
- `apps/web/src/hooks/useResultWorkspace.ts`

每个文件只写一个主职责，不要交叉承载。

- [ ] **Step 3: 写出组合层 `useReelStruct` 的保留职责**

保留职责只包含：

- 调用四个子 hook
- 合并返回值
- 对页面暴露兼容接口

不再新增新的业务编排。

- [ ] **Step 4: 定义前端状态层拆分的完成标准**

完成标准写入文档：

- `useReelStruct.ts` 行数显著下降
- 四个子 hook 可以单独理解职责
- `WorkspaceView.tsx` 不再依赖 `useReelStruct` 内部实现细节
- 现有前端类型检查和 smoke check 通过

- [ ] **Step 5: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md /Users/linkwind/Code/ReelStruct/docs/superpowers/specs/2026-05-31-reelstruct-refactor-phase-1-design.md
git commit -m "docs: add refactor phase 1 state-layer plan"
```

## Task 2: 写页面装配层收口计划

**Files:**
- Modify: `docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md`
- Reference: `apps/web/src/components/Views/WorkspaceView.tsx`
- Reference: `apps/web/src/hooks/useAgentWorkspace.ts`

- [ ] **Step 1: 识别 `WorkspaceView.tsx` 中必须迁出的职责**

在计划里列出以下迁出目标：

- agent flow 执行细节
- 执行阶段推进判断
- 大块 view model 派生
- 领域型本地化和结构标签判断

预期输出：

```text
迁去 useAgentWorkspace: executePlannedFlow / confirmation-driven execution
迁去 hooks: analysisView / shotEvidence / gapItems / resultView
迁去 utility: label / description / localization helpers
```

- [ ] **Step 2: 标明 `WorkspaceView.tsx` 的保留职责**

在计划里明确保留：

- 页面 layout
- tab 与 panel 装配
- UI 事件连接
- 极少量视图层状态

- [ ] **Step 3: 定义页面装配层的迁移顺序**

顺序必须写明：

1. 先抽 view model helper
2. 再迁 agent flow 细节
3. 最后清理 `WorkspaceView.tsx`

不要直接一次性大改页面。

- [ ] **Step 4: 定义页面层验证基线**

写入以下验证要求：

- `npm run typecheck`
- 相关 node tests
- `npm run build`
- `npm run check:workspace`

且期望行为为：

```text
workspace shell 流程输出保持 WORKSPACE_SHELL_OK=1
agent 确认、阶段推进、结果展示文案不回退
```

- [ ] **Step 5: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md
git commit -m "docs: add workspace view refactor plan"
```

## Task 3: 写后端结构域拆分计划

**Files:**
- Modify: `docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md`
- Reference: `services/api/app/structure_service.py`
- Reference: `services/api/app/workflow_service.py`
- Reference: `services/api/app/models.py`

- [ ] **Step 1: 列出 `structure_service.py` 当前承担的四类职责**

在计划里整理：

- 模板构建
- 迁移规划
- 缺口构建
- composition 构建

预期输出：

```text
template_builder: template / fallback graph / analysis summary seed
transfer_planner: mappings / explanations / variant-specific changes
material_gap_builder: gaps / request sheet / supplement options
composition_builder: composition tracks / timeline patch application / preview composition
```

- [ ] **Step 2: 定义后端新模块文件结构**

在计划文档中写明目标文件：

- `services/api/app/domain/structure/template_builder.py`
- `services/api/app/domain/structure/transfer_planner.py`
- `services/api/app/domain/structure/material_gap_builder.py`
- `services/api/app/domain/structure/composition_builder.py`

并说明一期允许先通过委托调用接入，而不是一次性完全搬空。

- [ ] **Step 3: 定义拆分顺序**

顺序写明为：

1. 先抽纯函数和 helper
2. 再抽 builder 模块
3. 最后让 `structure_service.py` 退化成装配入口

不要先改 `main.py`，不要先改 API 契约。

- [ ] **Step 4: 定义后端验证基线**

写入以下验证命令：

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py tests/test_workflow_service.py -q
```

如果触及结构主链路，额外补充：

```bash
cd /Users/linkwind/Code/ReelStruct/services/api
OPENAI_API_KEY= PYTHONPATH=. .venv/bin/python -m pytest tests/test_structure_service.py tests/test_media_api.py -q
```

- [ ] **Step 5: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md
git commit -m "docs: add backend structure-domain refactor plan"
```

## Task 4: 写总体执行节奏和检查点

**Files:**
- Modify: `docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md`

- [ ] **Step 1: 写出三阶段实施顺序**

计划中明确：

1. 前端状态层拆分
2. 页面装配层收口
3. 后端结构域拆分

并标明每一阶段结束前，不进入下一阶段。

- [ ] **Step 2: 写出每阶段的停顿检查点**

每一阶段结束后都加入检查点：

- 代码是否仍保持行为不变
- 大文件是否真的变薄
- 新边界是否清楚
- smoke check 是否通过

- [ ] **Step 3: 写出失败回滚策略**

计划中明确：

- 如果拆分后接口行为发生变化，优先恢复兼容层
- 如果页面 smoke check 失败，先停在当前阶段修正，不进入下一阶段
- 如果后端 builder 抽离导致测试大面积回退，先改为委托式抽离，不继续深拆

- [ ] **Step 4: 写出完成标准**

计划中写明一期完成标准：

- `useReelStruct.ts` 降为组合层
- `WorkspaceView.tsx` 主要承担页面装配职责
- `structure_service.py` 主要承担装配入口职责
- 核心验证命令全部通过

- [ ] **Step 5: Commit**

```bash
git add /Users/linkwind/Code/ReelStruct/docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md
git commit -m "docs: finalize refactor phase 1 execution plan"
```

## Self-Review

- Spec coverage: 已覆盖重构设计中的三大任务包：前端状态层、页面装配层、后端结构域。
- Placeholder scan: 无 `TODO` / `TBD` / “类似上文” 占位语句。
- Type consistency: 文件路径、验证命令和任务边界与设计文档保持一致，未引入新的运行时契约名称。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-31-reelstruct-refactor-phase-1.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
