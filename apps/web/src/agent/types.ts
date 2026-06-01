export type AgentStatus =
  | "idle"
  | "planning"
  | "awaiting_start_confirm"
  | "running"
  | "awaiting_tool_confirm"
  | "paused"
  | "completed"
  | "failed"

export type ConfirmationAction = "continue" | "skip" | "replan" | "pause"

export type ConfirmationKind =
  | "start_run"
  | "run_ocr"
  | "run_asr"
  | "material_strategy"
  | "generate_result"

export type ToolConfirmationKind = Exclude<ConfirmationKind, "start_run">

export type ConfirmationOption = {
  id: string
  label: string
  description: string
  action: ConfirmationAction
}

export type ConfirmationRequest = {
  id: string
  kind: ConfirmationKind
  title: string
  message: string
  options: ConfirmationOption[]
}

export type AgentPlanStepStatus =
  | "pending"
  | "running"
  | "completed"
  | "skipped"
  | "failed"

export type AgentPlanStep = {
  id: string
  tool_name: string
  title: string
  status: AgentPlanStepStatus
}

export type AgentPlan = {
  prompt: string
  steps: AgentPlanStep[]
}

export type ToolRunStatus = AgentPlanStepStatus

export type ToolRunRecord = {
  id: string
  tool_name: string
  status: ToolRunStatus
  summary: string
}

export type WorkspaceRuntimeState = {
  agent_status: AgentStatus
  current_plan: AgentPlan
  current_step: string
  pending_confirmation: ConfirmationRequest | null
  tool_runs: ToolRunRecord[]
  stage_results: Record<string, Record<string, unknown>>
  warnings: string[]
  errors: string[]
  skip_reasons: string[]
}

export type AgentMessageRole = "user" | "assistant" | "system"

export type AgentMessage = {
  id: string
  role: AgentMessageRole
  content: string
  createdAt: string
}
