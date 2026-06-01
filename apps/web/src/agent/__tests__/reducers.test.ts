// @ts-nocheck
export {}
import test from 'node:test'
import assert from 'node:assert/strict'

const {
  agentReducer,
  initialAgentState,
  mapRuntimeState,
} = await import('../reducers.ts')
const { toolCatalog } = await import('../toolCatalog.ts')

function buildRuntimeState(
  overrides: Record<string, unknown> = {},
) {
  return {
    agent_status: "awaiting_start_confirm",
    current_plan: {
      prompt: "先看结构",
      steps: [
        {
          id: "step_1",
          tool_name: "analyze_structure",
          title: "分析结构",
          status: "pending",
        },
      ],
    },
    current_step: "",
    pending_confirmation: {
      id: "confirm_start",
      kind: "start_run",
      title: "开始执行计划？",
      message: "确认后开始运行。",
      options: [],
    },
    tool_runs: [],
    stage_results: {},
    warnings: [],
    errors: [],
    skip_reasons: [],
    ...overrides,
  }
}

test("mapRuntimeState maps runtime fields into camelCase state", () => {
  const mapped = mapRuntimeState(
    buildRuntimeState({
      current_step: "run_ocr",
      skip_reasons: ["skip asr"],
    }),
  )

  assert.equal(mapped.agentStatus, "awaiting_start_confirm")
  assert.equal(mapped.currentStep, "run_ocr")
  assert.deepEqual(mapped.skipReasons, ["skip asr"])
  assert.equal(mapped.currentPlan.prompt, "先看结构")
})

test("planningStarted clears prior runtime residue and keeps prompt", () => {
  const dirtyState = {
    ...initialAgentState,
    agentStatus: "failed" as const,
    currentPlan: {
      prompt: "旧计划",
      steps: [
        {
          id: "step_old",
          tool_name: "run_ocr",
          title: "执行 OCR",
          status: "completed" as const,
        },
      ],
    },
    currentStep: "run_ocr",
    toolRuns: [{ id: "tool_1", tool_name: "run_ocr", status: "completed", summary: "" }],
    stageResults: { ocr: { status: "completed" } },
    warnings: ["old warning"],
    errors: ["old error"],
    skipReasons: ["old skip"],
  }

  const nextState = agentReducer(dirtyState, {
    type: "planningStarted",
    payload: { prompt: "新计划" },
  })

  assert.equal(nextState.agentStatus, "planning")
  assert.equal(nextState.currentPlan.prompt, "新计划")
  assert.deepEqual(nextState.currentPlan.steps, [])
  assert.equal(nextState.currentStep, "")
  assert.deepEqual(nextState.toolRuns, [])
  assert.deepEqual(nextState.stageResults, {})
  assert.deepEqual(nextState.warnings, [])
  assert.deepEqual(nextState.errors, [])
  assert.deepEqual(nextState.skipReasons, [])
})

test("planLoaded maps runtime payload into frontend state", () => {
  const runtime = buildRuntimeState({
    tool_runs: [
      {
        id: "tool_1",
        tool_name: "analyze_structure",
        status: "running",
        summary: "正在分析",
      },
    ],
  })

  const nextState = agentReducer(initialAgentState, {
    type: "planLoaded",
    payload: runtime,
  })

  assert.equal(nextState.agentStatus, "awaiting_start_confirm")
  assert.equal(nextState.pendingConfirmation?.kind, "start_run")
  assert.equal(nextState.toolRuns[0]?.tool_name, "analyze_structure")
})

test("planFailed clears runtime residue and records latest error", () => {
  const dirtyState = {
    ...initialAgentState,
    agentStatus: "running" as const,
    currentPlan: {
      prompt: "旧计划",
      steps: [
        {
          id: "step_old",
          tool_name: "run_ocr",
          title: "执行 OCR",
          status: "running" as const,
        },
      ],
    },
    currentStep: "run_ocr",
    pendingConfirmation: {
      id: "confirm_old",
      kind: "run_ocr" as const,
      title: "继续执行 OCR？",
      message: "",
      options: [],
    },
    toolRuns: [{ id: "tool_1", tool_name: "run_ocr", status: "running", summary: "" }],
    stageResults: { ocr: { status: "running" } },
    warnings: ["old warning"],
    errors: ["old error"],
    skipReasons: ["old skip"],
  }

  const nextState = agentReducer(dirtyState, {
    type: "planFailed",
    payload: { error: "请求失败" },
  })

  assert.equal(nextState.agentStatus, "failed")
  assert.equal(nextState.currentPlan.prompt, "旧计划")
  assert.deepEqual(nextState.currentPlan.steps, [])
  assert.equal(nextState.currentStep, "")
  assert.equal(nextState.pendingConfirmation, null)
  assert.deepEqual(nextState.toolRuns, [])
  assert.deepEqual(nextState.stageResults, {})
  assert.deepEqual(nextState.warnings, [])
  assert.deepEqual(nextState.skipReasons, [])
  assert.deepEqual(nextState.errors, ["请求失败"])
})

test("confirmationCleared removes pending confirmation only", () => {
  const stateWithConfirmation = agentReducer(initialAgentState, {
    type: "planLoaded",
    payload: buildRuntimeState(),
  })

  const nextState = agentReducer(stateWithConfirmation, {
    type: "confirmationCleared",
  })

  assert.equal(nextState.pendingConfirmation, null)
  assert.equal(nextState.agentStatus, "awaiting_start_confirm")
})

test("toolCatalog stays aligned with backend stage-level registry snapshot", () => {
  assert.deepEqual(
    toolCatalog.map((tool: {
      name: string
      stage: string
      confirmationKind: string
    }) => ({
      name: tool.name,
      stage: tool.stage,
      confirmationKind: tool.confirmationKind,
    })),
    [
      { name: "analyze_structure", stage: "structure", confirmationKind: "" },
      { name: "run_ocr", stage: "structure", confirmationKind: "run_ocr" },
      { name: "run_asr", stage: "structure", confirmationKind: "run_asr" },
      {
        name: "complete_materials",
        stage: "materials",
        confirmationKind: "material_strategy",
      },
      {
        name: "generate_result",
        stage: "output",
        confirmationKind: "generate_result",
      },
    ],
  )
})
