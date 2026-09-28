from dataclasses import dataclass
import math

from backend.app.core.config import settings
from backend.app.models import KnowledgeChunk
from backend.app.rag.embeddings import EmbeddingService
from backend.app.rag.vector_store import SQLiteVectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    id: int
    content: str
    score: float
    source: str
    title: str
    category: str
    chunk_index: int


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return dot / denominator if denominator else 0.0


class SemanticRetriever:
    def __init__(self, store: SQLiteVectorStore, embeddings: EmbeddingService | None = None) -> None:
        self.store = store
        self.embeddings = embeddings or EmbeddingService()

    async def retrieve(self, query: str, top_k: int = 5, category: str | None = None) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError("Retrieval query must not be empty.")
        if top_k < 1 or top_k > 50:
            raise ValueError("top_k must be between 1 and 50.")
        chunks = [
            chunk for chunk in self.store.all_chunks()
            if chunk.embedding_model == self.embeddings.model
            and (category is None or chunk.category == category)
        ]
        if not chunks:
            return []
        query_vector = (await self.embeddings.embed([query]))[0]
        ranked = [(cosine_similarity(query_vector, chunk.embedding_json), chunk) for chunk in chunks]
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        return [RetrievedChunk(
            id=chunk.id,
            content=chunk.content,
            score=score,
            source=chunk.source,
            title=chunk.title,
            category=chunk.category,
            chunk_index=chunk.chunk_index,
        ) for score, chunk in ranked if score >= settings.rag_min_similarity][:top_k]