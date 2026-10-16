"""Component 2 of the stub module: vectorization ("преобразование текстов рецептов").

``ml_planning/ml_plan`` names SBERT as the vectorizer of the module.  The stub uses it
when the optional ML stack is installed and switched on (``EMBEDDINGS_ENABLED``, see
``app/embeddings.py``, which imports the heavy stack lazily) and otherwise falls back to
a sparse bag-of-lemmas vector.  The fallback keeps the endpoint runnable - and the test
suite deterministic - without ``torch``.  Only ``similarity`` and ``centroid`` know both
backends; the rest of the pipeline is backend agnostic.
"""

from __future__ import annotations

import logging
import math
from typing import Sequence

from .. import embeddings
from ..config import Settings
from .preprocessing import lemmatize_terms

logger = logging.getLogger(__name__)

SPARSE_BACKEND = "sparse-bow"
SBERT_BACKEND = "sbert"
EMBEDDING_ERRORS = (ImportError, OSError, RuntimeError, ValueError)

SparseVector = dict[str, float]
DenseVector = list[float]
Vector = SparseVector | DenseVector


def sparse_vector(text: str) -> SparseVector:
    """Bag-of-lemmas vector of ``text``: every lemma of the text gets the weight 1.0."""
    return dict.fromkeys(lemmatize_terms([text]), 1.0)


def encode_texts(texts: Sequence[str], settings: Settings) -> tuple[list[Vector], str]:
    """Vectorize ``texts`` and report the backend that was used.

    Returns ``(vectors, backend)`` where ``backend`` is ``SBERT_BACKEND`` for sentence
    embeddings and ``SPARSE_BACKEND`` for the fallback.
    """
    if settings.embeddings_enabled and embeddings.is_available():
        try:
            dense = embeddings.encode(list(texts), settings.embedding_model)
        except EMBEDDING_ERRORS:
            logger.warning(
                "SBERT vectorization failed, the module falls back to bag-of-words",
                exc_info=True,
            )
        else:
            return [list(vector) for vector in dense], SBERT_BACKEND
    return [sparse_vector(text) for text in texts], SPARSE_BACKEND


def centroid(vectors: Sequence[Vector]) -> Vector:
    """Centroid of a vector set: the average of the training sample (empty set -> 0)."""
    if not vectors:
        return {}
    size = len(vectors)
    if isinstance(vectors[0], dict):
        total: SparseVector = {}
        for vector in vectors:
            for term, weight in vector.items():
                total[term] = total.get(term, 0.0) + weight
        return {term: weight / size for term, weight in total.items()}
    width = len(vectors[0])
    return [sum(float(vector[index]) for vector in vectors) / size for index in range(width)]


def similarity(left: Vector, right: Vector) -> float:
    """Cosine similarity of two vectors produced by the same backend."""
    if isinstance(left, dict) and isinstance(right, dict):
        return _sparse_cosine(left, right)
    if isinstance(left, list) and isinstance(right, list):
        return _dense_cosine(left, right)
    raise ValueError("Vector backends must not be mixed")


def _sparse_cosine(left: SparseVector, right: SparseVector) -> float:
    """Cosine similarity of two sparse vectors (the shorter one drives the product)."""
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = sum(weight * right.get(term, 0.0) for term, weight in left.items())
    if dot == 0.0:
        return 0.0
    return dot / (_sparse_norm(left) * _sparse_norm(right))


def _sparse_norm(vector: SparseVector) -> float:
    """Euclidean norm of a sparse vector, never zero (protects the division)."""
    return math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0


def _dense_cosine(left: DenseVector, right: DenseVector) -> float:
    """Cosine similarity of two dense vectors (the SBERT backend)."""
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot / (left_norm * right_norm)
