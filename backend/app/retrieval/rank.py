"""Merge the vector and keyword lists with reciprocal rank fusion, then rerank.

RRF: each list contributes 1 / (RRF_K + rank) for every chunk it found. Scores from
the two searches aren't comparable (cosine similarity vs. ts_rank), but ranks are, so
a chunk found high in both lists ends up on top.

Reranker: a cross-encoder reads the question and each chunk together and scores how
well the chunk answers the question. Much more accurate than the embedding comparison,
but too slow for 30,000 chunks, so it only sees the top RERANK_POOL after RRF.
"""

from functools import lru_cache

import torch
from sentence_transformers import CrossEncoder

from app.config import RERANK_MODEL
from app.retrieval.search import Candidate

RRF_K = 60          # standard constant from the RRF paper; dampens the gap between ranks
RERANK_POOL = 50    # chunks the reranker reads
FINAL_K = 5         # chunks passed on to the LLM
RERANK_MAX_LENGTH = 1024


def rrf_merge(candidates: list[Candidate]) -> list[Candidate]:
    for c in candidates:
        c.rrf_score = sum(1 / (RRF_K + rank) for rank in (c.vector_rank, c.keyword_rank) if rank)
    return sorted(candidates, key=lambda c: c.rrf_score, reverse=True)


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32  # fp16: half the GPU memory, faster
    return CrossEncoder(
        RERANK_MODEL, device=device, max_length=RERANK_MAX_LENGTH, model_kwargs={"torch_dtype": dtype}
    )


def rerank(question: str, candidates: list[Candidate], top_k: int = FINAL_K) -> list[Candidate]:
    if not candidates:
        return []
    scores = get_reranker().predict(
        [(question, c.embed_text) for c in candidates], batch_size=16, activation_fn=torch.nn.Sigmoid()
    )
    for c, score in zip(candidates, scores):
        c.rerank_score = float(score)
    return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]
