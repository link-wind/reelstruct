import json
import os
import re
from typing import Any, Optional

import httpx

from app.domain.shared.domain_models import (
    NewContentInput,
    TemplateStructure,
    TransferExplanation,
    TransferMapping,
    TransferPlan,
)
from app.video_understanding.openai_config import openai_responses_url
from app.video_understanding.schemas import ShotEvidenceGraph

DEFAULT_TRANSFER_EXPLAINER_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 90
_JSON_FENCE_RE = re.compile(r"^```\s*(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def explain_transfer_with_ai(
    *,
    template: TemplateStructure,
    content: NewContentInput,
    transfer_plan: TransferPlan,
    graph: Optional[ShotEvidenceGraph],
    variant: str,
) -> TransferPlan:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return transfer_plan

    try:
        explanations = _request_transfer_explanations(
            api_key=api_key,
            template=template,
            content=content,
            transfer_plan=transfer_plan,
            graph=graph,
            variant=variant,
        )
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        return _plan_with_failure_warnings(transfer_plan, f"AI transfer explanation failed: {exc}")

    explanation_lookup = {item.slot_id: item for item in explanations if item.slot_id}
    mappings = [
        mapping.model_copy(
            update={
                "explanation": explanation_lookup.get(mapping.slot_id)
                or _fallback_explanation_for_mapping(mapping)
            }
        )
        for mapping in transfer_plan.mappings
    ]
    return transfer_plan.model_copy(update={"mappings": mappings})


def _request_transfer_explanations(
    *,
    api_key: str,
    template: TemplateStructure,
    content: NewContentInput,
    transfer_plan: TransferPlan,
    graph: Optional[ShotEvidenceGraph],
    variant: str,
) -> list[TransferExplanation]:
    model = os.getenv("REELSTRUCT_TRANSFER_EXPLAINER_MODEL") or os.getenv("REELSTRUCT_STRUCTURE_MODEL") or DEFAULT_TRANSFER_EXPLAINER_MODEL
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _build_prompt(
                            template=template,
                            content=content,
                            transfer_plan=transfer_plan,
                            graph=graph,
                            variant=variant,
                        ),
                    }
                ],
            }
        ],
    }

    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        response = client.post(
            openai_responses_url(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    output_text = _extract_output_text(response.json())
    if not output_text.strip():
        raise ValueError("OpenAI transfer explanation response missing output_text")
    return parse_transfer_explanations(_parse_json_output(output_text))


def parse_transfer_explanations(payload: Any) -> list[TransferExplanation]:
    if not isinstance(payload, dict):
        raise ValueError("OpenAI transfer explanation output JSON must be an object")
    raw_items = payload.get("explanations")
    if not isinstance(raw_items, list):
        return []

    explanations: list[TransferExplanation] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        explanations.append(
            TransferExplanation(
                slot_id=_coerce_text(item.get("slot_id")),
                source_observation=_coerce_text(item.get("source_observation") or item.get("sample_observation")),
                transferable_principle=_coerce_text(item.get("transferable_principle") or item.get("transfer_principle")),
                target_expression=_coerce_text(item.get("target_expression") or item.get("target_message")),
                asset_plan=_coerce_text(item.get("asset_plan") or item.get("asset_strategy")),
                gap_handling=_coerce_text(item.get("gap_handling") or item.get("fallback_strategy")),
                reasoning=_coerce_text(item.get("reasoning") or item.get("reason")),
                confidence=_coerce_confidence(item.get("confidence")),
                warnings=_coerce_string_list(item.get("warnings")),
            )
        )
    return explanations


def build_fallback_transfer_explanation(
    *,
    mapping: TransferMapping,
    source_observation: str = "",
    transferable_principle: str = "",
    gap_handling: str = "",
    warnings: Optional[list[str]] = None,
) -> TransferExplanation:
    return TransferExplanation(
        slot_id=mapping.slot_id,
        source_observation=source_observation or mapping.source_method,
        transferable_principle=transferable_principle or mapping.reasoning,
        target_expression=mapping.target_message,
        asset_plan=mapping.asset_strategy or mapping.packaging_plan,
        gap_handling=gap_handling or mapping.fallback_strategy,
        reasoning=mapping.reasoning,
        confidence=0.55,
        warnings=warnings or [],
    )


def _fallback_explanation_for_mapping(mapping: TransferMapping) -> TransferExplanation:
    if mapping.explanation.target_expression:
        return mapping.explanation
    return build_fallback_transfer_explanation(mapping=mapping)


def _plan_with_failure_warnings(transfer_plan: TransferPlan, warning: str) -> TransferPlan:
    return transfer_plan.model_copy(
        update={
            "mappings": [
                mapping.model_copy(
                    update={
                        "explanation": build_fallback_transfer_explanation(
                            mapping=mapping,
                            warnings=[*mapping.explanation.warnings, warning],
                        )
                    }
                )
                for mapping in transfer_plan.mappings
            ]
        }
    )


def _build_prompt(
    *,
    template: TemplateStructure,
    content: NewContentInput,
    transfer_plan: TransferPlan,
    graph: Optional[ShotEvidenceGraph],
    variant: str,
) -> str:
    graph_payload = _compact_graph_payload(graph)
    payload = {
        "template": template.model_dump(exclude={"shot_evidence_graph"}),
        "target_content": content.model_dump(),
        "transfer_plan": transfer_plan.model_dump(),
        "shot_evidence_graph": graph_payload,
        "variant": variant,
    }
    return (
        "你是 ReelStruct 的 AI 结构迁移解释器。"
        "你的任务不是重新拆视频，也不是重新生成时间线，而是解释每个结构槽位如何从样例迁移到新内容。"
        "必须基于输入证据：slot 样例证据、shot/unit understanding、OCR、ASR、relations、新内容 brief、可用素材和素材缺口。"
        "不要照搬样例商品、人物、门店名或原文案；只迁移结构功能和表达方法。"
        "每个 mapping 都必须输出一条 explanation。"
        "只输出严格 JSON，不要 markdown，不要解释文字。"
        "顶层字段必须且只允许包含 explanations。"
        "每个 explanation 字段必须包含：slot_id, source_observation, transferable_principle, "
        "target_expression, asset_plan, gap_handling, reasoning, confidence, warnings。"
        "target_expression 必须是面向新主题/商品的具体表达，不要只写抽象方法。"
        "warnings 只能写证据不足、OCR/ASR 不稳定、素材缺口等提醒。"
        f"\n输入如下：\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _compact_graph_payload(graph: Optional[ShotEvidenceGraph]) -> dict[str, Any]:
    if graph is None:
        return {}
    return {
        "shots": [
            {
                "shot": node.shot.model_dump(),
                "ocr_texts": [item.model_dump() for item in node.ocr_texts[:8]],
                "transcript_texts": [item.model_dump() for item in node.transcript_texts[:8]],
                "understanding": node.understanding.model_dump() if node.understanding else {},
            }
            for node in graph.shots[:40]
        ],
        "analysis_units": [
            {
                "unit_id": unit.unit_id,
                "shot_indices": unit.shot_indices,
                "start": unit.start,
                "end": unit.end,
                "understanding": unit.understanding.model_dump() if unit.understanding else {},
                "ocr_texts": [item.model_dump() for item in unit.ocr_texts[:8]],
                "transcript_texts": [item.model_dump() for item in unit.transcript_texts[:8]],
            }
            for unit in getattr(graph, "analysis_units", [])[:24]
        ],
        "relations": [relation.model_dump() for relation in graph.relations[:80]],
        "warnings": graph.warnings,
    }


def _parse_json_output(output_text: str) -> dict[str, Any]:
    text = output_text.strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group("body").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI transfer explanation output was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI transfer explanation output JSON must be an object")
    return parsed


def _extract_output_text(response_data: dict[str, Any]) -> str:
    output_text = response_data.get("output_text")
    if isinstance(output_text, str):
        return output_text
    chunks: list[str] = []
    output = response_data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
    return "".join(chunks)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _coerce_text(item))]


def _coerce_confidence(value: Any) -> float:
    if isinstance(value, bool):
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number < 0:
        return 0
    if number > 1:
        return 1
    return number
