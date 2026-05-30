from uuid import uuid4

from app.agent.models import AgentPlan, AgentPlanStep, ConfirmationRequest, WorkspaceRuntimeState


def plan_from_prompt(prompt: str, state: WorkspaceRuntimeState) -> WorkspaceRuntimeState:
    normalized_prompt = prompt.strip()
    steps: list[AgentPlanStep] = []

    def add_step(tool_name: str, title: str) -> None:
        steps.append(
            AgentPlanStep(
                id=f"step_{tool_name}_{uuid4().hex[:8]}",
                tool_name=tool_name,
                title=title,
            )
        )

    add_step("analyze_structure", "分析结构")

    if _mentions_ocr(normalized_prompt):
        add_step("run_ocr", "执行 OCR")

    if not _skips_asr(normalized_prompt):
        add_step("run_asr", "执行 ASR")

    add_step("complete_materials", "补全素材")
    add_step("generate_result", "生成结果")

    return state.model_copy(
        update={
            "agent_status": "awaiting_start_confirm",
            "current_plan": AgentPlan(prompt=prompt, steps=steps),
            "pending_confirmation": ConfirmationRequest(
                id=f"confirm_start_{uuid4().hex[:8]}",
                kind="start_run",
                title="开始执行计划？",
                message="已生成执行计划，确认后开始运行。",
            ),
            "current_step": "",
        }
    )


def _mentions_ocr(prompt: str) -> bool:
    lowered = prompt.lower()
    return "ocr" in lowered


def _skips_asr(prompt: str) -> bool:
    lowered = prompt.lower()
    return "不要跑 asr" in lowered or "不要 asr" in lowered or "跳过 asr" in lowered
