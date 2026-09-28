import math

import httpx

from backend.app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingProviderError(EmbeddingError):
    pass


class EmbeddingService:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = settings.ai_base_url
        self.api_key = settings.ai_api_key
        self.model = settings.embedding_model
        self.timeout = settings.ai_timeout_seconds
        self.transport = transport

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Embedding input must contain non-empty text.")
        if not self.base_url.strip() or not self.model.strip():
            raise EmbeddingConfigurationError("Embedding provider is not configured.")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/embeddings",
                    headers=headers,
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
            items = response.json()["data"]
            items.sort(key=lambda item: item["index"])
            vectors = [[float(value) for value in item["embedding"]] for item in items]
            if len(vectors) != len(texts) or any(not vector or not all(math.isfinite(value) for value in vector)
                                                   for vector in vectors):
                raise ValueError("Invalid embedding vector dimensions or values")
            return vectors
        except httpx.TimeoutException as exc:
            raise EmbeddingProviderError("Embedding provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError("Embedding provider request failed.") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError("Embedding provider returned invalid vectors.") from exc