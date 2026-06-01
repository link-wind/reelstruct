# Agent / Tool 驱动工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 ReelStruct 当前的按钮驱动工作台升级成第一版 agent / tool 驱动工作流，支持 prompt 级阶段控制、左侧轻对话 + 输入框上方确认菜单、右侧保留 tab 的简洁执行区。

**Architecture:** 后端新增一层 agent 编排和阶段级 tool 执行入口，但继续复用现有结构拆解、OCR、ASR、素材补全和结果生成能力。前端新增 `agent/` 状态层和 `useAgentWorkspace.ts` 主 hook，把原有 `useReelStruct.ts` 从总控流程中降级为底层 API / 数据能力来源。

**Tech Stack:** Next.js、React、TypeScript、FastAPI、Pydantic、pytest、tsc

---

## File Structure

### Create

- `services/api/app/agent/models.py`
  - 定义 `AgentStatus`、`AgentPlan`、`AgentToolCall`、`ConfirmationRequest`、`ExecutionEvent`、`WorkspaceRuntimeState`
- `services/api/app/agent/policy.py`
  - 定义确认策略：哪些 tool 自动执行，哪些必须等待确认
- `services/api/app/agent/tool_registry.py`
  - 注册阶段级 tool 元数据
- `services/api/app/agent/tool_executor.py`
  - 调用阶段级 tool，统一标准化结果
- `services/api/app/agent/orchestrator.py`
  - 根据 prompt 和 runtime state 决定下一步
- `services/api/app/tools/analyze_structure.py`
- `services/api/app/tools/run_ocr.py`
- `services/api/app/tools/run_asr.py`
- `services/api/app/tools/complete_materials.py`
- `services/api/app/tools/generate_result.py`
- `services/api/tests/test_agent_orchestrator.py`
- `services/api/tests/test_tool_executor.py`
- `apps/web/src/agent/types.ts`
- `apps/web/src/agent/toolCatalog.ts`
- `apps/web/src/agent/reducers.ts`
- `apps/web/src/agent/planner.ts`
- `apps/web/src/hooks/useAgentWorkspace.ts`
- `apps/web/src/components/Workspace/AgentConfirmationMenu.tsx`
- `apps/web/src/components/Workspace/AgentConversationPanel.tsx`
- `apps/web/src/components/Workspace/ExecutionWorkspacePanel.tsx`
- `apps/web/src/components/Workspace/useExecutionTabs.ts`
- `apps/web/src/agent/__tests__/reducers.test.ts`

### Modify

- `services/api/app/main.py`
  - 增加 agent runtime 相关接口
- `services/api/app/models.py`
  - 复用已有 preview/run 响应模型，必要时加 agent 兼容字段
- `services/api/app/workflow_service.py`
  - 为 `generate_result` tool 提供稳定入口
- `services/api/app/structure_service.py`
  - 为 `analyze_structure`、`complete_materials` 提供稳定入口
- `services/api/app/video_understanding/ocr_service.py`
  - 为 `run_ocr` tool 提供稳定入口
- `services/api/app/video_understanding/asr_service.py`
  - 为 `run_asr` tool 提供稳定入口
- `apps/web/src/components/Views/WorkspaceView.tsx`
  - 从 `useReelStruct` 迁到 `useAgentWorkspace`
- `apps/web/src/components/MainApp.tsx`
  - 接入新的 workspace 主 hook
- `apps/web/src/hooks/useReelStructApi.ts`
  - 保持为 API 层，新增 agent runtime 请求
- `apps/web/src/app/globals.css`
  - 新增轻量对话区、输入框上方菜单、右侧简洁 tab 样式
- `apps/web/scripts/check-workspace-shell.mjs`
  - 更新 UI 回归检查

### Keep But De-scope From Control Layer

- `apps/web/src/hooks/useReelStruct.ts`
  - 先保留，后续逐步降级；本计划不要求一次删掉
- `apps/web/src/components/Workspace/AgentActionPanel.tsx`
  - 先不直接删，迁移后可作为旧实现对照
- `apps/web/src/components/Workspace/WorkPanel.tsx`
  - 保留数据映射和部分视图逻辑，但收缩为右侧执行区底层组件来源

---

### Task 1: 后端 agent runtime 数据模型

**Files:**
- Create: `services/api/app/agent/models.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_agent_orchestrator.py`

- [ ] **Step 1: 写失败测试，锁定 runtime state 基本结构**

```python
from app.agent.models import WorkspaceRuntimeState, ConfirmationRequest


def test_workspace_runtime_state_defaults():
    state = WorkspaceRuntimeState()

    assert state.agent_status == "idle"
    assert state.current_plan.steps == []
    assert state.pending_confirmation is None
    assert state.tool_runs == []


def test_confirmation_request_keeps_menu_options():
    confirmation = ConfirmationRequest(
        id="confirm_ocr",
        kind="run_ocr",
        title="继续执行 OCR？",
        message="OCR 能补强标题和包装证据。",
        options=[
            {"id": "continue", "label": "继续执行", "description": "补强证据后继续", "action": "continue"},
            {"id": "skip", "label": "跳过 OCR", "description": "直接进入下一步", "action": "skip"},
        ],
    )

    assert confirmation.kind == "run_ocr"
    assert confirmation.options[0].action == "continue"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py -q -k runtime_state`

Expected: FAIL，提示 `app.agent.models` 或 `WorkspaceRuntimeState` 不存在

- [ ] **Step 3: 最小实现 `agent/models.py`**

```python
from typing import Literal, Optional

from pydantic import BaseModel, Field


AgentStatus = Literal[
    "idle",
    "planning",
    "awaiting_start_confirm",
    "running",
    "awaiting_tool_confirm",
    "paused",
    "completed",
    "failed",
]


class ConfirmationOption(BaseModel):
    id: str
    label: str
    description: str = ""
    action: Literal["continue", "skip", "replan", "pause"]


class ConfirmationRequest(BaseModel):
    id: str
    kind: Literal["start_run", "run_ocr", "run_asr", "material_strategy", "generate_result"]
    title: str
    message: str = ""
    options: list[ConfirmationOption] = Field(default_factory=list)


class AgentPlanStep(BaseModel):
    id: str
    tool_name: str
    title: str
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "pending"


class AgentPlan(BaseModel):
    prompt: str = ""
    steps: list[AgentPlanStep] = Field(default_factory=list)


class ToolRunRecord(BaseModel):
    id: str
    tool_name: str
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "pending"
    summary: str = ""


class WorkspaceRuntimeState(BaseModel):
    agent_status: AgentStatus = "idle"
    current_plan: AgentPlan = Field(default_factory=AgentPlan)
    current_step: str = ""
    pending_confirmation: Optional[ConfirmationRequest] = None
    tool_runs: list[ToolRunRecord] = Field(default_factory=list)
    stage_results: dict[str, dict] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skip_reasons: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py -q -k runtime_state`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/app/agent/models.py services/api/tests/test_agent_orchestrator.py services/api/app/main.py
git commit -m "feat: add agent runtime state models"
```

---

### Task 2: 后端 tool registry 和确认策略

**Files:**
- Create: `services/api/app/agent/policy.py`
- Create: `services/api/app/agent/tool_registry.py`
- Test: `services/api/tests/test_agent_orchestrator.py`

- [ ] **Step 1: 写失败测试，锁定第一版阶段级 tool 集**

```python
from app.agent.tool_registry import build_default_tool_registry
from app.agent.policy import requires_confirmation


def test_default_tool_registry_contains_five_stage_tools():
    registry = build_default_tool_registry()

    assert [tool.name for tool in registry] == [
        "analyze_structure",
        "run_ocr",
        "run_asr",
        "complete_materials",
        "generate_result",
    ]


def test_confirmation_policy_blocks_high_value_tools():
    assert requires_confirmation("run_ocr") is True
    assert requires_confirmation("run_asr") is True
    assert requires_confirmation("generate_result") is True
    assert requires_confirmation("analyze_structure") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py -q -k registry`

Expected: FAIL，提示 `tool_registry` 或 `policy` 不存在

- [ ] **Step 3: 最小实现 registry 与 policy**

```python
# services/api/app/agent/tool_registry.py
from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    title: str
    stage: str
    description: str = ""


def build_default_tool_registry() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="analyze_structure", title="结构拆解", stage="structure"),
        ToolDefinition(name="run_ocr", title="OCR 证据", stage="structure"),
        ToolDefinition(name="run_asr", title="ASR 证据", stage="structure"),
        ToolDefinition(name="complete_materials", title="素材补全", stage="materials"),
        ToolDefinition(name="generate_result", title="结果生成", stage="output"),
    ]
```

```python
# services/api/app/agent/policy.py
CONFIRMATION_TOOLS = {"run_ocr", "run_asr", "complete_materials", "generate_result"}


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in CONFIRMATION_TOOLS
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py -q -k registry`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/app/agent/tool_registry.py services/api/app/agent/policy.py services/api/tests/test_agent_orchestrator.py
git commit -m "feat: add agent tool registry and confirmation policy"
```

---

### Task 3: 后端 tool executor 和稳定领域入口

**Files:**
- Create: `services/api/app/agent/tool_executor.py`
- Create: `services/api/app/tools/analyze_structure.py`
- Create: `services/api/app/tools/run_ocr.py`
- Create: `services/api/app/tools/run_asr.py`
- Create: `services/api/app/tools/complete_materials.py`
- Create: `services/api/app/tools/generate_result.py`
- Modify: `services/api/app/structure_service.py`
- Modify: `services/api/app/workflow_service.py`
- Test: `services/api/tests/test_tool_executor.py`

- [ ] **Step 1: 写失败测试，锁定 executor 的标准输出**

```python
from app.agent.tool_executor import execute_tool


def test_execute_tool_returns_stage_result_payload():
    payload = {
        "sample": {"title": "样例", "duration": 20, "shot_count": 6},
        "content": {"topic": "新任务", "available_assets": ["开头吸引镜头"]},
    }

    result = execute_tool("analyze_structure", payload)

    assert result["tool_name"] == "analyze_structure"
    assert result["stage"] == "structure"
    assert "preview" in result["data"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_tool_executor.py -q`

Expected: FAIL，提示 executor 不存在

- [ ] **Step 3: 为每个阶段级 tool 建稳定入口**

```python
# services/api/app/tools/analyze_structure.py
from app.models import StructurePreviewRequest
from app.structure_service import build_structure_preview


def run(payload: dict) -> dict:
    request = StructurePreviewRequest(**payload)
    preview = build_structure_preview(
        request.sample,
        request.content,
        mapping_overrides=request.mapping_overrides,
        material_request_sheet=request.material_request_sheet,
        supplement_selections=request.supplement_selections,
        variant=request.variant,
        use_ai_transfer_explanation=False,
    )
    return {"preview": preview.model_dump()}
```

```python
# services/api/app/tools/generate_result.py
from app.models import PreviewRunRequest
from app.workflow_service import create_demo_run_from_preview


def run(payload: dict) -> dict:
    request = PreviewRunRequest(**payload)
    response = create_demo_run_from_preview(request)
    return {"run": response.model_dump()}
```

- [ ] **Step 4: 实现 executor 注册调用**

```python
from app.tools import analyze_structure, complete_materials, generate_result, run_asr, run_ocr

_TOOL_MAP = {
    "analyze_structure": ("structure", analyze_structure.run),
    "run_ocr": ("structure", run_ocr.run),
    "run_asr": ("structure", run_asr.run),
    "complete_materials": ("materials", complete_materials.run),
    "generate_result": ("output", generate_result.run),
}


def execute_tool(tool_name: str, payload: dict) -> dict:
    stage, handler = _TOOL_MAP[tool_name]
    return {
        "tool_name": tool_name,
        "stage": stage,
        "data": handler(payload),
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_tool_executor.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/agent/tool_executor.py services/api/app/tools services/api/tests/test_tool_executor.py services/api/app/structure_service.py services/api/app/workflow_service.py
git commit -m "feat: add stage-level tool executor"
```

---

### Task 4: 后端 orchestrator 和 agent runtime API

**Files:**
- Create: `services/api/app/agent/orchestrator.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_agent_orchestrator.py`

- [ ] **Step 1: 写失败测试，锁定第一次计划和确认行为**

```python
from app.agent.models import WorkspaceRuntimeState
from app.agent.orchestrator import plan_from_prompt


def test_plan_from_prompt_creates_start_confirmation():
    state = WorkspaceRuntimeState()
    result = plan_from_prompt(
        prompt="先看结构和 OCR，不要跑 ASR，再决定是否生成结果",
        state=state,
    )

    assert result.agent_status == "awaiting_start_confirm"
    assert result.pending_confirmation is not None
    assert [step.tool_name for step in result.current_plan.steps] == [
        "analyze_structure",
        "run_ocr",
        "complete_materials",
        "generate_result",
    ]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py -q -k plan_from_prompt`

Expected: FAIL

- [ ] **Step 3: 最小实现 prompt 规划**

```python
from app.agent.models import AgentPlan, AgentPlanStep, ConfirmationRequest, WorkspaceRuntimeState


def plan_from_prompt(prompt: str, state: WorkspaceRuntimeState) -> WorkspaceRuntimeState:
    steps = [AgentPlanStep(id="step_structure", tool_name="analyze_structure", title="结构拆解")]
    if "不要跑 ASR" not in prompt:
        steps.append(AgentPlanStep(id="step_asr", tool_name="run_asr", title="ASR 证据"))
    if "OCR" in prompt or "ocr" in prompt.lower():
        steps.append(AgentPlanStep(id="step_ocr", tool_name="run_ocr", title="OCR 证据"))
    steps.extend(
        [
            AgentPlanStep(id="step_materials", tool_name="complete_materials", title="素材补全"),
            AgentPlanStep(id="step_result", tool_name="generate_result", title="结果生成"),
        ]
    )
    return state.model_copy(
        update={
            "agent_status": "awaiting_start_confirm",
            "current_plan": AgentPlan(prompt=prompt, steps=steps),
            "pending_confirmation": ConfirmationRequest(
                id="confirm_start",
                kind="start_run",
                title="开始执行当前计划？",
                message="确认后将按计划依次执行。",
                options=[
                    {"id": "continue", "label": "开始执行", "description": "按当前计划推进", "action": "continue"},
                    {"id": "replan", "label": "修改计划", "description": "调整执行顺序", "action": "replan"},
                ],
            ),
        }
    )
```

- [ ] **Step 4: 新增最小 API 入口**

```python
@app.post("/api/agent/plan")
def create_agent_plan(request: dict) -> dict:
    prompt = request.get("prompt", "")
    state = WorkspaceRuntimeState(**request.get("state", {}))
    return plan_from_prompt(prompt, state).model_dump()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py -q -k plan_from_prompt`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/agent/orchestrator.py services/api/app/main.py services/api/tests/test_agent_orchestrator.py
git commit -m "feat: add agent plan orchestration endpoint"
```

---

### Task 5: 前端 agent 状态层和 reducer

**Files:**
- Create: `apps/web/src/agent/types.ts`
- Create: `apps/web/src/agent/reducers.ts`
- Create: `apps/web/src/agent/toolCatalog.ts`
- Test: `apps/web/src/agent/__tests__/reducers.test.ts`

- [ ] **Step 1: 写失败测试，锁定 reducer 基本流转**

```ts
import { agentReducer, initialAgentState } from "../reducers"

test("plan loaded enters awaiting start confirm", () => {
  const state = agentReducer(initialAgentState, {
    type: "planLoaded",
    payload: {
      agent_status: "awaiting_start_confirm",
      current_plan: { prompt: "先看结构和 OCR", steps: [] },
      pending_confirmation: { id: "confirm_start", kind: "start_run", title: "开始执行？", message: "", options: [] },
    },
  })

  expect(state.agentStatus).toBe("awaiting_start_confirm")
  expect(state.pendingConfirmation?.kind).toBe("start_run")
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && npm test -- src/agent/__tests__/reducers.test.ts`

Expected: FAIL

- [ ] **Step 3: 最小实现 types 和 reducer**

```ts
export type AgentStatus =
  | "idle"
  | "planning"
  | "awaiting_start_confirm"
  | "running"
  | "awaiting_tool_confirm"
  | "paused"
  | "completed"
  | "failed"

export type ConfirmationOption = {
  id: string
  label: string
  description: string
  action: "continue" | "skip" | "replan" | "pause"
}

export type ConfirmationRequest = {
  id: string
  kind: "start_run" | "run_ocr" | "run_asr" | "material_strategy" | "generate_result"
  title: string
  message: string
  options: ConfirmationOption[]
}
```

```ts
export const initialAgentState = {
  agentStatus: "idle" as const,
  currentPlan: { prompt: "", steps: [] },
  pendingConfirmation: null as ConfirmationRequest | null,
  toolRuns: [],
  stageResults: {},
}

export function agentReducer(state = initialAgentState, action: any) {
  switch (action.type) {
    case "planLoaded":
      return {
        ...state,
        agentStatus: action.payload.agent_status,
        currentPlan: action.payload.current_plan,
        pendingConfirmation: action.payload.pending_confirmation,
      }
    default:
      return state
  }
}
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && npm test -- src/agent/__tests__/reducers.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/agent/types.ts apps/web/src/agent/reducers.ts apps/web/src/agent/toolCatalog.ts apps/web/src/agent/__tests__/reducers.test.ts
git commit -m "feat: add frontend agent state reducer"
```

---

### Task 6: 前端 `useAgentWorkspace` 主 hook 和 API 串联

**Files:**
- Create: `apps/web/src/hooks/useAgentWorkspace.ts`
- Modify: `apps/web/src/hooks/useReelStructApi.ts`
- Modify: `apps/web/src/components/MainApp.tsx`
- Test: `apps/web/src/agent/__tests__/reducers.test.ts`

- [ ] **Step 1: 写失败测试，锁定 hook 的首次计划加载行为**

```ts
test("submitPrompt requests agent plan and stores confirmation", async () => {
  const fakeResponse = {
    agent_status: "awaiting_start_confirm",
    current_plan: { prompt: "先看结构", steps: [] },
    pending_confirmation: { id: "confirm_start", kind: "start_run", title: "开始执行？", message: "", options: [] },
  }

  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => fakeResponse,
  } as Response)

  // render hook and call submitPrompt
  // expect pendingConfirmation.kind === "start_run"
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && npm test -- src/agent/__tests__/reducers.test.ts`

Expected: FAIL，提示 `useAgentWorkspace` 未实现

- [ ] **Step 3: 最小实现 API 层**

```ts
export async function requestAgentPlan(body: { prompt: string; state?: Record<string, unknown> }) {
  return requestJson("/api/agent/plan", {
    method: "POST",
    body,
  })
}
```

- [ ] **Step 4: 实现主 hook**

```ts
export function useAgentWorkspace() {
  const [state, dispatch] = useReducer(agentReducer, initialAgentState)

  const submitPrompt = async (prompt: string) => {
    dispatch({ type: "planningStarted" })
    const payload = await requestAgentPlan({ prompt, state })
    dispatch({ type: "planLoaded", payload })
  }

  return {
    state,
    submitPrompt,
  }
}
```

- [ ] **Step 5: 再跑测试确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && npm test -- src/agent/__tests__/reducers.test.ts`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/hooks/useAgentWorkspace.ts apps/web/src/hooks/useReelStructApi.ts apps/web/src/components/MainApp.tsx apps/web/src/agent/__tests__/reducers.test.ts
git commit -m "feat: add agent workspace hook"
```

---

### Task 7: 左侧轻对话区和输入框上方确认菜单

**Files:**
- Create: `apps/web/src/components/Workspace/AgentConfirmationMenu.tsx`
- Create: `apps/web/src/components/Workspace/AgentConversationPanel.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/app/globals.css`
- Test: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: 写失败 UI 回归检查**

```js
const panelText = await page.locator('[aria-label="智能助手对话区"]').innerText()
if (!panelText.includes("继续向智能助手输入指令")) {
  throw new Error("agent 对话区未渲染输入区域")
}

const confirmationMenu = page.locator('[data-agent-confirmation-menu="true"]')
await expect(confirmationMenu).toBeVisible()
```

- [ ] **Step 2: 运行脚本确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && node scripts/check-workspace-shell.mjs`

Expected: FAIL，提示没有确认菜单或左侧区仍是旧结构

- [ ] **Step 3: 实现菜单组件**

```tsx
export default function AgentConfirmationMenu({ request, onSelect }: Props) {
  if (!request) return null
  return (
    <div data-agent-confirmation-menu="true" className="agent-confirmation-menu">
      <div className="agent-confirmation-title">{request.title}</div>
      {request.options.map((option) => (
        <button key={option.id} type="button" className="agent-confirmation-option" onClick={() => onSelect(option)}>
          <strong>{option.label}</strong>
          <span>{option.description}</span>
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: 实现轻对话面板**

```tsx
export default function AgentConversationPanel({ messages, pendingConfirmation, onConfirm, onSendMessage }: Props) {
  return (
    <aside className="agent-conversation-panel" aria-label="智能助手对话区">
      <div className="agent-message-list">
        {messages.map((message) => (
          <div key={message.id} className={`agent-message ${message.role}`}>
            {message.body}
          </div>
        ))}
      </div>
      <div className="agent-input-shell">
        <textarea aria-label="继续向智能助手输入指令" />
        <AgentConfirmationMenu request={pendingConfirmation} onSelect={onConfirm} />
      </div>
    </aside>
  )
}
```

- [ ] **Step 5: 再跑脚本确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && node scripts/check-workspace-shell.mjs`

Expected: PASS，确认左侧存在轻对话区和输入框上方菜单

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/Workspace/AgentConfirmationMenu.tsx apps/web/src/components/Workspace/AgentConversationPanel.tsx apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/app/globals.css apps/web/scripts/check-workspace-shell.mjs
git commit -m "feat: add lightweight agent conversation panel"
```

---

### Task 8: 右侧保留 tab 的简洁执行区

**Files:**
- Create: `apps/web/src/components/Workspace/ExecutionWorkspacePanel.tsx`
- Create: `apps/web/src/components/Workspace/useExecutionTabs.ts`
- Modify: `apps/web/src/components/Workspace/WorkPanel.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `apps/web/src/app/globals.css`
- Test: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: 写失败 UI 检查，锁定 tab + 主内容区结构**

```js
await page.getByRole("tab", { name: "打开结构拆解标签" }).click()
const structureTabText = await page.locator("main").innerText()
if (!structureTabText.includes("当前阶段")) {
  throw new Error("右侧执行区缺少轻状态栏")
}
if (!structureTabText.includes("主内容区")) {
  throw new Error("右侧执行区缺少单一主内容区")
}
```

- [ ] **Step 2: 运行脚本确认失败**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && node scripts/check-workspace-shell.mjs`

Expected: FAIL

- [ ] **Step 3: 实现简洁执行区组件**

```tsx
export default function ExecutionWorkspacePanel({ activeTab, tabs, stageTitle, stageStatus, children, summaryLines }: Props) {
  return (
    <section className="execution-workspace-panel" aria-label="当前工作情况">
      <header className="execution-workspace-header">
        <div>
          <span>当前阶段</span>
          <h2>{stageTitle}</h2>
        </div>
        <span>{stageStatus}</span>
      </header>
      <div className="execution-tabs" role="tablist">
        {tabs.map((tab) => (
          <button key={tab.key} role="tab" aria-selected={tab.key === activeTab}>
            {tab.label}
          </button>
        ))}
      </div>
      <div className="execution-main-content">{children}</div>
      <div className="execution-summary-lines">
        {summaryLines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 4: 再跑脚本确认通过**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && node scripts/check-workspace-shell.mjs`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/Workspace/ExecutionWorkspacePanel.tsx apps/web/src/components/Workspace/useExecutionTabs.ts apps/web/src/components/Workspace/WorkPanel.tsx apps/web/src/components/Views/WorkspaceView.tsx apps/web/src/app/globals.css apps/web/scripts/check-workspace-shell.mjs
git commit -m "feat: simplify execution workspace tabs"
```

---

### Task 9: Agent 工作台主线接管 + 全量回归

**Files:**
- Modify: `apps/web/src/components/MainApp.tsx`
- Modify: `apps/web/src/components/Views/WorkspaceView.tsx`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_agent_orchestrator.py`
- Test: `services/api/tests/test_tool_executor.py`
- Test: `apps/web/scripts/check-workspace-shell.mjs`

- [ ] **Step 1: 写回归断言，确认主入口已走新 hook**

```js
const bodyText = await page.locator("main").innerText()
if (!bodyText.includes("继续向智能助手输入指令")) {
  throw new Error("workspace 未切换到 agent 驱动入口")
}
```

- [ ] **Step 2: 运行后端测试**

Run: `cd /Users/linkwind/Code/ReelStruct/services/api && PYTHONPATH=. .venv/bin/python -m pytest tests/test_agent_orchestrator.py tests/test_tool_executor.py -q`

Expected: PASS

- [ ] **Step 3: 运行前端类型检查**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && npm run typecheck`

Expected: PASS

- [ ] **Step 4: 运行工作台脚本回归**

Run: `cd /Users/linkwind/Code/ReelStruct/apps/web && node scripts/check-workspace-shell.mjs`

Expected: PASS

- [ ] **Step 5: 手工验证关键流程**

Run:

```bash
1. 打开 http://127.0.0.1:3000
2. 输入“先看结构和 OCR，不要跑 ASR，再决定是否生成结果”
3. 确认首次执行
4. 验证左侧出现 OCR 确认菜单
5. 验证右侧 tab 仍可切换，且内容区简洁
```

Expected:

- 左侧是轻对话，不是旧重面板
- 菜单贴近输入框上方
- 右侧保留 tab，但不再铺满重卡片

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/MainApp.tsx apps/web/src/components/Views/WorkspaceView.tsx services/api/app/main.py
git commit -m "feat: switch workspace to agent tool runtime"
```

---

## Self-Review

### Spec coverage

- `tool 驱动 + agent 编排`：Task 1-4
- `左侧轻对话 + 小菜单`：Task 7
- `右侧保留 tab 但更简洁`：Task 8
- `统一 runtime state`：Task 1、Task 5、Task 9
- `prompt 影响执行策略`：Task 4、Task 6

### Placeholder scan

- 已补具体文件路径
- 已补关键测试样例
- 已补执行命令和预期

### Type consistency

- 后端统一使用 `WorkspaceRuntimeState` / `ConfirmationRequest`
- 前端统一使用 `AgentStatus` / `ConfirmationRequest`
- 阶段级 tool 名称保持一致：
  - `analyze_structure`
  - `run_ocr`
  - `run_asr`
  - `complete_materials`
  - `generate_result`
