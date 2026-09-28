from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.rag.chunker import chunk_text
from backend.app.rag.embeddings import EmbeddingService
from backend.app.rag.loaders import LoadedDocument, load_document
from backend.app.rag.retriever import RetrievedChunk, SemanticRetriever
from backend.app.rag.vector_store import SQLiteVectorStore


class RAGPipeline:
    def __init__(self, db: Session, embeddings: EmbeddingService | None = None) -> None:
        self.db = db
        self.embeddings = embeddings or EmbeddingService()
        self.store = SQLiteVectorStore(db, self.embeddings.model)
        self.retriever = SemanticRetriever(self.store, self.embeddings)

    async def ingest_file(self, path: str | Path, category: str | None = None) -> int:
        document = load_document(path, category)
        return await self.ingest_document(document)

    async def ingest_document(self, document: LoadedDocument) -> int:
        chunks = chunk_text(document.content, settings.rag_chunk_size, settings.rag_chunk_overlap)
        if not chunks:
            raise ValueError("Knowledge document contains no chunks.")
        embeddings = await self.embeddings.embed([chunk.content for chunk in chunks])
        return self.store.replace_source(
            document.source,
            document.title,
            document.category,
            [chunk.content for chunk in chunks],
            embeddings,
        )

    async def ingest_directory(self, directory: str | Path | None = None) -> dict[str, int]:
        root = Path(directory or settings.knowledge_base_dir)
        if not root.is_dir():
            raise ValueError("Knowledge base directory does not exist.")
        results = {}
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.casefold() in {".txt", ".md", ".pdf", ".docx"}:
                results[str(path)] = await self.ingest_file(path)
        return results

    async def retrieve(self, query: str, top_k: int | None = None, category: str | None = None) -> list[RetrievedChunk]:
        return await self.retriever.retrieve(query, top_k or settings.rag_top_k, category)