"""Optional semantic similarity helpers.

The heavy ML stack (``sentence-transformers``/``torch``) is imported lazily so the
API and the test suite stay runnable when it is disabled or not installed
(``EMBEDDINGS_ENABLED`` in app/config.py).
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Sequence

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


def is_available() -> bool:
    """True when ``sentence-transformers`` can be imported."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        logger.info("sentence-transformers is not installed, semantic scoring is disabled")
        return False
    return True


def _load_model(model_name: str):
    """Load and cache the embedding model for this process."""
    with _MODEL_LOCK:
        model = _MODEL_CACHE.get(model_name)
        if model is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name)
            _MODEL_CACHE[model_name] = model
            logger.info("Embedding model loaded: %s", model_name)
        return model


def encode(texts: Sequence[str], model_name: str) -> list[list[float]]:
    """Encode ``texts`` into normalized embedding vectors."""
    model = _load_model(model_name)
    vectors = model.encode(list(texts), normalize_embeddings=True)
    return [[float(value) for value in vector] for vector in vectors]


def cosine_similarity(query: Sequence[float], candidates: Sequence[Sequence[float]]) -> list[float]:
    """Cosine similarity between one query vector and many candidate vectors."""
    query_norm = math.sqrt(sum(value * value for value in query)) or 1.0
    similarities: list[float] = []
    for candidate in candidates:
        candidate_norm = math.sqrt(sum(value * value for value in candidate)) or 1.0
        dot_product = sum(left * right for left, right in zip(query, candidate))
        similarities.append(dot_product / (query_norm * candidate_norm))
    return similarities
