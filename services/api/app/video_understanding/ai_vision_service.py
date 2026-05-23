import base64
import json
import os
from pathlib import Path
import re
from typing import Any

import httpx

from app.video_understanding.schemas import KeyframeEvidence, ShotVisualAnalysis

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_VISION_MODEL = "gpt-4.1-mini"
OPENAI_TIMEOUT_SECONDS = 60
_JSON_FENCE_RE = re.compile(r"^```\s*(?:json)?\s*(?P<body>.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def analyze_keyframe_visuals(keyframes: list[KeyframeEvidence]) -> list[ShotVisualAnalysis]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to analyze keyframe visuals")

    model = os.getenv("REELSTRUCT_VISION_MODEL", DEFAULT_VISION_MODEL)
    analyses: list[ShotVisualAnalysis] = []
    with httpx.Client(timeout=OPENAI_TIMEOUT_SECONDS) as client:
        for keyframe in keyframes:
            analyses.append(_analyze_one_keyframe(client, api_key, model, keyframe))
    return analyses


def _analyze_one_keyframe(
    client: httpx.Client,
    api_key: str,
    model: str,
    keyframe: KeyframeEvidence,
) -> ShotVisualAnalysis:
    image_url = _keyframe_to_data_url(keyframe)
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _build_prompt(keyframe.shot_index)},
                    {"type": "input_image", "image_url": image_url, "detail": "low"},
                ],
            }
        ],
    }

    try:
        response = client.post(
            OPENAI_RESPONSES_URL,
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
            f"OpenAI vision request failed for shot_index={keyframe.shot_index} "
            f"with status={exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"OpenAI vision request failed for shot_index={keyframe.shot_index}: {exc}") from exc

    try:
        response_data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI vision response was not JSON for shot_index={keyframe.shot_index}") from exc

    output_text = _extract_output_text(response_data)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError(f"OpenAI vision response missing output_text for shot_index={keyframe.shot_index}")

    analysis_data = _parse_json_output(output_text, keyframe.shot_index)
    analysis_data["shot_index"] = keyframe.shot_index
    return ShotVisualAnalysis.model_validate(analysis_data)


def _keyframe_to_data_url(keyframe: KeyframeEvidence) -> str:
    image_path = Path(keyframe.local_path)
    if not image_path.is_file():
        raise FileNotFoundError(
            f"keyframe image not found for shot_index={keyframe.shot_index}: {image_path}"
        )

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _build_prompt(shot_index: int) -> str:
    return (
        "Analyze this video keyframe for a product/video-structure understanding pipeline. "
        f"It belongs to shot_index={shot_index}. Return only strict JSON with exactly these keys: "
        "visual_summary, subject_type, scene_type, packaging_signals, confidence, warnings. "
        "Use a concise visual_summary grounded only in the image. "
        "subject_type and scene_type should be short strings. "
        "packaging_signals and warnings must be arrays of strings. "
        "confidence must be a number from 0 to 1. Do not include markdown or extra text."
    )


def _parse_json_output(output_text: str, shot_index: int) -> dict[str, Any]:
    text = output_text.strip()
    match = _JSON_FENCE_RE.match(text)
    if match:
        text = match.group("body").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI vision output was not valid JSON for shot_index={shot_index}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"OpenAI vision output JSON must be an object for shot_index={shot_index}")
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
