import argparse
import asyncio

from backend.app.core.config import settings
from backend.app.database.initialization import initialize_database
from backend.app.database.session import SessionLocal
from backend.app.rag.pipeline import RAGPipeline


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge documents and run a semantic retrieval query.")
    parser.add_argument("query")
    parser.add_argument("--ingest", action="store_true", help="Ingest supported files under KNOWLEDGE_BASE_DIR first")
    args = parser.parse_args()
    initialize_database()
    with SessionLocal() as db:
        pipeline = RAGPipeline(db)
        if args.ingest:
            print(await pipeline.ingest_directory(settings.knowledge_base_dir))
        chunks = await pipeline.retrieve(args.query)
        for chunk in chunks:
            print(f"[{chunk.score:.3f}] {chunk.title} | {chunk.category} | {chunk.source} | chunk {chunk.chunk_index}")
            print(chunk.content)
            print()


if __name__ == "__main__":
    asyncio.run(main())