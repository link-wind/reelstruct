from dataclasses import dataclass
import json
import shutil
from pathlib import Path
from typing import Optional

from app.models import CompositionSpec
from app.models import MaterialFitAnalysis


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_ROOT = PROJECT_ROOT
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "downloads"


@dataclass(frozen=True)
class FixtureAssetCandidate:
    id: str
    title: str
    duration: float
    local_path: str
    public_url: str
    matched_keywords: list[str]


@dataclass(frozen=True)
class RenderClip:
    scene_id: str
    local_path: str
    public_url: str
    caption: str
    start_time: float
    duration: float
    source_type: str
    source_label: str
    material_analysis: MaterialFitAnalysis


def search_fixture_assets(
    keywords: list[str],
    *,
    fixture_root: Optional[Path] = None,
    max_results: int = 5,
) -> list[FixtureAssetCandidate]:
    root = fixture_root or DEFAULT_FIXTURE_ROOT
    normalized_keywords = _normalize_keywords(keywords)
    if not normalized_keywords:
        return []

    scored_entries: list[tuple[int, dict, list[str]]] = []
    for entry in _load_fixture_library(root):
        matched = _matched_keywords(entry, normalized_keywords)
        if matched:
            scored_entries.append((len(matched), entry, matched))

    scored_entries.sort(key=lambda item: item[0], reverse=True)
    candidates = []
    for _score, entry, matched in scored_entries[: max(0, max_results)]:
        public_url = str(entry.get("videoUrl") or "")
        local_path = _resolve_fixture_path(root, public_url)
        if not local_path.is_file():
            continue
        candidates.append(
            FixtureAssetCandidate(
                id=str(entry.get("id") or ""),
                title=str(entry.get("title") or ""),
                duration=float(entry.get("duration") or 0),
                local_path=str(local_path),
                public_url=public_url,
                matched_keywords=matched,
            )
        )
    return candidates


def copy_fixture_asset(
    candidate: FixtureAssetCandidate,
    *,
    output_dir: Optional[Path] = None,
    output_name: str,
) -> RenderClip:
    target_dir = output_dir or DEFAULT_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / output_name
    shutil.copyfile(candidate.local_path, target_path)
    return RenderClip(
        scene_id="",
        local_path=str(target_path),
        public_url=f"/downloads/{output_name}",
        caption="",
        start_time=0,
        duration=candidate.duration,
        source_type="fixture",
        source_label=f"fixture 匹配：{candidate.title}",
        material_analysis=MaterialFitAnalysis(),
    )


def build_render_clips_from_composition(
    composition: CompositionSpec,
    *,
    fixture_root: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> list[RenderClip]:
    caption_lookup = _caption_lookup_with_packaging(composition)
    clips: list[RenderClip] = []
    for index, track in enumerate([item for item in composition.tracks if item.type == "video"], start=1):
        uploaded_path = Path(track.asset_local_path) if track.asset_local_path else None
        if uploaded_path and uploaded_path.is_file():
            clips.append(
                RenderClip(
                    scene_id=track.slot_id,
                    local_path=str(uploaded_path),
                    public_url=track.asset_public_url,
                    caption=caption_lookup.get(track.slot_id, ""),
                    start_time=track.start,
                    duration=track.duration,
                    source_type="uploaded",
                    source_label="用户上传素材",
                    material_analysis=track.material_analysis,
                )
            )
            continue

        keywords = _normalize_keywords([track.source, track.slot_id])
        candidates = search_fixture_assets(keywords, fixture_root=fixture_root, max_results=1)
        candidate = candidates[0] if candidates else find_fallback_fixture_asset(fixture_root=fixture_root)
        if candidate is None:
            continue
        copied = copy_fixture_asset(
            candidate,
            output_dir=output_dir,
            output_name=f"{track.slot_id or index}.mp4",
        )
        source_type = copied.source_type if candidates else "fixture_fallback"
        source_label = copied.source_label if candidates else f"fixture 兜底：{candidate.title}"
        clips.append(
            RenderClip(
                scene_id=track.slot_id,
                local_path=copied.local_path,
                public_url=copied.public_url,
                caption=caption_lookup.get(track.slot_id, ""),
                start_time=track.start,
                duration=track.duration,
                source_type=source_type,
                source_label=source_label,
                material_analysis=copied.material_analysis,
            )
        )
    return clips


def find_fallback_fixture_asset(*, fixture_root: Optional[Path] = None) -> Optional[FixtureAssetCandidate]:
    root = fixture_root or DEFAULT_FIXTURE_ROOT
    for entry in _load_fixture_library(root):
        public_url = str(entry.get("videoUrl") or "")
        local_path = _resolve_fixture_path(root, public_url)
        if not local_path.is_file():
            continue
        return FixtureAssetCandidate(
            id=str(entry.get("id") or ""),
            title=str(entry.get("title") or ""),
            duration=float(entry.get("duration") or 0),
            local_path=str(local_path),
            public_url=public_url,
            matched_keywords=[],
        )
    return None


def _caption_lookup_with_packaging(composition: CompositionSpec) -> dict[str, str]:
    lookup: dict[str, list[str]] = {}
    for track_type in ("card", "caption"):
        for track in composition.tracks:
            if track.type == track_type and track.text.strip():
                lookup.setdefault(track.slot_id, []).append(track.text.strip())
    return {
        slot_id: "\n".join(_dedupe_texts(texts))
        for slot_id, texts in lookup.items()
    }


def _load_fixture_library(root: Path) -> list[dict]:
    library_path = root / "fixtures" / "videos.json"
    with library_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_fixture_path(root: Path, public_url: str) -> Path:
    return root / public_url.lstrip("/")


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    for keyword in keywords:
        for part in str(keyword).replace("/", " ").split():
            stripped = part.strip()
            if stripped:
                normalized.append(stripped)
    return normalized


def _dedupe_texts(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _matched_keywords(entry: dict, keywords: list[str]) -> list[str]:
    searchable_parts = [
        str(entry.get("title") or ""),
        str(entry.get("description") or ""),
        *[str(tag) for tag in entry.get("tags") or []],
    ]
    searchable = " ".join(searchable_parts)
    searchable_tokens = _normalize_keywords(searchable_parts)
    matched = []
    for keyword in keywords:
        if not keyword:
            continue
        if keyword in searchable or any(token and token in keyword for token in searchable_tokens):
            matched.append(keyword)
    return matched
