from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import re
from typing import Any, Protocol


@dataclass
class MaterialVectorDocument:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)


@dataclass
class MaterialVectorSearchResult:
    id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MaterialVectorStore(Protocol):
    def upsert(self, documents: list[MaterialVectorDocument]) -> None:
        ...

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[MaterialVectorSearchResult]:
        ...


class InMemoryMaterialVectorStore:
    def __init__(self) -> None:
        self._documents: dict[str, MaterialVectorDocument] = {}

    def upsert(self, documents: list[MaterialVectorDocument]) -> None:
        for document in documents:
            self._documents[document.id] = document

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[MaterialVectorSearchResult]:
        query_terms = _tokenize(query)
        results: list[MaterialVectorSearchResult] = []
        for document in self._documents.values():
            if filters and not _metadata_matches(document.metadata, filters):
                continue
            if query_embedding is not None and document.embedding:
                score = _cosine_similarity(query_embedding, document.embedding)
            else:
                score = _lexical_similarity(query_terms, _tokenize(document.text))
            if score <= 0:
                continue
            results.append(
                MaterialVectorSearchResult(
                    id=document.id,
                    score=score,
                    text=document.text,
                    metadata=document.metadata,
                )
            )
        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]


class MilvusLiteMaterialVectorStore:
    def __init__(self, uri: str, collection_name: str = "material_chunks", dimension: int = 128) -> None:
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:  # pragma: no cover - depends on optional runtime package
            raise RuntimeError("Milvus Lite 需要安装 pymilvus：pip install pymilvus") from exc
        self._client = MilvusClient(uri)
        self._collection_name = collection_name
        self._dimension = dimension
        if not self._client.has_collection(collection_name):
            self._client.create_collection(collection_name=collection_name, dimension=dimension)

    def upsert(self, documents: list[MaterialVectorDocument]) -> None:
        if not documents:
            return
        rows = [
            {
                "id": _stable_int_id(document.id),
                "vector": _normalized_embedding(document.embedding, self._dimension)
                if document.embedding
                else _hash_embedding(document.text, self._dimension),
                "text": document.text,
                **document.metadata,
                "document_id": document.id,
            }
            for document in documents
        ]
        self._client.upsert(collection_name=self._collection_name, data=rows)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[MaterialVectorSearchResult]:
        filter_expr = _milvus_filter_expr(filters or {})
        raw_results = self._client.search(
            collection_name=self._collection_name,
            data=[
                _normalized_embedding(query_embedding, self._dimension)
                if query_embedding is not None
                else _hash_embedding(query, self._dimension)
            ],
            limit=top_k,
            filter=filter_expr or "",
            output_fields=[
                "document_id",
                "text",
                "asset_id",
                "filename",
                "chunk_id",
                "source_slot_id",
                "public_url",
                "start",
                "end",
                "modalities",
                "evidence",
                "slot",
            ],
        )
        results: list[MaterialVectorSearchResult] = []
        for hit in raw_results[0] if raw_results else []:
            entity = hit.get("entity", {})
            metadata = {key: value for key, value in entity.items() if key not in {"document_id", "text"}}
            results.append(
                MaterialVectorSearchResult(
                    id=entity.get("document_id", str(hit.get("id", ""))),
                    score=float(hit.get("distance", 0)),
                    text=entity.get("text", ""),
                    metadata=metadata,
                )
            )
        return results


def _tokenize(value: str) -> set[str]:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    terms = set(item for item in re.split(r"[\s,，。/]+", normalized) if item)
    for phrase in ["产品特写", "卖点展开", "行动号召", "使用过程", "快速补水"]:
        if phrase in normalized:
            terms.add(phrase)
    return terms


def _lexical_similarity(query_terms: set[str], document_terms: set[str]) -> float:
    if not query_terms or not document_terms:
        return 0
    overlap = query_terms.intersection(document_terms)
    return len(overlap) / math.sqrt(len(query_terms) * len(document_terms))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return dot / (left_norm * right_norm)


def _normalized_embedding(embedding: list[float], dimension: int) -> list[float]:
    vector = [0.0] * dimension
    for index, value in enumerate(embedding[:dimension]):
        vector[index] = value
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(metadata.get(key) == value for key, value in filters.items())


def _stable_int_id(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def _hash_embedding(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    terms = _tokenize(text)
    for term in terms:
        digest = hashlib.sha1(term.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dimension
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _milvus_filter_expr(filters: dict[str, Any]) -> str:
    expressions = []
    for key, value in filters.items():
        if isinstance(value, str):
            expressions.append(f'{key} == "{value}"')
        elif isinstance(value, (int, float)):
            expressions.append(f"{key} == {value}")
    return " and ".join(expressions)
