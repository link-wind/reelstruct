import sys
import types
from pathlib import Path

from app.video_understanding.schemas import FrameEvidence, FrameOCRText


def _clear_ocr_env(monkeypatch):
    for name in (
        "REELSTRUCT_OCR_ENABLED",
        "REELSTRUCT_OCR_LANG",
        "REELSTRUCT_OCR_USE_ANGLE_CLS",
    ):
        monkeypatch.delenv(name, raising=False)


def _frame(path: Path) -> FrameEvidence:
    return FrameEvidence(
        shot_index=1,
        frame_index=2,
        time=1.25,
        role="middle",
        local_path=str(path),
        public_url="/keyframes/shot.jpg",
    )


def test_ocr_is_disabled_by_default(monkeypatch):
    _clear_ocr_env(monkeypatch)

    from app.video_understanding.ocr_service import ocr_is_enabled

    assert ocr_is_enabled() is False


def test_load_ocr_config_defaults_to_chinese(monkeypatch):
    _clear_ocr_env(monkeypatch)

    from app.video_understanding.ocr_service import load_ocr_config

    config = load_ocr_config()

    assert config.enabled is False
    assert config.lang == "ch"
    assert config.use_angle_cls is True


def test_recognize_frames_returns_empty_when_disabled(monkeypatch, tmp_path):
    _clear_ocr_env(monkeypatch)
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"jpeg")

    from app.video_understanding.ocr_service import recognize_frames_with_ocr

    result = recognize_frames_with_ocr([_frame(frame_path)])

    assert result.texts == []
    assert result.warnings == []


def test_enabled_ocr_uses_paddleocr_and_normalizes_old_result_format(monkeypatch, tmp_path):
    _clear_ocr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_OCR_ENABLED", "true")
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"jpeg")
    calls = []

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def ocr(self, path, cls=True):
            calls.append(("ocr", path, cls))
            return [
                [
                    [
                        [[0, 0], [100, 0], [100, 30], [0, 30]],
                        ("早上来不及吃饭？", 0.92),
                    ]
                ]
            ]

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))

    from app.video_understanding.ocr_service import recognize_frames_with_ocr

    result = recognize_frames_with_ocr([_frame(frame_path)])

    assert calls == [
        (
            "init",
            {
                "lang": "ch",
                "use_doc_orientation_classify": False,
                "use_doc_unwarping": False,
                "use_textline_orientation": True,
            },
        ),
        ("ocr", str(frame_path), True),
    ]
    assert result.texts == [
        FrameOCRText(
            shot_index=1,
            frame_index=2,
            frame_time=1.25,
            text="早上来不及吃饭？",
            position="[[0, 0], [100, 0], [100, 30], [0, 30]]",
            confidence=0.92,
        )
    ]
    assert result.warnings == []


def test_enabled_ocr_returns_warning_for_missing_frame(monkeypatch, tmp_path):
    _clear_ocr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_OCR_ENABLED", "true")
    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        types.SimpleNamespace(PaddleOCR=lambda **_kwargs: object()),
    )

    from app.video_understanding.ocr_service import recognize_frames_with_ocr

    result = recognize_frames_with_ocr([_frame(tmp_path / "missing.jpg")])

    assert result.texts == []
    assert result.warnings == ["OCR 未完成：frame image not found for shot_index=1 frame_index=2"]


def test_enabled_ocr_does_not_pass_removed_show_log_argument(monkeypatch, tmp_path):
    _clear_ocr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_OCR_ENABLED", "true")
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"jpeg")
    init_kwargs = []

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            init_kwargs.append(kwargs)
            if "show_log" in kwargs:
                raise ValueError("Unknown argument: show_log")

        def ocr(self, path, **kwargs):
            return [{"rec_texts": ["限时优惠"], "rec_scores": [0.93], "rec_polys": [[[0, 0], [1, 0]]]}]

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))

    from app.video_understanding.ocr_service import recognize_frames_with_ocr

    result = recognize_frames_with_ocr([_frame(frame_path)])

    assert all("show_log" not in kwargs for kwargs in init_kwargs)
    assert result.warnings == []
    assert result.texts[0].text == "限时优惠"


def test_enabled_ocr_retries_with_scaled_image_when_original_has_no_text(monkeypatch, tmp_path):
    _clear_ocr_env(monkeypatch)
    monkeypatch.setenv("REELSTRUCT_OCR_ENABLED", "true")
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"jpeg")
    calls = []

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            pass

        def ocr(self, path, **kwargs):
            calls.append(path)
            if path.endswith("_ocr_scale_0.50.jpg"):
                return [{"rec_texts": ["超级大标题"], "rec_scores": [0.95], "rec_polys": [[[0, 0], [100, 0]]]}]
            return [{"rec_texts": [], "rec_scores": [], "rec_polys": []}]

    def fake_prepare_scaled_ocr_image(image_path, *, scale, suffix):
        assert scale == 0.5
        scaled_path = image_path.with_name(f"{image_path.stem}{suffix}{image_path.suffix}")
        scaled_path.write_bytes(b"scaled")
        return scaled_path

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakePaddleOCR))
    monkeypatch.setattr("app.video_understanding.ocr_service._prepare_scaled_ocr_image", fake_prepare_scaled_ocr_image)

    from app.video_understanding.ocr_service import recognize_frames_with_ocr

    result = recognize_frames_with_ocr([_frame(frame_path)])

    assert calls == [str(frame_path), str(tmp_path / "shot_ocr_scale_0.50.jpg")]
    assert result.texts == [
        FrameOCRText(
            shot_index=1,
            frame_index=2,
            frame_time=1.25,
            text="超级大标题",
            position="[[0, 0], [100, 0]]",
            confidence=0.95,
        )
    ]
