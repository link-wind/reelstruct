import type {
  AgentMessage,
  AgentPlan,
  AgentStatus,
  ConfirmationRequest,
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
        pendingConfirmation: null,
        errors: [...state.errors, action.payload.error],
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

    default:
      return state
  }
}
