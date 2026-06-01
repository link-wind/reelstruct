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

    return WorkspaceRuntimeState(
        agent_status="awaiting_start_confirm",
        current_plan=AgentPlan(prompt=prompt, steps=steps),
        current_step="",
        pending_confirmation=ConfirmationRequest(
            id=f"confirm_start_{uuid4().hex[:8]}",
            kind="start_run",
            title="开始执行计划？",
            message="已生成执行计划，确认后开始运行。",
            options=[
                {
                    "id": "continue",
                    "label": "继续执行",
                    "description": "按当前计划开始运行结构拆解和结果生成。",
                    "action": "continue",
                },
                {
                    "id": "pause",
                    "label": "稍后再说",
                    "description": "先保留计划，稍后再决定是否执行。",
                    "action": "pause",
                },
            ],
        ),
        tool_runs=[],
        stage_results={},
        warnings=[],
        errors=[],
        skip_reasons=[],
    )


def _mentions_ocr(prompt: str) -> bool:
    lowered = prompt.lower()
    return "ocr" in lowered


def _skips_asr(prompt: str) -> bool:
    lowered = prompt.lower()
    return "不要跑 asr" in lowered or "不要 asr" in lowered or "跳过 asr" in lowered
