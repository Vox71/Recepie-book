"""Co-occurrence/PMI scorer for ingredient ranking.

A hidden ingredient is absent from the query, so lexical similarity alone has little
signal.  The products that remain in the query, however, often co-occur with it in the
training corpus.  This index turns those co-occurrences into a positive PMI score and
maps the score back to the recipes that contain the associated product.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

from .bm25 import BM25Index

DEFAULT_MIN_PMI = 0.0


class CooccurrenceIndex:
    """Positive PMI associations learned only from the training recipes."""

    def __init__(
        self,
        training_documents: Sequence[Sequence[str]],
        *,
        all_documents: Sequence[Sequence[str]] | None = None,
        min_pmi: float = DEFAULT_MIN_PMI,
    ) -> None:
        self.documents_count = max(len(training_documents), 1)
        self.document_frequency: dict[str, int] = defaultdict(int)
        pair_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for document in training_documents:
            terms = tuple(dict.fromkeys(document))
            for term in terms:
                self.document_frequency[term] += 1
            for left in terms:
                for right in terms:
                    if left != right:
                        pair_counts[left][right] += 1

        self.associations: dict[str, dict[str, float]] = {}
        for left, neighbours in pair_counts.items():
            left_frequency = self.document_frequency[left]
            scored: dict[str, float] = {}
            for right, count in neighbours.items():
                right_frequency = self.document_frequency[right]
                pmi = math.log((count * self.documents_count) / (left_frequency * right_frequency))
                if pmi > min_pmi:
                    scored[right] = pmi
            if scored:
                self.associations[left] = scored

        self._postings = BM25Index(all_documents or training_documents)

    def scores(self, query_terms: Sequence[str]) -> dict[int, float]:
        """Score recipes by positive PMI between query terms and their own ingredients."""
        scores: dict[int, float] = defaultdict(float)
        unique_query = tuple(dict.fromkeys(query_terms))
        if not unique_query:
            return {}
        for query_term in unique_query:
            for related, pmi in self.associations.get(query_term, {}).items():
                for document_id in self._postings.postings.get(related, {}):
                    scores[document_id] += pmi
        return dict(scores)
