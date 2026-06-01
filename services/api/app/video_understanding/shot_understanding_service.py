import base64
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Optional

import httpx

from app.video_understanding.openai_config import openai_responses_url
from app.video_understanding.schemas import (
    AnalysisUnit,
    AnalysisUnitUnderstanding,
    FrameEvidence,
    FrameOCRText,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotUnderstanding,
)

DEFAULT_SHOT_UNDERSTANDING_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 90
MAX_SHOT_UNDERSTANDING_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 0.4
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
_JSON_FENCE_RE = re.compile(r"^```\s*(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL | re.IGNORECASE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_OCR_SYMBOL_NOISE_RE = re.compile(r"[×_\\|/]")
_PROMPT_OCR_MIN_CONFIDENCE = 0.6


def understand_shots_with_ai(graph: ShotEvidenceGraph) -> ShotEvidenceGraph:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to understand shots with AI")

    model = (
        os.getenv("REELSTRUCT_SHOT_UNDERSTANDING_MODEL")
        or os.getenv("REELSTRUCT_VISION_MODEL")
        or DEFAULT_SHOT_UNDERSTANDING_MODEL
    )
    if graph.analysis_units:
        return _understand_units_with_ai(graph=graph, api_key=api_key, model=model)

    understood_nodes: list[ShotEvidenceNode] = []
    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        for node in graph.shots:
            try:
                understanding = _understand_one_shot(
                    client=client,
                    api_key=api_key,
                    model=model,
                    node=node,
                )
            except (FileNotFoundError, RuntimeError, ValueError) as exc:
                understanding = ShotUnderstanding(
                    shot_index=node.shot.index,
                    warnings=[f"shot understanding failed: {exc}"],
                )
            understood_nodes.append(
                node.model_copy(
                    update={"understanding": understanding}
                )
            )

    return graph.model_copy(update={"shots": understood_nodes})


def _understand_units_with_ai(*, graph: ShotEvidenceGraph, api_key: str, model: str) -> ShotEvidenceGraph:
    understood_units: list[AnalysisUnit] = []
    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        for unit in graph.analysis_units:
            try:
                understanding = _understand_one_unit(
                    client=client,
                    api_key=api_key,
                    model=model,
                    unit=unit,
                )
            except (FileNotFoundError, RuntimeError, ValueError) as exc:
                understanding = AnalysisUnitUnderstanding(
                    unit_id=unit.unit_id,
                    warnings=[f"unit understanding failed: {exc}"],
                )
            understood_units.append(unit.model_copy(update={"understanding": understanding}))

    shot_updates = _unit_understandings_by_shot(understood_units)
    understood_nodes = [
        node.model_copy(
            update={
                "understanding": shot_updates.get(node.shot.index)
                or node.understanding
                or ShotUnderstanding(shot_index=node.shot.index)
            }
        )
        for node in graph.shots
    ]
    return graph.model_copy(update={"analysis_units": understood_units, "shots": understood_nodes})


def _understand_one_unit(
    *,
    client: httpx.Client,
    api_key: str,
    model: str,
    unit: AnalysisUnit,
) -> AnalysisUnitUnderstanding:
    if not unit.representative_frames:
        return AnalysisUnitUnderstanding(
            unit_id=unit.unit_id,
            warnings=["analysis unit has no representative frames for visual understanding"],
        )

    content: list[dict[str, Any]] = [{"type": "input_text", "text": _build_unit_prompt(unit)}]
    for frame in unit.representative_frames:
        content.append({"type": "input_image", "image_url": _frame_to_data_url(frame), "detail": "low"})

    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }

    response = _post_with_retries(client=client, api_key=api_key, payload=payload, shot_index=unit.shot_indices[0])
    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI unit understanding response was not JSON for unit_id={unit.unit_id}") from exc

    output_text = _extract_output_text(response_data)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError(f"OpenAI unit understanding response missing output_text for unit_id={unit.unit_id}")

    data = _normalize_understanding_payload(_parse_json_output(output_text, unit.shot_indices[0]))
    data["unit_id"] = unit.unit_id
    return AnalysisUnitUnderstanding.model_validate(data)


def _unit_understandings_by_shot(units: list[AnalysisUnit]) -> dict[int, ShotUnderstanding]:
    lookup: dict[int, ShotUnderstanding] = {}
    for unit in units:
        understanding = unit.understanding or AnalysisUnitUnderstanding(unit_id=unit.unit_id)
        for shot_index in unit.shot_indices:
            lookup[shot_index] = ShotUnderstanding(
                shot_index=shot_index,
                visual_summary=understanding.visual_summary,
                text_summary=understanding.text_summary,
                subject=understanding.subject,
                scene=understanding.scene,
                action=understanding.action,
                packaging_signals=understanding.packaging_signals,
                creative_function_hint=understanding.creative_function_hint,
                confidence=understanding.confidence,
                warnings=[
                    f"understood from analysis unit {unit.unit_id} covering shots {unit.shot_indices}",
                    *understanding.warnings,
                ],
            )
    return lookup


def _understand_one_shot(
    *,
    client: httpx.Client,
    api_key: str,
    model: str,
    node: ShotEvidenceNode,
) -> ShotUnderstanding:
    if not node.frames:
        return ShotUnderstanding(
            shot_index=node.shot.index,
            warnings=["shot has no extracted frames for visual understanding"],
        )

    content: list[dict[str, Any]] = [{"type": "input_text", "text": _build_prompt(node)}]
    for frame in node.frames:
        content.append({"type": "input_image", "image_url": _frame_to_data_url(frame), "detail": "low"})

    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }

    response = _post_with_retries(client=client, api_key=api_key, payload=payload, shot_index=node.shot.index)

    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI shot understanding response was not JSON for shot_index={node.shot.index}") from exc

    output_text = _extract_output_text(response_data)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError(f"OpenAI shot understanding response missing output_text for shot_index={node.shot.index}")

    data = _normalize_understanding_payload(_parse_json_output(output_text, node.shot.index))
    data["shot_index"] = node.shot.index
    return ShotUnderstanding.model_validate(data)


def _post_with_retries(
    *,
    client: httpx.Client,
    api_key: str,
    payload: dict[str, Any],
    shot_index: int,
) -> httpx.Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_SHOT_UNDERSTANDING_ATTEMPTS + 1):
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
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status_code = exc.response.status_code
            if status_code not in RETRYABLE_STATUS_CODES or attempt >= MAX_SHOT_UNDERSTANDING_ATTEMPTS:
                detail = _safe_response_detail(exc.response)
                raise RuntimeError(
                    f"OpenAI shot understanding request failed for shot_index={shot_index} "
                    f"with status={status_code}: {detail}"
                ) from exc
            _sleep_before_retry(attempt)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= MAX_SHOT_UNDERSTANDING_ATTEMPTS:
                raise RuntimeError(f"OpenAI shot understanding request failed for shot_index={shot_index}: {exc}") from exc
            _sleep_before_retry(attempt)

    raise RuntimeError(f"OpenAI shot understanding request failed for shot_index={shot_index}: {last_error}")


def _sleep_before_retry(attempt: int) -> None:
    if RETRY_SLEEP_SECONDS <= 0:
        return
    time.sleep(RETRY_SLEEP_SECONDS * attempt)


def _build_prompt(node: ShotEvidenceNode) -> str:
    frame_notes = [
        {
            "frame_index": frame.frame_index,
            "role": frame.role,
            "time": frame.time,
        }
        for frame in node.frames
    ]
    ocr_notes = [
        {
            "frame_index": item.frame_index,
            "frame_time": item.frame_time,
            "text": item.text,
            "position": item.position,
            "confidence": item.confidence,
        }
        for item in _prompt_ocr_items(node.ocr_texts)
    ]
    transcript_notes = [
        {
            "text": item.text,
            "source_start": item.source_start,
            "source_end": item.source_end,
            "overlap_ratio": item.overlap_ratio,
        }
        for item in node.transcript_texts
    ]
    return (
        "你是 ReelStruct 的单镜头理解器。"
        "你会看到同一个 shot 的多帧图片、OCR 可见文字，以及和该 shot 时间重叠的 ASR 口播文本。"
        "请基于图片、时间信息、OCR 和 ASR 文本理解这个镜头。"
        "OCR 文本是画面可见文字证据；ASR 文本只能作为口播证据，不要当作画面里可见文字。"
        "不要判断整条视频结构，不要编造证据里没有的信息。"
        "只输出严格 JSON，不要 markdown，不要解释文字。"
        "JSON 字段名保持英文，但所有自然语言字段的值必须使用简体中文。"
        "visual_summary、text_summary、subject、scene、action、packaging_signals、warnings 的值都必须用中文。"
        "creative_function_hint 只能保留下面列出的英文枚举值，其他字段禁止输出英文描述。"
        "字段必须且只允许包含：visual_summary, text_summary, subject, scene, action, "
        "packaging_signals, creative_function_hint, confidence, warnings。"
        "visual_summary 用一句话概括画面；text_summary 可综合图片中可见字幕和 ASR 口播大意，没有就留空。"
        "subject 写主要主体；scene 写场景类型；action 写主体正在做什么。"
        "packaging_signals 写字幕、标题条、贴纸、价格牌、产品露出、转场感等可见包装元素。"
        "creative_function_hint 只能从 hook, pain_point, product_intro, product_demo, proof, comparison, "
        "transition, offer, cta, atmosphere, unknown 中选一个。"
        "confidence 必须是 0 到 1 的数字，warnings 必须是字符串数组。"
        f"\nshot_index={node.shot.index}, start={node.shot.start}, end={node.shot.end}, "
        f"duration={node.shot.duration}, frames={json.dumps(frame_notes, ensure_ascii=False)}, "
        f"ocr_texts={json.dumps(ocr_notes, ensure_ascii=False)}, "
        f"transcript_texts={json.dumps(transcript_notes, ensure_ascii=False)}"
    )


def _build_unit_prompt(unit: AnalysisUnit) -> str:
    frame_notes = [
        {
            "shot_index": frame.shot_index,
            "frame_index": frame.frame_index,
            "role": frame.role,
            "time": frame.time,
        }
        for frame in unit.representative_frames
    ]
    ocr_notes = [
        {
            "shot_index": item.shot_index,
            "frame_index": item.frame_index,
            "frame_time": item.frame_time,
            "text": item.text,
            "position": item.position,
            "confidence": item.confidence,
        }
        for item in _prompt_ocr_items(unit.ocr_texts)
    ]
    transcript_notes = [
        {
            "shot_index": item.shot_index,
            "text": item.text,
            "source_start": item.source_start,
            "source_end": item.source_end,
            "overlap_ratio": item.overlap_ratio,
        }
        for item in unit.transcript_texts
    ]
    return (
        "你是 ReelStruct 的分析单元理解器。"
        "一个 analysis unit 由多个连续 shot 组成，用来减少长视频逐镜头理解的碎片化。"
        "你会看到该 unit 的代表帧、OCR 可见文字，以及和该 unit 时间重叠的 ASR 口播文本。"
        "请理解这一组连续镜头作为一个创作片段的画面内容、文本信息和创作功能。"
        "OCR 文本是画面可见文字证据；ASR 文本只能作为口播证据，不要当作画面里可见文字。"
        "不要判断整条视频结构，不要编造证据里没有的信息。"
        "只输出严格 JSON，不要 markdown，不要解释文字。"
        "JSON 字段名保持英文，但所有自然语言字段的值必须使用简体中文。"
        "visual_summary、text_summary、subject、scene、action、packaging_signals、warnings 的值都必须用中文。"
        "creative_function_hint 只能保留下面列出的英文枚举值，其他字段禁止输出英文描述。"
        "字段必须且只允许包含：visual_summary, text_summary, subject, scene, action, "
        "packaging_signals, creative_function_hint, confidence, warnings。"
        "visual_summary 用一句话概括这个连续片段；text_summary 可综合图片中可见字幕和 ASR 口播大意，没有就留空。"
        "subject 写主要主体；scene 写场景类型；action 写主体正在做什么。"
        "packaging_signals 写字幕、标题条、贴纸、价格牌、产品露出、转场感等可见包装元素。"
        "creative_function_hint 只能从 hook, pain_point, product_intro, product_demo, proof, comparison, "
        "transition, offer, cta, atmosphere, unknown 中选一个。"
        "confidence 必须是 0 到 1 的数字，warnings 必须是字符串数组。"
        f"\nunit_id={unit.unit_id}, shot_indices={unit.shot_indices}, start={unit.start}, end={unit.end}, "
        f"duration={unit.duration}, representative_frames={json.dumps(frame_notes, ensure_ascii=False)}, "
        f"ocr_texts={json.dumps(ocr_notes, ensure_ascii=False)}, "
        f"transcript_texts={json.dumps(transcript_notes, ensure_ascii=False)}"
    )


def _prompt_ocr_items(items: list[FrameOCRText]) -> list[FrameOCRText]:
    best_by_text: dict[str, FrameOCRText] = {}
    for item in items:
        text = item.text.strip()
        if not text:
            continue
        if item.confidence < _PROMPT_OCR_MIN_CONFIDENCE:
            continue
        if _looks_like_ocr_noise(text=text, confidence=item.confidence):
            continue

        key = _normalize_ocr_text_key(text)
        previous = best_by_text.get(key)
        if previous is None or item.confidence > previous.confidence:
            best_by_text[key] = item.model_copy(update={"text": text})

    return sorted(
        best_by_text.values(),
        key=lambda item: (item.shot_index, item.frame_time, item.frame_index, -item.confidence),
    )


def _normalize_ocr_text_key(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def _looks_like_ocr_noise(*, text: str, confidence: float) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return True
    has_cjk = bool(_CJK_RE.search(compact))
    has_artifact_symbol = bool(_OCR_SYMBOL_NOISE_RE.search(compact))
    if has_cjk:
        return confidence < 0.7 and has_artifact_symbol
    if has_artifact_symbol and len(compact) <= 12:
        return True
    return False


def _normalize_understanding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "visual_summary": _coerce_text(payload.get("visual_summary")),
        "text_summary": _coerce_text(payload.get("text_summary")),
        "subject": _coerce_text(payload.get("subject") or payload.get("subject_type")),
        "scene": _coerce_text(payload.get("scene") or payload.get("scene_type")),
        "action": _coerce_text(payload.get("action")),
        "packaging_signals": _coerce_string_list(payload.get("packaging_signals")),
        "creative_function_hint": _coerce_text(payload.get("creative_function_hint")),
        "confidence": _coerce_confidence(payload.get("confidence")),
        "warnings": _coerce_string_list(payload.get("warnings")),
    }


def _frame_to_data_url(frame: FrameEvidence) -> str:
    image_path = Path(frame.local_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"frame image not found for shot_index={frame.shot_index}: {image_path}")

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _parse_json_output(output_text: str, shot_index: int) -> dict[str, Any]:
    text = output_text.strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group("body").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI shot understanding output was not valid JSON for shot_index={shot_index}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"OpenAI shot understanding output JSON must be an object for shot_index={shot_index}")
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
