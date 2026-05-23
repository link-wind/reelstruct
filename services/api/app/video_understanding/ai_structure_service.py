import json
import os
import re
from typing import Any

import httpx

from app.video_understanding.openai_config import openai_responses_url
from app.video_understanding.schemas import AIStructureAnalysis, ShotEvidence, VideoSignal

DEFAULT_STRUCTURE_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 90
_JSON_FENCE_RE = re.compile(r"^```\s*(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def decompose_video_structure_with_ai(
    *,
    title: str,
    signal: VideoSignal,
    evidence: list[ShotEvidence],
    transcript_summary: str,
) -> AIStructureAnalysis:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for real AI video structure decomposition")

    model = os.getenv("REELSTRUCT_STRUCTURE_MODEL", DEFAULT_STRUCTURE_MODEL)
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": _build_prompt(title, signal, evidence, transcript_summary)}],
            }
        ],
    }

    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        try:
            response = client.post(
                openai_responses_url(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _safe_response_detail(exc.response)
            raise RuntimeError(
                "OpenAI structure request failed "
                f"with status={exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenAI structure request failed: {exc}") from exc

    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI structure response was not JSON") from exc

    output_text = _extract_output_text(response_data)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("OpenAI structure response missing output_text")

    parsed = _parse_json_output(output_text)
    try:
        return AIStructureAnalysis.model_validate(parsed)
    except Exception as exc:
        raise ValueError(f"OpenAI structure output failed schema validation: {exc}") from exc


def _build_prompt(title: str, signal: VideoSignal, evidence: list[ShotEvidence], transcript_summary: str) -> str:
    input_payload = {
        "title": title,
        "video_signal": signal.model_dump(),
        "shot_evidence": [item.model_dump() for item in evidence],
        "transcript_summary": transcript_summary,
    }
    return (
        "你是短视频结构拆解专家。请基于真实视频证据拆解创作结构，不要套固定四段模板。\n"
        "你的任务是总结这条样例视频的结构组织方式，让后续系统可以迁移方法，但不能照抄具体商品信息。\n"
        "请输出严格 JSON，不要输出 markdown，不要输出解释文字。\n"
        "顶层字段必须且只允许包含：source, headline, segments, rhythm_structure, packaging_structure, confidence, warnings。\n"
        "source 必须等于 ai。segments 必须是非空数组。\n"
        "每个 segment 必须包含：id, label, type, start, end, shot_indices, purpose, method, evidence, rhythm, packaging, required_asset, transferable_rule, non_transferable, confidence。\n"
        "shot_indices 必须引用输入里真实存在的镜头编号，start/end 要与这些镜头大致对应。\n"
        "rhythm_structure 包含：summary, peak_position, slowdown_position。\n"
        "packaging_structure 包含：caption_density, title_style, transition_style, cover_style。\n"
        "confidence 为 0 到 1 的数字，warnings 为字符串数组。\n"
        f"输入证据如下：\n{json.dumps(input_payload, ensure_ascii=False)}"
    )


def _parse_json_output(output_text: str) -> dict[str, Any]:
    text = output_text.strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group("body").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI structure output was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("OpenAI structure output JSON must be an object")
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
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
    return "".join(chunks)


def _safe_response_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except json.JSONDecodeError:
        return response.text[:500]

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message[:500]
        return json.dumps(data, ensure_ascii=False)[:500]
    return str(data)[:500]
