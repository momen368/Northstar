import hashlib
import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.models import KnowledgeChunk


class SQLiteVectorStore:
    def __init__(self, db: Session, embedding_model: str) -> None:
        self.db = db
        self.embedding_model = embedding_model

    def replace_source(
        self,
        source: str,
        title: str,
        category: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Each knowledge chunk must have exactly one embedding.")
        self.db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source == source))
        for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            self.db.add(KnowledgeChunk(
                source=source,
                category=category,
                title=title,
                chunk_index=index,
                content=content,
                embedding_json=embedding,
                embedding_model=self.embedding_model,
                content_hash=digest,
            ))
        self.db.commit()
        return len(chunks)

    def all_chunks(self) -> list[KnowledgeChunk]:
        return list(self.db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.id)))