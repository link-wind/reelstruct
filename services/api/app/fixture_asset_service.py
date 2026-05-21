from dataclasses import dataclass
import json
import shutil
from pathlib import Path
from typing import Optional

from app.models import CompositionSpec


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
    )


def build_render_clips_from_composition(
    composition: CompositionSpec,
    *,
    fixture_root: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> list[RenderClip]:
    caption_lookup = {
        track.slot_id: track.text
        for track in composition.tracks
        if track.type == "caption" and track.text.strip()
    }
    clips: list[RenderClip] = []
    for index, track in enumerate([item for item in composition.tracks if item.type == "video"], start=1):
        keywords = _normalize_keywords([track.source, track.slot_id])
        candidates = search_fixture_assets(keywords, fixture_root=fixture_root, max_results=1)
        if not candidates:
            continue
        copied = copy_fixture_asset(
            candidates[0],
            output_dir=output_dir,
            output_name=f"{track.slot_id or index}.mp4",
        )
        clips.append(
            RenderClip(
                scene_id=track.slot_id,
                local_path=copied.local_path,
                public_url=copied.public_url,
                caption=caption_lookup.get(track.slot_id, ""),
                start_time=track.start,
                duration=track.duration,
            )
        )
    return clips


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
