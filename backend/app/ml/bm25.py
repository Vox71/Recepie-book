"""Small BM25 index used by the ranking experiments.

The production model is cosine TF-IDF; this module offers a second lexical scorer that
often behaves better on short ingredient lists.  It is pure Python and uses the same
inverted-index idea as ``app.ml.evaluate``: only recipes sharing a query term are scored.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


class BM25Index:
    """BM25 over canonical ingredient terms.

    ``documents`` is the whole catalogue.  ``idf_documents`` is the training part only:
    the term document frequencies and the average length come from it, so validation and
    test recipes cannot tune the weights that rank them.
    """

    def __init__(
        self,
        documents: Sequence[Sequence[str]],
        *,
        idf_documents: Sequence[Sequence[str]] | None = None,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.documents = [tuple(document) for document in documents]
        training = self.documents if idf_documents is None else idf_documents
        self.documents_count = max(len(training), 1)
        self.average_length = (
            sum(len(document) for document in training) / self.documents_count if training else 1.0
        ) or 1.0
        self.document_lengths = [len(document) for document in self.documents]
        self.postings: dict[str, dict[int, int]] = defaultdict(dict)
        self.document_frequency: dict[str, int] = defaultdict(int)

        for document_id, document in enumerate(self.documents):
            for term in document:
                self.postings[term][document_id] = self.postings[term].get(document_id, 0) + 1
        for document in training:
            for term in set(document):
                self.document_frequency[term] += 1

        self.idf = {
            term: math.log(1.0 + (self.documents_count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in self.document_frequency.items()
        }
        self.default_idf = math.log(1.0 + (self.documents_count + 0.5) / 0.5)

    def scores(self, query_terms: Sequence[str]) -> dict[int, float]:
        """Return BM25 scores of the recipes that share at least one query term."""
        scores: dict[int, float] = defaultdict(float)
        unique_terms = tuple(dict.fromkeys(query_terms))
        for term in unique_terms:
            idf = self.idf.get(term, self.default_idf)
            for document_id, frequency in self.postings.get(term, {}).items():
                length = self.document_lengths[document_id]
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length / self.average_length
                )
                scores[document_id] += idf * frequency * (self.k1 + 1.0) / denominator
        return dict(scores)

    def candidate_ids(self, query_terms: Sequence[str]) -> set[int]:
        """Recipes that share at least one query term."""
        candidates: set[int] = set()
        for term in query_terms:
            candidates.update(self.postings.get(term, {}))
        return candidates
