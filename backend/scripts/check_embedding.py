"""Check that BGE-M3 loads on the GPU and produces sensible 1024-dim vectors.

Usage: python backend/scripts/check_embedding.py
"""

import time

import torch
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL as MODEL


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'})")

    start = time.perf_counter()
    model = SentenceTransformer(MODEL, device=device)
    if device == "cuda":
        model.half()  # fp16: half the GPU memory, faster, same quality for retrieval
    print(f"Loaded {MODEL} in {time.perf_counter() - start:.1f}s, max input {model.max_seq_length} tokens")

    question = "How many days of paid time off do I get?"
    passages = [
        "Paid Time Off > Requesting PTO: GitLab has a flexible paid time off policy. "
        "Team members are encouraged to take at least 25 days off per year.",
        "Merge requests > Review: every merge request needs approval from a maintainer before it is merged.",
        "Security > Incident response: report suspected security incidents in the #security channel.",
    ]

    vectors = model.encode([question, *passages], normalize_embeddings=True)
    print(f"Vector shape: {vectors.shape}  (expect 1024 numbers per text)")

    print("\nSimilarity to the question (higher = closer in meaning):")
    for passage, score in zip(passages, vectors[1:] @ vectors[0]):
        print(f"  {score:.3f}  {passage[:70]}...")

    # Speed test with chunk-sized texts (~450 tokens each)
    batch = [" ".join(passages) * 6] * 64
    start = time.perf_counter()
    model.encode(batch, batch_size=16, normalize_embeddings=True)
    rate = len(batch) / (time.perf_counter() - start)
    print(f"\nSpeed: ~{rate:.0f} chunks/second -> 25,000 chunks in ~{25000 / rate / 60:.0f} minutes")
    if device == "cuda":
        print(f"GPU memory used: {torch.cuda.max_memory_allocated() / 1e9:.1f} GB of 6 GB")


if __name__ == "__main__":
    main()
