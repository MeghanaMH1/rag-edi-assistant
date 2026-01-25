import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Mock embedding generator.
    Each text is converted to a simple numeric vector.
    """
    embeddings = []
    for text in texts:
        # simple deterministic embedding (length-based)
        vector = [len(text), sum(ord(c) for c in text) % 1000]
        embeddings.append(vector)
    return embeddings


def embed_text(text: str) -> list[float]:
    """
    Embed a single question string.
    """
    return [len(text), sum(ord(c) for c in text) % 1000]


def find_similar_rows(
    query_embedding: list[float],
    row_embeddings: list[list[float]],
    rows: list[dict],
    top_k: int = 5
) -> list[dict]:
    """
    Find top-k similar rows using cosine similarity.
    """
    if not row_embeddings:
        return []

    similarities = cosine_similarity(
        [query_embedding],
        row_embeddings
    )[0]

    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [rows[i] for i in top_indices]
