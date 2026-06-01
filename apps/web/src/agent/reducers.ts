import type {
  AgentMessage,
  AgentPlan,
  AgentStatus,
  ConfirmationRequest,
  AgentPlanStepStatus,
  ToolRunRecord,
  WorkspaceRuntimeState,
} from "./types"

export type AgentWorkspaceState = {
  agentStatus: AgentStatus
  currentPlan: AgentPlan
  currentStep: string
  pendingConfirmation: ConfirmationRequest | null
  toolRuns: ToolRunRecord[]
  stageResults: Record<string, Record<string, unknown>>
  warnings: string[]
  errors: string[]
  skipReasons: string[]
  messages: AgentMessage[]
}

export const initialAgentState: AgentWorkspaceState = {
  agentStatus: "idle",
  currentPlan: {
    prompt: "",
    steps: [],
  },
  currentStep: "",
  pendingConfirmation: null,
  toolRuns: [],
  stageResults: {},
  warnings: [],
  errors: [],
  skipReasons: [],
  messages: [],
}

export type AgentWorkspaceAction =
  | {
      type: "planningStarted"
      payload?: {
        prompt?: string
      }
    }
  | {
      type: "planLoaded"
      payload: WorkspaceRuntimeState
    }
  | {
      type: "planFailed"
      payload: {
        error: string
      }
    }
  | {
      type: "confirmationCleared"
    }
  | {
      type: "messageAdded"
      payload: AgentMessage
    }
  | {
      type: "runtimePatched"
      payload: Partial<
        Omit<AgentWorkspaceState, "messages" | "currentPlan"> & {
          currentPlan?: Partial<AgentPlan>
          toolRun?: ToolRunRecord
          currentStepStatus?: AgentPlanStepStatus
        }
      >
    }

export function mapRuntimeState(
  runtime: WorkspaceRuntimeState,
): Omit<AgentWorkspaceState, "messages"> {
  return {
    agentStatus: runtime.agent_status,
    currentPlan: runtime.current_plan,
    currentStep: runtime.current_step,
    pendingConfirmation: runtime.pending_confirmation,
    toolRuns: runtime.tool_runs,
    stageResults: runtime.stage_results,
    warnings: runtime.warnings,
    errors: runtime.errors,
    skipReasons: runtime.skip_reasons,
  }
}

export function agentReducer(
  state: AgentWorkspaceState,
  action: AgentWorkspaceAction,
): AgentWorkspaceState {
  switch (action.type) {
    case "planningStarted":
      return {
        ...state,
        agentStatus: "planning",
        currentPlan: {
          prompt: action.payload?.prompt ?? state.currentPlan.prompt,
          steps: [],
        },
        currentStep: "",
        pendingConfirmation: null,
        toolRuns: [],
        stageResults: {},
        warnings: [],
        errors: [],
        skipReasons: [],
      }

    case "planLoaded":
      return {
        ...state,
        ...mapRuntimeState(action.payload),
      }

    case "planFailed":
      return {
        ...state,
        agentStatus: "failed",
        currentPlan: {
          prompt: state.currentPlan.prompt,
          steps: [],
        },
        currentStep: "",
        toolRuns: [],
        stageResults: {},
        warnings: [],
        skipReasons: [],
        pendingConfirmation: null,
        errors: [action.payload.error],
      }

    case "confirmationCleared":
      return {
        ...state,
        pendingConfirmation: null,
      }

    case "messageAdded":
      return {
        ...state,
        messages: [...state.messages, action.payload],
      }

    case "runtimePatched": {
      const nextPlan = action.payload.currentPlan
        ? {
            ...state.currentPlan,
            ...action.payload.currentPlan,
          }
        : state.currentPlan

      const nextToolRuns = action.payload.toolRun
        ? [...state.toolRuns.filter((item) => item.tool_name !== action.payload.toolRun?.tool_name), action.payload.toolRun]
        : state.toolRuns

      const nextPlanSteps: AgentPlan["steps"] = action.payload.currentStep
        ? nextPlan.steps.map((step) =>
            step.tool_name === action.payload.currentStep
              ? {
                  ...step,
                  status: action.payload.currentStepStatus ?? step.status,
                }
              : action.payload.currentStepStatus === "running" && step.status === "running"
                ? { ...step, status: "completed" }
                : step,
          )
        : nextPlan.steps

      return {
        ...state,
        agentStatus: action.payload.agentStatus ?? state.agentStatus,
        currentStep: action.payload.currentStep ?? state.currentStep,
        pendingConfirmation:
          action.payload.pendingConfirmation === undefined
            ? state.pendingConfirmation
            : action.payload.pendingConfirmation,
        toolRuns: nextToolRuns,
        stageResults: action.payload.stageResults ?? state.stageResults,
        warnings: action.payload.warnings ?? state.warnings,
        errors: action.payload.errors ?? state.errors,
        skipReasons: action.payload.skipReasons ?? state.skipReasons,
        currentPlan: {
          ...nextPlan,
          steps: nextPlanSteps,
        },
      }
    }

    default:
      return state
  }
}
