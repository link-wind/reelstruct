from __future__ import annotations

from app.domain.shared.domain_models import (
    MaterialGraph,
    MaterialGraphEdge,
    MaterialGraphMatchedNode,
    MaterialGraphNode,
    MaterialGraphSearchResult,
    SlotQueryProfile,
    UserSlotAsset,
)


def build_material_graph(assets: list[UserSlotAsset]) -> MaterialGraph:
    graph = MaterialGraph(material_id=_graph_material_id(assets))
    for asset in assets:
        asset_id = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.slot_id
        asset_node_id = f"asset::{asset_id}"
        graph.nodes.append(
            MaterialGraphNode(
                node_id=asset_node_id,
                node_type="asset",
                label=asset.filename or asset.slot_id,
                source_asset_id=asset_id,
                text=asset.analysis.visual_summary,
            )
        )
        for chunk in asset.analysis.evidence_chunks:
            chunk_id = chunk.chunk_id or "full"
            chunk_node_id = f"chunk::{asset_id}::{chunk_id}"
            graph.nodes.append(
                MaterialGraphNode(
                    node_id=chunk_node_id,
                    node_type="chunk",
                    label=chunk_id,
                    source_asset_id=asset_id,
                    chunk_id=chunk_id,
                    start=chunk.start,
                    end=chunk.end,
                    text=chunk.visual_summary or chunk.embedding_text,
                )
            )
            graph.edges.append(MaterialGraphEdge(source=asset_node_id, target=chunk_node_id, relation="contains"))
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "ocr_text", chunk.ocr_texts)
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "asr_text", chunk.asr_texts)
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "packaging_signal", chunk.packaging_signals)
            _append_text_nodes(graph, chunk_node_id, asset_id, chunk_id, "tag", [*chunk.subject_tags, *chunk.action_tags])
            for index, slot_hint in enumerate(chunk.slot_hints):
                node_id = f"slot_hint::{asset_id}::{chunk_id}::{index}"
                graph.nodes.append(
                    MaterialGraphNode(
                        node_id=node_id,
                        node_type="slot_hint",
                        label=slot_hint,
                        source_asset_id=asset_id,
                        chunk_id=chunk_id,
                        text=slot_hint,
                    )
                )
                graph.edges.append(MaterialGraphEdge(source=chunk_node_id, target=node_id, relation="supports_slot"))
    return graph


def search_material_graph_for_slot(
    graph: MaterialGraph,
    profile: SlotQueryProfile,
    *,
    top_k: int = 5,
) -> list[MaterialGraphSearchResult]:
    chunk_nodes = [node for node in graph.nodes if node.node_type == "chunk"]
    results: list[MaterialGraphSearchResult] = []
    for chunk in chunk_nodes:
        evidence_nodes = _child_nodes(graph, chunk.node_id)
        matched_nodes = _matched_nodes(chunk, evidence_nodes, profile)
        if not matched_nodes:
            continue
        score_breakdown = _graph_score_breakdown(chunk, matched_nodes, profile)
        score = sum(score_breakdown.values())
        if score <= 0:
            continue
        results.append(
            MaterialGraphSearchResult(
                slot_id=profile.slot_id,
                asset_id=chunk.source_asset_id,
                chunk_id=chunk.chunk_id,
                start=chunk.start,
                end=chunk.end,
                matched_nodes=[
                    MaterialGraphMatchedNode(
                        node_id=node.node_id,
                        node_type=node.node_type,
                        label=node.label,
                        text=node.text,
                        source_asset_id=node.source_asset_id,
                        chunk_id=node.chunk_id,
                    )
                    for node in matched_nodes
                ],
                evidence_path=_evidence_path(chunk, matched_nodes, profile),
                missing=_graph_missing(profile, score_breakdown),
                score_breakdown=score_breakdown,
                confidence=round(min(0.95, score / 100), 2),
            )
        )
    return sorted(results, key=lambda item: item.confidence, reverse=True)[:top_k]


def _append_text_nodes(
    graph: MaterialGraph,
    chunk_node_id: str,
    asset_id: str,
    chunk_id: str,
    node_type: str,
    values: list[str],
) -> None:
    for index, value in enumerate(values):
        if not value:
            continue
        node_id = f"{node_type}::{asset_id}::{chunk_id}::{index}"
        graph.nodes.append(
            MaterialGraphNode(
                node_id=node_id,
                node_type=node_type,
                label=value,
                source_asset_id=asset_id,
                chunk_id=chunk_id,
                text=value,
            )
        )
        graph.edges.append(MaterialGraphEdge(source=chunk_node_id, target=node_id, relation="has_evidence"))


def _child_nodes(graph: MaterialGraph, source: str) -> list[MaterialGraphNode]:
    targets = {edge.target for edge in graph.edges if edge.source == source}
    return [node for node in graph.nodes if node.node_id in targets]


def _matched_nodes(
    chunk: MaterialGraphNode,
    evidence_nodes: list[MaterialGraphNode],
    profile: SlotQueryProfile,
) -> list[MaterialGraphNode]:
    terms = _lower_terms(
        [
            *profile.visual_terms,
            *profile.action_terms,
            *profile.text_terms,
            *profile.packaging_terms,
            profile.slot_label,
        ]
    )
    matched = [chunk] if _contains_any(chunk.text, terms) else []
    for node in evidence_nodes:
        if _contains_any(" ".join([node.label, node.text]), terms):
            matched.append(node)
    return _dedupe_nodes(matched)


def _graph_score_breakdown(
    chunk: MaterialGraphNode,
    matched_nodes: list[MaterialGraphNode],
    profile: SlotQueryProfile,
) -> dict[str, int]:
    node_types = {node.node_type for node in matched_nodes}
    return {
        "semantic": 20 if _contains_any(chunk.text, _lower_terms(profile.semantic_terms)) else 0,
        "visual": 20 if "tag" in node_types or _contains_any(chunk.text, _lower_terms(profile.visual_terms)) else 0,
        "ocr_asr": 25 if {"ocr_text", "asr_text"} & node_types else 0,
        "packaging": 15 if "packaging_signal" in node_types else 0,
        "slot_hint": 25 if "slot_hint" in node_types else 0,
        "duration_fit": _duration_fit_score(profile.target_duration, chunk.end - chunk.start),
    }


def _duration_fit_score(target_duration: float, chunk_duration: float) -> int:
    if target_duration <= 0 or chunk_duration <= 0:
        return 0
    ratio = min(target_duration, chunk_duration) / max(target_duration, chunk_duration)
    return round(ratio * 15)


def _evidence_path(
    chunk: MaterialGraphNode,
    matched_nodes: list[MaterialGraphNode],
    profile: SlotQueryProfile,
) -> list[str]:
    path = [f"槽位 {profile.slot_label or profile.slot_id} 需要 {profile.required_asset}"]
    for node in matched_nodes:
        if node.node_type == "chunk":
            path.append(f"{chunk.chunk_id} 命中 视觉摘要={node.text}")
        elif node.node_type == "ocr_text":
            path.append(f"{chunk.chunk_id} 命中 OCR={node.text}")
        elif node.node_type == "asr_text":
            path.append(f"{chunk.chunk_id} 命中 ASR={node.text}")
        elif node.node_type == "packaging_signal":
            path.append(f"{chunk.chunk_id} 命中 包装={node.text}")
        elif node.node_type == "tag":
            path.append(f"{chunk.chunk_id} 命中 标签={node.text}")
        elif node.node_type == "slot_hint":
            path.append(f"{chunk.chunk_id} 命中 槽位提示={node.text}")
    return _dedupe(path)


def _graph_missing(profile: SlotQueryProfile, score_breakdown: dict[str, int]) -> list[str]:
    missing: list[str] = []
    if profile.visual_terms and score_breakdown.get("visual", 0) == 0:
        missing.append("缺少明确画面主体或动作证据")
    if profile.text_terms and score_breakdown.get("ocr_asr", 0) == 0:
        missing.append("缺少 OCR/ASR 文本证据")
    if profile.packaging_terms and score_breakdown.get("packaging", 0) == 0:
        missing.append("缺少包装信号")
    return missing


def _lower_terms(values: list[str]) -> list[str]:
    return [value.lower() for value in values if value]


def _contains_any(value: str, terms: list[str]) -> bool:
    normalized = value.lower()
    return any(term and term in normalized for term in terms)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _dedupe_nodes(nodes: list[MaterialGraphNode]) -> list[MaterialGraphNode]:
    seen: set[str] = set()
    unique: list[MaterialGraphNode] = []
    for node in nodes:
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        unique.append(node)
    return unique


def _graph_material_id(assets: list[UserSlotAsset]) -> str:
    if len(assets) == 1:
        return assets[0].slot_id
    return "material_graph"
