"""BGE-M3 embeddings, shared by ingestion (chunks) and search (questions).

The same model must embed both, or vector search won't match.
"""

from functools import lru_cache

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL

# Chunks are capped near 800 tokens, but a few large tables or code blocks go higher.
MAX_SEQ_LENGTH = 2048


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    model.max_seq_length = MAX_SEQ_LENGTH
    if device == "cuda":
        model.half()  # fp16: half the GPU memory and faster, same retrieval quality
    return model


def embed(texts: list[str], batch_size: int = 16) -> np.ndarray:
    """Normalized vectors (cosine similarity = dot product), shape (len(texts), 1024)."""
    vectors = get_model().encode(
        texts, batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True
    )
    return vectors.astype(np.float32)  # fp16 model output → float32 for pgvector
