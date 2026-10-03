"""Load the dense embedding model and BM25 sparse model natively (GPU if available).

Dense embeddings come from sentence-transformers (multilingual-e5, asymmetric:
queries get a "query: " prefix, passages get a "passage: " prefix). Sparse
embeddings come from fastembed's BM25 implementation. Both models are loaded
once per process and reused across calls.
"""
from typing import Optional

import torch
from fastembed import SparseEmbedding, SparseTextEmbedding
from sentence_transformers import SentenceTransformer

from config import BGE_QUERY_INSTRUCTION, DENSE_MODEL_NAME, SPARSE_MODEL_NAME

DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"

_dense_model: Optional[SentenceTransformer] = None
_sparse_model: Optional[SparseTextEmbedding] = None


def get_dense_model() -> SentenceTransformer:
    """Return a lazily-initialized, module-level dense embedding model."""
    global _dense_model
    if _dense_model is None:
        _dense_model = SentenceTransformer(DENSE_MODEL_NAME, device=DEVICE)
    return _dense_model


def get_sparse_model() -> SparseTextEmbedding:
    """Return a lazily-initialized, module-level BM25 sparse embedding model."""
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    return _sparse_model


def encode_passage(texts: list[str]) -> list[list[float]]:
    """Embed documents/chunks for indexing — with the "passage: " prefix (e5 asymmetric).

    Args:
        texts: Raw chunk texts to embed.

    Returns:
        One dense vector per input text.
    """
    prefixed = ["passage: " + text for text in texts]
    vectors = get_dense_model().encode(prefixed, normalize_embeddings=True)
    return vectors.tolist()


def encode_query(query: str) -> list[float]:
    """Embed a search query — with the BGE query instruction prefix.

    Args:
        query: The user's natural-language question.

    Returns:
        The dense query vector.
    """
    prefixed = BGE_QUERY_INSTRUCTION + query
    vector = get_dense_model().encode(prefixed, normalize_embeddings=True)
    return vector.tolist()


def encode_sparse(texts: list[str]) -> list[SparseEmbedding]:
    """Embed texts as BM25 sparse vectors via fastembed.

    Args:
        texts: Texts to embed (chunk texts or a single-item query list).

    Returns:
        One SparseEmbedding (with .indices and .values) per input text.
    """
    return list(get_sparse_model().embed(texts))
