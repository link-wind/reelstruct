import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.video_understanding.schemas import FrameEvidence, FrameOCRText


OCR_ENABLED_ENV = "REELSTRUCT_OCR_ENABLED"
OCR_LANG_ENV = "REELSTRUCT_OCR_LANG"
OCR_USE_ANGLE_CLS_ENV = "REELSTRUCT_OCR_USE_ANGLE_CLS"


@dataclass(frozen=True)
class OCRConfig:
    enabled: bool = False
    lang: str = "ch"
    use_angle_cls: bool = True


@dataclass
class OCRResult:
    texts: list[FrameOCRText] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def ocr_is_enabled() -> bool:
    return load_ocr_config().enabled


def load_ocr_config() -> OCRConfig:
    return OCRConfig(
        enabled=_read_bool_env(OCR_ENABLED_ENV, default=False),
        lang=os.getenv(OCR_LANG_ENV, "ch").strip() or "ch",
        use_angle_cls=_read_bool_env(OCR_USE_ANGLE_CLS_ENV, default=True),
    )


def recognize_frames_with_ocr(frames: list[FrameEvidence]) -> OCRResult:
    config = load_ocr_config()
    if not config.enabled:
        return OCRResult()

    try:
        PaddleOCR = _load_paddle_ocr()
        engine = _create_paddle_ocr_engine(PaddleOCR, config)
    except Exception as exc:
        return OCRResult(warnings=[f"OCR 未完成：PaddleOCR 初始化失败：{exc}"])

    texts: list[FrameOCRText] = []
    warnings: list[str] = []
    for frame in frames:
        image_path = Path(frame.local_path)
        if not image_path.is_file():
            warnings.append(
                f"OCR 未完成：frame image not found for shot_index={frame.shot_index} frame_index={frame.frame_index}"
            )
            continue
        try:
            raw_result = _run_paddle_ocr(engine, image_path, config)
        except Exception as exc:
            warnings.append(f"OCR 未完成：shot_index={frame.shot_index} frame_index={frame.frame_index}：{exc}")
            continue
        normalized = _normalize_ocr_result(raw_result, frame)
        if normalized:
            texts.extend(normalized)
            continue
        for scale in (0.5, 1.5, 2.0):
            try:
                scaled_image_path = _prepare_scaled_ocr_image(image_path, scale=scale, suffix=f"_ocr_scale_{scale:.2f}")
            except Exception as exc:
                warnings.append(f"OCR 大字 fallback 未完成：shot_index={frame.shot_index} frame_index={frame.frame_index}：{exc}")
                continue
            try:
                raw_result = _run_paddle_ocr(engine, scaled_image_path, config)
            except Exception as exc:
                warnings.append(f"OCR 未完成：shot_index={frame.shot_index} frame_index={frame.frame_index}：{exc}")
                continue
            normalized = _normalize_ocr_result(raw_result, frame)
            if normalized:
                texts.extend(normalized)
                break
    return OCRResult(texts=texts, warnings=warnings)


def _prepare_scaled_ocr_image(image_path: Path, *, scale: float, suffix: str) -> Path:
    from PIL import Image

    scaled_path = image_path.with_name(f"{image_path.stem}{suffix}{image_path.suffix}")
    if scaled_path.is_file():
        return scaled_path
    with Image.open(image_path) as image:
        width, height = image.size
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        resized = image.resize(new_size, Image.Resampling.LANCZOS)
        resized.save(scaled_path)
    return scaled_path


def _load_paddle_ocr() -> Any:
    from paddleocr import PaddleOCR

    return PaddleOCR


def _create_paddle_ocr_engine(provider: Any, config: OCRConfig) -> Any:
    modern_kwargs = {
        "lang": config.lang,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": config.use_angle_cls,
    }
    try:
        return provider(**modern_kwargs)
    except (TypeError, ValueError):
        try:
            return provider(lang=config.lang, use_angle_cls=config.use_angle_cls)
        except (TypeError, ValueError):
            return provider(lang=config.lang)


def _run_paddle_ocr(engine: Any, image_path: Path, config: OCRConfig) -> Any:
    try:
        return engine.ocr(str(image_path), cls=config.use_angle_cls)
    except (TypeError, ValueError) as exc:
        if "cls" not in str(exc) and "Unknown argument" not in str(exc):
            raise
        if hasattr(engine, "predict"):
            return engine.predict(str(image_path), use_textline_orientation=config.use_angle_cls)
        return engine.ocr(str(image_path))


def _normalize_ocr_result(raw_result: Any, frame: FrameEvidence) -> list[FrameOCRText]:
    lines: list[FrameOCRText] = []
    for box, text, confidence in _iter_ocr_lines(raw_result):
        cleaned_text = str(text).strip()
        if not cleaned_text:
            continue
        lines.append(
            FrameOCRText(
                shot_index=frame.shot_index,
                frame_index=frame.frame_index,
                frame_time=frame.time,
                text=cleaned_text,
                position=_position_to_text(box),
                confidence=_clamp_confidence(confidence),
            )
        )
    return lines


def _iter_ocr_lines(raw_result: Any) -> list[tuple[Any, str, float]]:
    if isinstance(raw_result, dict):
        return _iter_dict_ocr_lines(raw_result)

    lines: list[tuple[Any, str, float]] = []
    pages = raw_result if isinstance(raw_result, list) else []
    for page in pages:
        if isinstance(page, dict):
            lines.extend(_iter_dict_ocr_lines(page))
            continue
        if not isinstance(page, list):
            continue
        for item in page:
            parsed = _parse_old_format_item(item)
            if parsed is not None:
                lines.append(parsed)
    return lines


def _iter_dict_ocr_lines(raw_result: dict[str, Any]) -> list[tuple[Any, str, float]]:
    texts = raw_result.get("rec_texts") or []
    scores = raw_result.get("rec_scores") or []
    boxes = raw_result.get("rec_polys") or raw_result.get("dt_polys") or []
    lines: list[tuple[Any, str, float]] = []
    if not isinstance(texts, list):
        return lines
    for index, text in enumerate(texts):
        confidence = scores[index] if isinstance(scores, list) and index < len(scores) else 0
        box = boxes[index] if isinstance(boxes, list) and index < len(boxes) else ""
        lines.append((box, str(text), _safe_float(confidence)))
    return lines


def _parse_old_format_item(item: Any) -> Optional[tuple[Any, str, float]]:
    if not isinstance(item, list) or len(item) < 2:
        return None
    box = item[0]
    payload = item[1]
    if not isinstance(payload, (list, tuple)) or len(payload) < 2:
        return None
    return box, str(payload[0]), _safe_float(payload[1])


def _position_to_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _clamp_confidence(value: float) -> float:
    if value < 0:
        return 0
    if value > 1:
        return 1
    return value


def _read_bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
