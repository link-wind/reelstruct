from __future__ import annotations

import hashlib
import math
import re


class MaterialEmbeddingService:
    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for term in _tokenize(text):
            digest = hashlib.sha1(term.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _tokenize(value: str) -> set[str]:
    normalized = value.lower().replace("_", " ").replace("-", " ")
    terms = set(item for item in re.split(r"[\s,，。/]+", normalized) if item)
    for phrase in ["产品特写", "卖点展开", "行动号召", "使用过程", "快速补水"]:
        if phrase in normalized:
            terms.add(phrase)
    return terms
