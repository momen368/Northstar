from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> list[TextChunk]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap must be smaller than chunk size.")
    words = re.findall(r"\S+", text)
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        content = " ".join(words[start:end])
        if content:
            chunks.append(TextChunk(index=len(chunks), content=content))
        if end == len(words):
            break
        start = end - overlap
    return chunks