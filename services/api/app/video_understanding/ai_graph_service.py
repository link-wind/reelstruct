import json
import os
import re
import time
from typing import Any, Optional

import httpx

from app.video_understanding.openai_config import openai_responses_url
from app.video_understanding.schemas import (
    GraphAggregationResult,
    ShotEvidenceGraph,
)

DEFAULT_STRUCTURE_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 90
MAX_GRAPH_AGGREGATION_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 0.4
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
_JSON_FENCE_RE = re.compile(r"^```\s*(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def parse_graph_segments(payload: Any, graph: Optional[ShotEvidenceGraph] = None) -> GraphAggregationResult:
    return GraphAggregationResult.model_validate(_normalize_graph_payload(payload, graph=graph))


def _normalize_graph_payload(payload: Any, *, graph: Optional[ShotEvidenceGraph] = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("OpenAI graph aggregation output JSON must be an object")
    shot_times = _shot_time_lookup(graph)

    return {
        "relations": _normalize_relations(payload.get("relations")),
        "beats": _normalize_beats(payload.get("beats"), shot_times=shot_times),
        "segments": _normalize_segments(payload.get("segments"), shot_times=shot_times),
        "warnings": _normalize_string_list(payload.get("warnings")),
    }


def _normalize_relations(value: Any) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return relations

    for item in value:
        if not isinstance(item, dict):
            continue
        relation = {
            "from_shot": item.get("from_shot"),
            "to_shot": item.get("to_shot"),
            "relation_type": item.get("relation_type") or item.get("type") or "relation",
            "relation_summary": _coerce_optional_text(item.get("relation_summary"))
            or _join_evidence(item.get("evidence")),
            "rhythm_change": _coerce_optional_text(item.get("rhythm_change")),
            "semantic_shift": _coerce_optional_text(item.get("semantic_shift")),
            "confidence": _coerce_confidence(item.get("confidence")),
        }
        relations.append(relation)
    return relations


def _normalize_beats(
    value: Any,
    *,
    shot_times: dict[int, tuple[float, float]],
) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return beats

    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        shot_indices = _normalize_positive_int_list(item.get("shot_indices"))
        if not shot_indices:
            continue
        beat_id = item.get("beat_id") or f"beat_{item.get('beat_index') or index}"
        inferred_start, inferred_end = _infer_time_range(shot_indices, shot_times)
        start = _coerce_non_negative_number(item.get("start"), inferred_start)
        beats.append(
            {
                "beat_id": str(beat_id),
                "label": _coerce_optional_text(item.get("label")) or str(beat_id),
                "shot_indices": shot_indices,
                "start": start,
                "end": _coerce_non_negative_number(item.get("end"), inferred_end or start),
                "function": _coerce_optional_text(item.get("function")),
                "reason": _coerce_optional_text(item.get("reason")),
                "confidence": _coerce_confidence(item.get("confidence")),
            }
        )
    return beats


def _normalize_segments(
    value: Any,
    *,
    shot_times: dict[int, tuple[float, float]],
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return segments

    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        shot_indices = _normalize_positive_int_list(item.get("shot_indices"))
        if not shot_indices:
            continue
        segment_id = item.get("segment_id") or f"seg_{item.get('segment_index') or index}"
        inferred_start, inferred_end = _infer_time_range(shot_indices, shot_times)
        start = _coerce_non_negative_number(item.get("start"), inferred_start)
        segments.append(
            {
                "segment_id": str(segment_id),
                "label": _coerce_optional_text(item.get("label")) or str(segment_id),
                "beat_ids": _normalize_string_list(item.get("beat_ids")),
                "shot_indices": shot_indices,
                "start": start,
                "end": _coerce_non_negative_number(item.get("end"), inferred_end or start),
                "purpose": _coerce_optional_text(item.get("purpose")),
                "method": _coerce_optional_text(item.get("method")),
                "evidence": _normalize_evidence_list(item.get("evidence")),
                "rhythm": _coerce_optional_text(item.get("rhythm")),
                "packaging": _coerce_optional_text(item.get("packaging")),
                "transferable_rule": _coerce_optional_text(item.get("transferable_rule")),
                "non_transferable": _coerce_optional_text(item.get("non_transferable")),
                "required_asset": _coerce_optional_text(item.get("required_asset")),
                "confidence": _coerce_confidence(item.get("confidence")),
            }
        )
    return segments


def _shot_time_lookup(graph: Optional[ShotEvidenceGraph]) -> dict[int, tuple[float, float]]:
    if graph is None:
        return {}
    return {node.shot.index: (node.shot.start, node.shot.end) for node in graph.shots}


def _infer_time_range(
    shot_indices: list[int],
    shot_times: dict[int, tuple[float, float]],
) -> tuple[float, float]:
    ranges = [shot_times[shot_index] for shot_index in shot_indices if shot_index in shot_times]
    if not ranges:
        return 0, 0
    return min(start for start, _ in ranges), max(end for _, end in ranges)


def _normalize_positive_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    normalized: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0:
            normalized.append(number)
    return normalized


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _coerce_optional_text(item))]


def _normalize_evidence_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    evidence: list[str] = []
    for item in value:
        text = _evidence_to_text(item)
        if text:
            evidence.append(text)
    return evidence


def _join_evidence(value: Any) -> str:
    return "; ".join(_normalize_evidence_list(value))


def _evidence_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return _coerce_optional_text(value)

    source = _coerce_optional_text(value.get("source"))
    detail = (
        _coerce_optional_text(value.get("text"))
        or _coerce_optional_text(value.get("summary"))
        or _coerce_optional_text(value.get("detail"))
        or _coerce_optional_text(value.get("value"))
    )
    if source and detail:
        return f"{source}: {detail}"
    if detail:
        return detail
    if source:
        return source
    return json.dumps(value, ensure_ascii=False)


def _coerce_optional_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _coerce_non_negative_number(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number < 0:
        return default
    return number


def _coerce_confidence(value: Any) -> float:
    number = _coerce_non_negative_number(value, 0)
    if number > 1:
        return 1
    return number


def aggregate_graph_structure_with_ai(graph: ShotEvidenceGraph) -> GraphAggregationResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for real AI graph aggregation")

    model = os.getenv("REELSTRUCT_STRUCTURE_MODEL", DEFAULT_STRUCTURE_MODEL)
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _build_graph_prompt(graph),
                    }
                ],
            }
        ],
    }

    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        response = _post_with_retries(client=client, api_key=api_key, payload=payload)

    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI graph aggregation response was not JSON") from exc

    output_text = _extract_output_text(response_data)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("OpenAI graph aggregation response missing output_text")

    parsed = _parse_json_output(output_text)
    return parse_graph_segments(parsed, graph=graph)


def _post_with_retries(
    *,
    client: httpx.Client,
    api_key: str,
    payload: dict[str, Any],
) -> httpx.Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_GRAPH_AGGREGATION_ATTEMPTS + 1):
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
            if status_code not in RETRYABLE_STATUS_CODES or attempt >= MAX_GRAPH_AGGREGATION_ATTEMPTS:
                detail = _safe_response_detail(exc.response)
                raise RuntimeError(
                    "OpenAI graph aggregation request failed "
                    f"with status={status_code}: {detail}"
                ) from exc
            _sleep_before_retry(attempt)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= MAX_GRAPH_AGGREGATION_ATTEMPTS:
                raise RuntimeError(f"OpenAI graph aggregation request failed: {exc}") from exc
            _sleep_before_retry(attempt)

    raise RuntimeError(f"OpenAI graph aggregation request failed: {last_error}")


def _sleep_before_retry(attempt: int) -> None:
    if RETRY_SLEEP_SECONDS <= 0:
        return
    time.sleep(RETRY_SLEEP_SECONDS * attempt)


def _build_graph_prompt(graph: ShotEvidenceGraph) -> str:
    graph_payload = graph.model_dump()
    return (
        "你是 ReelStruct 的 Shot Evidence Graph 聚合器。"
        "只能基于输入的 Shot Evidence Graph 做关系、节拍和段落聚合，不要引入外部知识，不要补写图中没有的事实。"
        "只输出严格 JSON，不要 markdown，不要解释文字。"
        "顶层字段必须且只允许包含：relations, beats, segments, warnings。"
        "relations 必须描述 shot 与 shot 的关系，字段必须使用 relation_type，不要使用 type。"
        "beats 必须表示创作节拍，字段必须使用 beat_id，不要使用 beat_index；shot_indices 必须来自输入图。"
        "segments 必须基于图中的证据聚合，字段必须使用 segment_id，不要使用 segment_index。"
        "segment.evidence 必须是字符串数组，每一项逐条引用输入中的证据或说明它来自哪里，不要输出对象数组。"
        "beats 和 segments 都必须输出 start 与 end；如果证据不足，应基于覆盖的 shot 起止时间保守填写。"
        "不要编造新的证据，不要把抽象判断当作证据。"
        "warnings 只能写关于图聚合质量、证据缺口、覆盖不足、关系不明确之类的提醒。"
        f"\n输入 Shot Evidence Graph 如下：\n{json.dumps(graph_payload, ensure_ascii=False)}"
    )


def _parse_json_output(output_text: str) -> dict[str, Any]:
    text = output_text.strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group("body").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI graph aggregation output was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("OpenAI graph aggregation output JSON must be an object")
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
