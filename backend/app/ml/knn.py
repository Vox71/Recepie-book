"""Component 4 of the stub module: k nearest neighbours.

``ml_planning/ml_plan``: "алгоритм рекомендаций: реализация k-ближайших соседей (KNN)".
The stub implements the search in plain Python over the vectors of ``app.ml.vectorizer``:
the data set of one request is tiny (the recipes of one installation and the favourites
of one user), and this keeps the start-up of the API free of the heavy ML stack.
Switching to ``sklearn.neighbors.NearestNeighbors`` (the library is already in
``requirements.txt``) means replacing ``k_nearest`` only.
"""

from __future__ import annotations

from typing import Sequence

from .vectorizer import Vector, similarity

Neighbour = tuple[int, float]


def k_nearest(profile: Vector, candidates: Sequence[Vector], *, k: int) -> list[Neighbour]:
    """Return ``(index, similarity)`` of the ``k`` closest ``candidates``.

    The result is sorted by similarity (most similar first) and truncated to ``k``.
    Candidates with equal similarity keep their input order, because ``list.sort`` is
    stable: the same input always gives the same answer.
    """
    scored: list[Neighbour] = [
        (index, similarity(profile, candidate)) for index, candidate in enumerate(candidates)
    ]
    scored.sort(key=lambda neighbour: neighbour[1], reverse=True)
    return scored[: max(k, 0)]
