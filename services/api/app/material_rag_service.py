from __future__ import annotations

import os
from typing import Optional

from app.material_embedding_service import MaterialEmbeddingService
from app.material_vector_store import (
    InMemoryMaterialVectorStore,
    MaterialVectorDocument,
    MaterialVectorSearchResult,
    MaterialVectorStore,
    MilvusLiteMaterialVectorStore,
)
from app.domain.shared.domain_models import (
    MaterialEvidenceChunk,
    MaterialRetrievalCandidate,
    NewContentInput,
    StructureSlot,
    UserSlotAsset,
)


_MATERIAL_VECTOR_STORE: MaterialVectorStore | None = None
_MATERIAL_ASSET_LOOKUP: dict[str, tuple[UserSlotAsset, MaterialEvidenceChunk]] = {}
_EMBEDDING_SERVICE = MaterialEmbeddingService()


def retrieve_material_candidates_for_slot(
    slot: StructureSlot,
    content: NewContentInput,
) -> list[MaterialRetrievalCandidate]:
    candidates: list[MaterialRetrievalCandidate] = []
    candidates.extend(_vector_candidates_for_slot(slot, content))
    for asset in content.uploaded_assets:
        if not (asset.local_path or asset.public_url):
            continue
        chunk_candidates = _chunk_candidates_for_slot(slot, content, asset)
        if chunk_candidates:
            candidates.extend(chunk_candidates)
            continue
        score = int(asset.analysis.slot_fit_scores.get(slot.id, 0))
        semantic_score = _semantic_material_score(slot, content, asset)
        score = max(score, semantic_score)
        if asset.slot_id == slot.id:
            score = max(score, 95)
        if asset.analysis.recommended_slot_id == slot.id:
            score = max(score, 88)
        if score < 45:
            continue
        filename = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.local_path.rsplit("/", 1)[-1]
        candidates.append(
            MaterialRetrievalCandidate(
                asset_id=filename or asset.slot_id,
                filename=filename,
                source_slot_id=asset.slot_id,
                public_url=asset.public_url,
                match_score=min(score, 100),
                score_breakdown={
                    "slot_hint": int(asset.analysis.slot_fit_scores.get(slot.id, 0)),
                    "semantic": semantic_score,
                    "duration_fit": 95 if asset.slot_id == slot.id else 0,
                },
                match_reason=_material_match_reason(slot, asset, score, semantic_score),
                reuse_strategy=_material_reuse_strategy(slot, score),
            )
        )
    return _merge_material_candidates(candidates)[:3]


def create_material_vector_store() -> MaterialVectorStore:
    backend = os.getenv("REELSTRUCT_MATERIAL_VECTOR_BACKEND", "memory").strip().lower()
    if backend == "milvus":
        uri = os.getenv("REELSTRUCT_MILVUS_URI", "./services/api/storage/material-vector.db")
        try:
            return MilvusLiteMaterialVectorStore(uri=uri)
        except RuntimeError:
            return InMemoryMaterialVectorStore()
    return InMemoryMaterialVectorStore()


def get_material_vector_store() -> MaterialVectorStore:
    global _MATERIAL_VECTOR_STORE
    if _MATERIAL_VECTOR_STORE is None:
        _MATERIAL_VECTOR_STORE = create_material_vector_store()
    return _MATERIAL_VECTOR_STORE


def reset_material_vector_store_for_tests() -> None:
    global _MATERIAL_VECTOR_STORE
    _MATERIAL_VECTOR_STORE = None
    _MATERIAL_ASSET_LOOKUP.clear()


def index_material_asset(asset: UserSlotAsset) -> None:
    documents = _material_vector_documents(NewContentInput(topic="", uploaded_assets=[asset]))
    if not documents:
        return
    get_material_vector_store().upsert(documents)
    _MATERIAL_ASSET_LOOKUP.update(_material_chunk_lookup(NewContentInput(topic="", uploaded_assets=[asset])))


def _vector_candidates_for_slot(slot: StructureSlot, content: NewContentInput) -> list[MaterialRetrievalCandidate]:
    documents = _material_vector_documents(content)
    query = _material_vector_query(slot, content)
    query_embedding = _EMBEDDING_SERVICE.embed(query)
    results = get_material_vector_store().search(query, top_k=5, query_embedding=query_embedding)
    chunk_lookup = {**_MATERIAL_ASSET_LOOKUP, **_material_chunk_lookup(content)}
    if documents:
        transient_store = InMemoryMaterialVectorStore()
        transient_store.upsert(documents)
        results.extend(transient_store.search(query, top_k=5, query_embedding=query_embedding))
    candidates: list[MaterialRetrievalCandidate] = []
    for result in results:
        candidate = _vector_result_to_candidate(slot, content, result, chunk_lookup)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _material_vector_documents(content: NewContentInput) -> list[MaterialVectorDocument]:
    documents: list[MaterialVectorDocument] = []
    for asset in content.uploaded_assets:
        if not (asset.local_path or asset.public_url):
            continue
        filename = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.local_path.rsplit("/", 1)[-1]
        for chunk in asset.analysis.evidence_chunks:
            text = chunk.embedding_text or chunk.visual_summary or asset.analysis.embedding_text
            if not text:
                continue
            document_id = _material_chunk_document_id(filename or chunk.asset_id or asset.slot_id, chunk.chunk_id)
            documents.append(
                MaterialVectorDocument(
                    id=document_id,
                    text=text,
                    metadata={
                        "asset_id": filename or chunk.asset_id or asset.slot_id,
                        "filename": filename,
                        "chunk_id": chunk.chunk_id,
                        "source_slot_id": asset.slot_id,
                        "public_url": asset.public_url,
                        "start": chunk.start,
                        "end": chunk.end,
                        "modalities": ",".join(_dedupe([*chunk.modalities, "vector"])),
                        "evidence": "；".join(_chunk_evidence(chunk)),
                    },
                    embedding=_EMBEDDING_SERVICE.embed(text),
                )
            )
    return documents


def _material_vector_query(slot: StructureSlot, content: NewContentInput) -> str:
    return " ".join(
        _dedupe(
            [
                slot.id,
                slot.label,
                slot.required_asset,
                slot.purpose,
                slot.method,
                slot.role,
                content.topic,
                content.product_name,
                *content.selling_points,
                *_slot_core_terms(slot.id),
            ]
        )
    )


def _material_chunk_lookup(content: NewContentInput) -> dict[str, tuple[UserSlotAsset, MaterialEvidenceChunk]]:
    lookup: dict[str, tuple[UserSlotAsset, MaterialEvidenceChunk]] = {}
    for asset in content.uploaded_assets:
        filename = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.local_path.rsplit("/", 1)[-1]
        for chunk in asset.analysis.evidence_chunks:
            lookup[_material_chunk_document_id(filename or chunk.asset_id or asset.slot_id, chunk.chunk_id)] = (asset, chunk)
            lookup[_material_chunk_document_id(chunk.asset_id or filename or asset.slot_id, chunk.chunk_id)] = (asset, chunk)
    return lookup


def _vector_result_to_candidate(
    slot: StructureSlot,
    content: NewContentInput,
    result: MaterialVectorSearchResult,
    chunk_lookup: dict[str, tuple[UserSlotAsset, MaterialEvidenceChunk]],
) -> Optional[MaterialRetrievalCandidate]:
    asset_chunk = chunk_lookup.get(result.id)
    if asset_chunk is None:
        metadata_id = _material_chunk_document_id(
            str(result.metadata.get("asset_id", "")),
            str(result.metadata.get("chunk_id", "")),
        )
        asset_chunk = chunk_lookup.get(metadata_id)
    if asset_chunk is None:
        return _vector_metadata_to_candidate(slot, result)
    asset, chunk = asset_chunk
    filename = asset.filename or result.metadata.get("filename", "") or result.metadata.get("asset_id", "")
    vector_score = _vector_match_score(result.score)
    score_breakdown = _hybrid_score_breakdown(slot, content, chunk, vector_score)
    score = min(100, round(sum(score_breakdown.values()) / 1.35))
    return MaterialRetrievalCandidate(
        asset_id=filename or chunk.asset_id or asset.slot_id,
        filename=filename,
        source_slot_id=asset.slot_id,
        public_url=asset.public_url,
        chunk_id=chunk.chunk_id,
        start=chunk.start,
        end=chunk.end,
        matched_modalities=_dedupe([*chunk.modalities, "vector"]),
        evidence=_dedupe([*_chunk_evidence(chunk), f"向量检索：{result.text}"])[:6],
        match_score=score,
        score_breakdown=score_breakdown,
        match_reason=_vector_match_reason(slot, chunk, score),
        reuse_strategy=_chunk_reuse_strategy(slot, chunk, score),
    )


def _vector_metadata_to_candidate(
    slot: StructureSlot,
    result: MaterialVectorSearchResult,
) -> MaterialRetrievalCandidate | None:
    asset_id = str(result.metadata.get("asset_id") or result.metadata.get("filename") or "")
    chunk_id = str(result.metadata.get("chunk_id") or "")
    if not asset_id or not chunk_id:
        return None
    filename = str(result.metadata.get("filename") or asset_id)
    score = _vector_match_score(result.score)
    evidence = _split_metadata_list(str(result.metadata.get("evidence") or ""))
    if result.text:
        evidence.append(f"向量检索：{result.text}")
    return MaterialRetrievalCandidate(
        asset_id=asset_id,
        filename=filename,
        source_slot_id=str(result.metadata.get("source_slot_id") or ""),
        public_url=str(result.metadata.get("public_url") or ""),
        chunk_id=chunk_id,
        start=_metadata_float(result.metadata.get("start")),
        end=_metadata_float(result.metadata.get("end")),
        matched_modalities=_dedupe([*_split_metadata_list(str(result.metadata.get("modalities") or "")), "vector"]),
        evidence=_dedupe(evidence)[:6],
        match_score=score,
        score_breakdown={"vector": score},
        match_reason=f"{slot.label} 需要“{slot.required_asset}”，向量索引命中已入库素材片段，评分 {score}。",
        reuse_strategy=f"复用 {filename} 的 {chunk_id} 片段，按“{slot.label}”段落重新裁切并补字幕。",
    )


def _material_chunk_document_id(asset_id: str, chunk_id: str) -> str:
    return f"{asset_id}::{chunk_id}"


def _vector_match_score(raw_score: float) -> int:
    normalized = max(0, min(raw_score, 1))
    return min(92, 55 + round(normalized * 40))


def _vector_match_reason(slot: StructureSlot, chunk: MaterialEvidenceChunk, score: int) -> str:
    time_range = f"{chunk.start}s-{chunk.end}s" if chunk.end > chunk.start else "完整片段"
    evidence = "；".join(_chunk_evidence(chunk)[:2])
    return f"{slot.label} 需要“{slot.required_asset}”，向量检索命中 {time_range} 素材片段，评分 {score}。{evidence}"


def _merge_material_candidates(candidates: list[MaterialRetrievalCandidate]) -> list[MaterialRetrievalCandidate]:
    merged: dict[tuple[str, str], MaterialRetrievalCandidate] = {}
    for candidate in candidates:
        key = (candidate.asset_id, candidate.chunk_id or "")
        existing = merged.get(key)
        if existing is None or candidate.match_score > existing.match_score:
            merged[key] = _candidate_with_merged_context(candidate, existing)
            continue
        merged[key] = _candidate_with_merged_context(existing, candidate)
    return sorted(merged.values(), key=lambda item: item.match_score, reverse=True)


def _candidate_with_merged_context(
    primary: MaterialRetrievalCandidate,
    secondary: MaterialRetrievalCandidate | None,
) -> MaterialRetrievalCandidate:
    if secondary is None:
        return primary
    score_breakdown = dict(secondary.score_breakdown)
    for key, value in primary.score_breakdown.items():
        score_breakdown[key] = max(score_breakdown.get(key, 0), value)
    return primary.model_copy(
        update={
            "matched_modalities": _dedupe([*secondary.matched_modalities, *primary.matched_modalities]),
            "evidence": _dedupe([*secondary.evidence, *primary.evidence])[:6],
            "score_breakdown": score_breakdown,
        }
    )


def _chunk_candidates_for_slot(
    slot: StructureSlot,
    content: NewContentInput,
    asset: UserSlotAsset,
) -> list[MaterialRetrievalCandidate]:
    candidates: list[MaterialRetrievalCandidate] = []
    filename = asset.filename or asset.public_url.rsplit("/", 1)[-1] or asset.local_path.rsplit("/", 1)[-1]
    for chunk in asset.analysis.evidence_chunks:
        semantic_score = _semantic_chunk_score(slot, content, chunk)
        slot_hint_score = _chunk_slot_hint_score(slot, chunk)
        score = max(semantic_score, slot_hint_score)
        if score < 45:
            continue
        score_breakdown = _hybrid_score_breakdown(slot, content, chunk, semantic_score)
        score = min(100, max(score, round(sum(score_breakdown.values()) / 1.35)))
        candidates.append(
            MaterialRetrievalCandidate(
                asset_id=filename or chunk.asset_id or asset.slot_id,
                filename=filename,
                source_slot_id=asset.slot_id,
                public_url=asset.public_url,
                chunk_id=chunk.chunk_id,
                start=chunk.start,
                end=chunk.end,
                matched_modalities=chunk.modalities,
                evidence=_chunk_evidence(chunk),
                match_score=min(score, 100),
                score_breakdown=score_breakdown,
                match_reason=_chunk_match_reason(slot, chunk, score),
                reuse_strategy=_chunk_reuse_strategy(slot, chunk, score),
            )
        )
    return candidates


def _semantic_material_score(slot: StructureSlot, content: NewContentInput, asset: UserSlotAsset) -> int:
    haystack = _normalize_material_text(
        " ".join(
            [
                asset.filename,
                asset.public_url,
                asset.analysis.recommendation_reason,
                asset.analysis.recommended_slot_label,
                asset.analysis.visual_summary,
                " ".join(asset.analysis.tags),
                " ".join(asset.analysis.usable_for),
                asset.analysis.embedding_text,
            ]
        )
    )
    query_terms = _slot_semantic_terms(slot, content)
    hits = [term for term in query_terms if term and term in haystack]
    if not hits:
        return 0
    score = 42 + min(len(hits), 5) * 8
    if any(term in haystack for term in _slot_core_terms(slot.id)):
        score += 12
    return min(score, 74)


def _semantic_chunk_score(slot: StructureSlot, content: NewContentInput, chunk: MaterialEvidenceChunk) -> int:
    haystack = _normalize_material_text(
        " ".join(
            [
                chunk.visual_summary,
                *chunk.ocr_texts,
                *chunk.asr_texts,
                *chunk.packaging_signals,
                *chunk.subject_tags,
                *chunk.action_tags,
                *chunk.slot_hints,
                chunk.embedding_text,
            ]
        )
    )
    query_terms = _slot_semantic_terms(slot, content)
    hits = [term for term in query_terms if term and term in haystack]
    if not hits:
        return 0
    score = 46 + min(len(hits), 6) * 7
    if any(term in haystack for term in _slot_core_terms(slot.id)):
        score += 12
    if chunk.ocr_texts or chunk.asr_texts:
        score += 4
    if chunk.packaging_signals:
        score += 8
    return min(score, 82)


def _hybrid_score_breakdown(
    slot: StructureSlot,
    content: NewContentInput,
    chunk: MaterialEvidenceChunk,
    vector_score: int,
) -> dict[str, int]:
    text_terms = _dedupe([content.product_name, *content.selling_points, slot.required_asset, slot.label])
    chunk_text = " ".join([chunk.visual_summary, *chunk.ocr_texts, *chunk.asr_texts, chunk.embedding_text])
    ocr_asr_score = 25 if any(term and term in chunk_text for term in text_terms) else 0
    visual_terms = set([*chunk.subject_tags, *chunk.action_tags])
    visual_score = 20 if visual_terms else 0
    packaging_score = 15 if chunk.packaging_signals else 0
    slot_hint_score = 25 if slot.label in chunk.slot_hints or slot.id in chunk.slot_hints else 0
    duration_score = _duration_fit_score(slot.duration, chunk.duration or max(chunk.end - chunk.start, 0))
    return {
        "vector": vector_score,
        "semantic": vector_score,
        "visual": visual_score,
        "ocr_asr": ocr_asr_score,
        "packaging": packaging_score,
        "slot_hint": slot_hint_score,
        "duration_fit": duration_score,
    }


def _duration_fit_score(slot_duration: float, chunk_duration: float) -> int:
    if slot_duration <= 0 or chunk_duration <= 0:
        return 0
    ratio = min(slot_duration, chunk_duration) / max(slot_duration, chunk_duration)
    return round(ratio * 15)


def _chunk_slot_hint_score(slot: StructureSlot, chunk: MaterialEvidenceChunk) -> int:
    slot_labels = {slot.id, slot.label}
    if slot.id == "selling_points":
        slot_labels.update({"卖点展开", "卖点"})
    if slot.id == "hook":
        slot_labels.update({"Hook", "开头钩子", "开头吸引"})
    if slot.id == "usage":
        slot_labels.update({"使用过程", "过程"})
    if slot.id == "cta":
        slot_labels.update({"CTA", "行动号召", "行动引导"})
    normalized_hints = {_normalize_material_text(hint) for hint in chunk.slot_hints}
    if any(_normalize_material_text(label) in normalized_hints for label in slot_labels):
        return 84
    return 0


def _chunk_evidence(chunk: MaterialEvidenceChunk) -> list[str]:
    evidence = [
        chunk.visual_summary,
        *[f"OCR：{text}" for text in chunk.ocr_texts],
        *[f"ASR：{text}" for text in chunk.asr_texts],
        *[f"包装：{signal}" for signal in chunk.packaging_signals],
        *[f"主体：{tag}" for tag in chunk.subject_tags],
        *[f"动作：{tag}" for tag in chunk.action_tags],
    ]
    return _dedupe([item for item in evidence if item])[:6]


def _chunk_match_reason(slot: StructureSlot, chunk: MaterialEvidenceChunk, score: int) -> str:
    evidence = "；".join(_chunk_evidence(chunk)[:3])
    time_range = f"{chunk.start}s-{chunk.end}s" if chunk.end > chunk.start else "完整片段"
    return f"{slot.label} 需要“{slot.required_asset}”，命中 {time_range} 素材片段，评分 {score}。{evidence}"


def _chunk_reuse_strategy(slot: StructureSlot, chunk: MaterialEvidenceChunk, score: int) -> str:
    time_range = f"{chunk.start}s-{chunk.end}s" if chunk.end > chunk.start else "完整片段"
    if score >= 80:
        return f"裁切 {time_range} 直接放入“{slot.label}”，按目标段落时长微调。"
    return f"裁切 {time_range} 作为“{slot.label}”补位画面，叠加字幕或标题卡强化表达。"


def _slot_semantic_terms(slot: StructureSlot, content: NewContentInput) -> list[str]:
    terms = [
        slot.id,
        slot.label,
        slot.required_asset,
        slot.purpose,
        slot.method,
        slot.role,
        content.product_name,
        content.topic,
        *content.selling_points,
        *_slot_core_terms(slot.id),
    ]
    normalized_terms: list[str] = []
    for term in terms:
        normalized_terms.extend(_split_material_terms(term))
    return _dedupe(normalized_terms)


def _slot_core_terms(slot_id: str) -> list[str]:
    return {
        "hook": ["hook", "开头", "吸引", "痛点", "结果", "反差", "停留"],
        "selling_points": ["selling", "product", "detail", "closeup", "商品", "产品", "特写", "细节", "卖点", "质地", "瓶身"],
        "usage": ["usage", "use", "process", "使用", "过程", "场景", "动作", "演示", "手部"],
        "cta": ["cta", "ending", "end", "card", "结尾", "行动", "号召", "到店", "优惠", "入口", "门店", "购买"],
    }.get(slot_id, ["素材", "补位", "镜头"])


def _normalize_material_text(value: str) -> str:
    return value.lower().replace("_", " ").replace("-", " ")


def _split_material_terms(value: str) -> list[str]:
    normalized = _normalize_material_text(value.strip())
    if not normalized:
        return []
    terms = [normalized]
    terms.extend(item for item in normalized.replace("/", " ").split() if item)
    return terms


def _material_match_reason(slot: StructureSlot, asset: UserSlotAsset, score: int, semantic_score: int = 0) -> str:
    reason = asset.analysis.recommendation_reason or "素材分析命中了当前结构槽位的需求。"
    semantic_note = "文本语义命中素材名称/理解卡/分析说明。" if semantic_score else ""
    return f"{slot.label} 需要“{slot.required_asset}”，候选素材评分 {score}。{reason}{semantic_note}"


def _material_reuse_strategy(slot: StructureSlot, score: int) -> str:
    if score >= 80:
        return f"直接放入“{slot.label}”段落，并按该段时长裁切或压缩。"
    return f"作为“{slot.label}”的背景或局部画面，叠加字幕、标题卡和卖点标签补足表达。"


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _split_metadata_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", "；").split("；") if item.strip()]


def _metadata_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0
