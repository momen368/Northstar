import asyncio
import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database.base import Base
from backend.app.models import KnowledgeChunk
from backend.app.rag.chunker import chunk_text
from backend.app.rag.embeddings import EmbeddingProviderError, EmbeddingService
from backend.app.rag.loaders import DocumentLoadError, load_document
from backend.app.rag.pipeline import RAGPipeline
from backend.app.rag.vector_store import SQLiteVectorStore


@pytest.fixture
def database(tmp_path):
    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "rag-tests.db")))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_document_loader_cleans_text_and_infers_category(tmp_path):
    category = tmp_path / "skills"
    category.mkdir()
    path = category / "python.md"
    path.write_text("  Python\tengineering  \n\n\nData pipelines  ", encoding="utf-8")

    document = load_document(path)

    assert document.category == "skills"
    assert document.title == "python"
    assert document.content == "Python engineering\n\nData pipelines"


def test_loader_rejects_empty_and_unsupported_documents(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("  \n\t", encoding="utf-8")
    with pytest.raises(DocumentLoadError, match="no readable text"):
        load_document(empty)

    unsupported = tmp_path / "data.xlsx"
    unsupported.write_bytes(b"not supported")
    with pytest.raises(DocumentLoadError, match="Supported knowledge documents"):
        load_document(unsupported)


def test_chunker_overlaps_and_rejects_invalid_parameters():
    chunks = chunk_text("one two three four five six", chunk_size=4, overlap=1)
    assert [item.content for item in chunks] == ["one two three four", "four five six"]
    with pytest.raises(ValueError):
        chunk_text("words", chunk_size=2, overlap=2)


def test_embedding_service_sends_configured_model_and_parses_sorted_vectors(monkeypatch):
    monkeypatch.setattr(settings, "ai_base_url", "https://embeddings.example/v1")
    monkeypatch.setattr(settings, "embedding_model", "embed-test")
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [0.0, 1.0]},
            {"index": 0, "embedding": [1.0, 0.0]},
        ]})

    service = EmbeddingService(transport=httpx.MockTransport(handler))
    vectors = asyncio.run(service.embed(["first", "second"]))

    assert observed["url"].endswith("/embeddings")
    assert observed["payload"]["model"] == "embed-test"
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


def test_embedding_service_normalizes_provider_failures(monkeypatch):
    monkeypatch.setattr(settings, "ai_base_url", "https://embeddings.example/v1")
    monkeypatch.setattr(settings, "embedding_model", "test-model")
    service = EmbeddingService(
        transport=httpx.MockTransport(lambda _request: httpx.Response(500, json={"error": "secret"}))
    )
    with pytest.raises(EmbeddingProviderError, match="request failed") as error:
        asyncio.run(service.embed(["query"]))
    assert "secret" not in str(error.value)


def test_pipeline_ingests_and_retrieves_semantic_chunks_with_metadata(database, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ai_base_url", "https://embeddings.example/v1")
    monkeypatch.setattr(settings, "rag_chunk_size", 8)
    monkeypatch.setattr(settings, "rag_chunk_overlap", 1)
    monkeypatch.setattr(settings, "embedding_model", "test-embedding")
    monkeypatch.setattr(settings, "rag_min_similarity", 0.25)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        vectors = []
        for index, value in enumerate(payload["input"]):
            is_python = "python" in value.casefold()
            vectors.append({"index": index, "embedding": [1.0, 0.0] if is_python else [0.0, 1.0]})
        return httpx.Response(200, json={"data": vectors})

    service = EmbeddingService(transport=httpx.MockTransport(handler))
    pipeline = RAGPipeline(database, service)
    path = tmp_path / "skills" / "python.md"
    path.parent.mkdir()
    path.write_text("Python is used for data automation and API services.", encoding="utf-8")
    asyncio.run(pipeline.ingest_file(path))
    vector_store = SQLiteVectorStore(database, "test-embedding")
    vector_store.replace_source(
        "extra-source", "Java guide", "skills", ["Java platform development"], [[0.0, 1.0]]
    )

    retrieved = asyncio.run(pipeline.retrieve("Python automation", top_k=2))

    assert len(retrieved) == 1
    assert retrieved[0].title == "python"
    assert retrieved[0].category == "skills"
    assert retrieved[0].source == "skills/python.md"
    assert retrieved[0].score == pytest.approx(1.0)
    assert all(isinstance(chunk.id, int) and chunk.content for chunk in retrieved)


def test_reingest_replaces_source_chunks(database):
    store = SQLiteVectorStore(database, "test")
    store.replace_source("source.md", "Guide", "skills", ["old chunk"], [[1.0]])
    store.replace_source("source.md", "Guide", "skills", ["new chunk"], [[0.0, 1.0]])

    chunks = list(database.query(KnowledgeChunk).filter_by(source="source.md"))

    assert len(chunks) == 1
    assert chunks[0].content == "new chunk"