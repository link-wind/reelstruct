from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str = ""
    action: Literal["continue", "skip", "replan", "pause"]


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["start_run", "run_ocr", "run_asr", "material_strategy", "generate_result"]
    title: str
    message: str = ""
    options: list[ConfirmationOption] = Field(default_factory=list)


class AgentPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool_name: str
    title: str
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "pending"


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = ""
    steps: list[AgentPlanStep] = Field(default_factory=list)


class ToolRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool_name: str
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "pending"
    summary: str = ""


class WorkspaceRuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_status: AgentStatus = "idle"
    current_plan: AgentPlan = Field(default_factory=AgentPlan)
    current_step: str = ""
    pending_confirmation: Optional[ConfirmationRequest] = None
    tool_runs: list[ToolRunRecord] = Field(default_factory=list)
    stage_results: dict[str, dict] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    skip_reasons: list[str] = Field(default_factory=list)
