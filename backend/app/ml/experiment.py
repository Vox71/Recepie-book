"""Honest ranking experiment: split, BM25, co-occurrence and a hybrid scorer.

This is a separate command from the production ``app.ml.evaluate`` because it changes two
important things:

* the corpus is split by recipe into train/validation/test, and IDF/associations are
  learned on the training part only;
* the candidate ranking is compared for BM25, positive-PMI co-occurrence and a weighted
  hybrid, not only for the old TF-IDF model.

The protocol remains leave-one-ingredient-out, the one already used by
``docs/recommendation-model.md``: the hidden product is never part of the query, so the
numbers describe how well a scorer recovers it from the remaining ingredients.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from ..config import Settings
from . import corpus
from .bm25 import BM25Index
from .cooccurrence import CooccurrenceIndex
from .normalization import canonical_ingredients

logger = logging.getLogger(__name__)

DEFAULT_K = 10
DEFAULT_SEED = 42
DEFAULT_TRAIN_RATIO = 0.70
DEFAULT_VALIDATION_RATIO = 0.15
DEFAULT_MAX_QUERIES = 1_500
DEFAULT_WEIGHTS = (0.55, 0.35, 0.10)
EXIT_OK = 0
EXIT_FAILED = 1


@dataclass(frozen=True)
class Metrics:
    """Mean ranking metrics over the queries of one scorer."""

    queries: int
    k: int
    precision_at_1: float
    precision_at_k: float
    recall_at_k: float
    hit_rate: float
    mrr: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "queries": self.queries,
            "k": self.k,
            "p@1": round(self.precision_at_1, 4),
            f"p@{self.k}": round(self.precision_at_k, 4),
            f"r@{self.k}": round(self.recall_at_k, 4),
            f"hit@{self.k}": round(self.hit_rate, 4),
            "mrr": round(self.mrr, 4),
        }


@dataclass(frozen=True)
class QueryResult:
    """Cached component scores of one query; the source recipe is excluded."""

    source: int
    target: str
    query_terms: tuple[str, ...]
    relevant: frozenset[int]
    components: dict[int, tuple[float, float, float]]
    max_bm25: float
    max_cooccurrence: float


@dataclass(frozen=True)
class ExperimentResult:
    """Everything that a report needs: sizes, chosen weights and both metric tables."""

    recipes: int
    train_size: int
    validation_size: int
    test_size: int
    k: int
    seed: int
    weights: tuple[float, float, float]
    validation: dict[str, Metrics]
    test: dict[str, Metrics]

    def as_dict(self) -> dict:
        return {
            "recipes": self.recipes,
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            "test_size": self.test_size,
            "k": self.k,
            "seed": self.seed,
            "weights": {
                "bm25": self.weights[0],
                "cooccurrence": self.weights[1],
                "overlap": self.weights[2],
            },
            "validation": {name: metrics.as_dict() for name, metrics in self.validation.items()},
            "test": {name: metrics.as_dict() for name, metrics in self.test.items()},
        }


def split_indices(
    count: int,
    *,
    seed: int = DEFAULT_SEED,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> tuple[list[int], list[int], list[int]]:
    """Return shuffled global indices of the train, validation and test parts."""
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    if not 0 < validation_ratio < 1 or train_ratio + validation_ratio >= 1:
        raise ValueError("validation_ratio must leave a non-empty test part")
    indices = list(range(count))
    random.Random(seed).shuffle(indices)
    train_end = max(1, int(count * train_ratio))
    validation_end = max(train_end + 1, int(count * (train_ratio + validation_ratio)))
    train = indices[:train_end]
    validation = indices[train_end:validation_end]
    test = indices[validation_end:]
    if not validation or not test:
        raise ValueError("the corpus is too small for a train/validation/test split")
    return train, validation, test


def split_entries(
    entries: Sequence[corpus.RecipeEntry],
    *,
    seed: int = DEFAULT_SEED,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> tuple[list[corpus.RecipeEntry], list[corpus.RecipeEntry], list[corpus.RecipeEntry]]:
    """Shuffle recipes deterministically and split them into train/validation/test."""
    train_indices, validation_indices, test_indices = split_indices(
        len(entries),
        seed=seed,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
    )
    return (
        [entries[index] for index in train_indices],
        [entries[index] for index in validation_indices],
        [entries[index] for index in test_indices],
    )


def _term_postings(documents: Sequence[Sequence[str]]) -> dict[str, set[int]]:
    postings: dict[str, set[int]] = {}
    for recipe_id, document in enumerate(documents):
        for term in document:
            postings.setdefault(term, set()).add(recipe_id)
    return postings


def _iter_queries(
    entries: Sequence[corpus.RecipeEntry],
    *,
    source_ids: Sequence[int],
    documents: Sequence[Sequence[str]],
    postings: dict[str, set[int]],
    bm25: BM25Index,
    cooccurrence: CooccurrenceIndex,
) -> Iterator[QueryResult]:
    """Yield leave-one-ingredient-out queries with component scores.

    The generator is intentional: a full 12k corpus has tens of thousands of queries,
    and keeping every candidate score of every query in a list exhausts memory.  The
    caller consumes one query at a time and keeps only running metric totals.
    """
    for local_id, entry in enumerate(entries):
        recipe_id = source_ids[local_id]
        # Pantry products do not separate recipes, so they are neither targets nor query
        # terms.  The hidden product itself is still taken from the canonical list.
        targets = canonical_ingredients(entry.ingredients, drop_pantry=True)
        for target in targets:
            query_terms = tuple(term for term in targets if term != target)
            if not query_terms:
                continue
            relevant = set(postings.get(target, set())) - {recipe_id}
            if not relevant:
                continue

            bm25_scores = bm25.scores(query_terms)
            cooccurrence_scores = cooccurrence.scores(query_terms)
            candidate_ids = set(bm25_scores) | set(cooccurrence_scores)
            candidate_ids.discard(recipe_id)
            components: dict[int, tuple[float, float, float]] = {}
            query_set = set(query_terms)
            for candidate_id in candidate_ids:
                overlap = len(query_set & set(documents[candidate_id])) / len(query_set)
                components[candidate_id] = (
                    bm25_scores.get(candidate_id, 0.0),
                    cooccurrence_scores.get(candidate_id, 0.0),
                    overlap,
                )
            if not components:
                continue
            yield QueryResult(
                source=recipe_id,
                target=target,
                query_terms=query_terms,
                relevant=frozenset(relevant),
                components=components,
                max_bm25=max(value[0] for value in components.values()) or 1.0,
                max_cooccurrence=max(value[1] for value in components.values()) or 1.0,
            )


def _ranking(query: QueryResult, weights: tuple[float, float, float], k: int) -> list[int]:
    """Top-``k`` recipe ids for one query and one set of component weights."""
    bm25_weight, cooccurrence_weight, overlap_weight = weights
    scored: list[tuple[float, int]] = []
    for recipe_id, (bm25, cooccurrence, overlap) in query.components.items():
        score = (
            bm25_weight * (bm25 / query.max_bm25)
            + cooccurrence_weight * (cooccurrence / query.max_cooccurrence)
            + overlap_weight * overlap
        )
        scored.append((score, recipe_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [recipe_id for _, recipe_id in scored[: max(k, 0)]]


def metrics_for(
    queries: Sequence[QueryResult], weights: tuple[float, float, float], *, k: int
) -> Metrics:
    """Compute the five ranking metrics for one weight configuration."""
    if not queries:
        raise ValueError("no query with a relevant recipe")
    totals = [0.0] * 5
    for query in queries:
        ranking = _ranking(query, weights, k)
        relevant = query.relevant
        hits = sum(1 for recipe_id in ranking if recipe_id in relevant)
        totals[0] += 1.0 if ranking and ranking[0] in relevant else 0.0
        totals[1] += hits / k if k else 0.0
        totals[2] += hits / min(len(relevant), k) if k else 0.0
        totals[3] += 1.0 if hits else 0.0
        for position, recipe_id in enumerate(ranking, start=1):
            if recipe_id in relevant:
                totals[4] += 1.0 / position
                break
    count = len(queries)
    return Metrics(
        queries=count,
        k=k,
        precision_at_1=totals[0] / count,
        precision_at_k=totals[1] / count,
        recall_at_k=totals[2] / count,
        hit_rate=totals[3] / count,
        mrr=totals[4] / count,
    )


def evaluate_strategies(
    queries: Iterable[QueryResult],
    strategies: Mapping[str, tuple[float, float, float]],
    *,
    k: int,
) -> dict[str, Metrics]:
    """Evaluate several weight configurations in one streaming pass."""
    totals: dict[str, list[float]] = {name: [0.0] * 5 for name in strategies}
    count = 0
    for query in queries:
        count += 1
        for name, weights in strategies.items():
            ranking = _ranking(query, weights, k)
            relevant = query.relevant
            hits = sum(1 for recipe_id in ranking if recipe_id in relevant)
            values = totals[name]
            values[0] += 1.0 if ranking and ranking[0] in relevant else 0.0
            values[1] += hits / k if k else 0.0
            values[2] += hits / min(len(relevant), k) if k else 0.0
            values[3] += 1.0 if hits else 0.0
            for position, recipe_id in enumerate(ranking, start=1):
                if recipe_id in relevant:
                    values[4] += 1.0 / position
                    break
    if not count:
        raise ValueError("no query with a relevant recipe")
    return {
        name: Metrics(
            queries=count,
            k=k,
            precision_at_1=values[0] / count,
            precision_at_k=values[1] / count,
            recall_at_k=values[2] / count,
            hit_rate=values[3] / count,
            mrr=values[4] / count,
        )
        for name, values in totals.items()
    }


def choose_weights(
    queries: Sequence[QueryResult], *, k: int = DEFAULT_K
) -> tuple[float, float, float]:
    """Pick hybrid weights on a validation slice by MRR, then P@k."""
    # A small grid is enough: the components are already normalized to their query maximum.
    options: list[tuple[float, float, float]] = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for bm25_weight in (0.25, 0.5, 0.75, 1.0):
        for cooccurrence_weight in (0.25, 0.5, 0.75, 1.0):
            options.append((bm25_weight, cooccurrence_weight, 0.1))
    options.extend([(0.5, 0.3, 0.2), (0.6, 0.3, 0.1), (0.4, 0.4, 0.2)])

    best = options[0]
    slice_ = queries[: min(len(queries), 800)]
    best_metrics = metrics_for(slice_, best, k=k)
    for weights in options[1:]:
        current = metrics_for(slice_, weights, k=k)
        if (current.mrr, current.precision_at_k) > (best_metrics.mrr, best_metrics.precision_at_k):
            best, best_metrics = weights, current
    return best


def run_experiment(
    entries: Sequence[corpus.RecipeEntry],
    *,
    k: int = DEFAULT_K,
    seed: int = DEFAULT_SEED,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    max_queries: int = DEFAULT_MAX_QUERIES,
) -> ExperimentResult:
    """Run the split, fit the lexical models and report validation and test metrics."""
    if not entries:
        raise ValueError("the corpus is empty")
    train_indices, validation_indices, test_indices = split_indices(
        len(entries), seed=seed, train_ratio=train_ratio, validation_ratio=validation_ratio
    )
    train = [entries[index] for index in train_indices]
    validation = [entries[index] for index in validation_indices]
    test = [entries[index] for index in test_indices]
    all_documents = [canonical_ingredients(entry.ingredients) for entry in entries]
    train_documents = [all_documents[index] for index in train_indices]
    postings = _term_postings(all_documents)
    bm25 = BM25Index(all_documents, idf_documents=train_documents)
    cooccurrence = CooccurrenceIndex(train_documents, all_documents=all_documents)

    validation_queries = _iter_queries(
        validation,
        source_ids=validation_indices,
        documents=all_documents,
        postings=postings,
        bm25=bm25,
        cooccurrence=cooccurrence,
    )
    test_queries = _iter_queries(
        test,
        source_ids=test_indices,
        documents=all_documents,
        postings=postings,
        bm25=bm25,
        cooccurrence=cooccurrence,
    )
    # Tune on a bounded validation slice, then evaluate a bounded sample.  The full
    # 12k product catalogue is used for training and candidate retrieval; limits apply
    # only to the number of held-out queries, so memory and runtime stay predictable.
    tuning_queries = list(islice(validation_queries, min(300, max_queries)))
    weights = choose_weights(tuning_queries, k=k)
    strategies = {
        "bm25": (1.0, 0.0, 0.0),
        "cooccurrence": (0.0, 1.0, 0.0),
        "hybrid": weights,
    }
    # The iterators above can only be consumed once.  Rebuild them after the sample.
    validation_queries = islice(
        _iter_queries(
            validation,
            source_ids=validation_indices,
            documents=all_documents,
            postings=postings,
            bm25=bm25,
            cooccurrence=cooccurrence,
        ),
        max_queries,
    )
    test_queries = islice(
        _iter_queries(
            test,
            source_ids=test_indices,
            documents=all_documents,
            postings=postings,
            bm25=bm25,
            cooccurrence=cooccurrence,
        ),
        max_queries,
    )
    return ExperimentResult(
        recipes=len(entries),
        train_size=len(train),
        validation_size=len(validation),
        test_size=len(test),
        k=k,
        seed=seed,
        weights=weights,
        validation=evaluate_strategies(validation_queries, strategies, k=k),
        test=evaluate_strategies(test_queries, strategies, k=k),
    )


def format_report(result: ExperimentResult) -> str:
    """Render the experiment as a compact text table."""
    lines = [
        f"Corpus: {result.recipes} recipes; train {result.train_size}, "
        f"validation {result.validation_size}, test {result.test_size}; k={result.k}",
        f"weights: bm25={result.weights[0]:.2f}, cooc={result.weights[1]:.2f}, "
        f"overlap={result.weights[2]:.2f}",
        "",
        f"{'split':<12}{'strategy':<14}{'P@1':>8}{'P@k':>8}{'R@k':>8}"
        f"{'Hit@k':>8}{'MRR':>8}{'queries':>9}",
    ]
    for split_name, table in (("validation", result.validation), ("test", result.test)):
        for strategy, metrics in table.items():
            lines.append(
                f"{split_name:<12}{strategy:<14}{metrics.precision_at_1:>8.3f}"
                f"{metrics.precision_at_k:>8.3f}{metrics.recall_at_k:>8.3f}"
                f"{metrics.hit_rate:>8.3f}{metrics.mrr:>8.3f}{metrics.queries:>9}"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Arguments of ``python -m app.ml.experiment``."""
    parser = argparse.ArgumentParser(
        prog="python -m app.ml.experiment",
        description="Honest split with BM25, co-occurrence and a hybrid ranking.",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=corpus.DEFAULT_CORPUS,
        help=f"corpus file (default: {corpus.DEFAULT_CORPUS})",
    )
    parser.add_argument("--from-db", action="store_true", help="read DATABASE_URL")
    parser.add_argument("--limit", type=int, default=corpus.DEFAULT_DATABASE_LIMIT)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO)
    parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO)
    parser.add_argument(
        "--max-queries",
        type=int,
        default=DEFAULT_MAX_QUERIES,
        help="held-out queries evaluated per split (default: 1500)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the experiment from the command line."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args(argv)
    settings = Settings.from_env()
    try:
        if arguments.from_db:
            if not settings.database_url:
                raise ValueError("--from-db needs DATABASE_URL")
            entries = corpus.from_database(settings.database_url, limit=arguments.limit)
        else:
            entries = corpus.load_corpus(arguments.sample)
        result = run_experiment(
            entries,
            k=arguments.k,
            seed=arguments.seed,
            train_ratio=arguments.train_ratio,
            validation_ratio=arguments.validation_ratio,
            max_queries=arguments.max_queries,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    if arguments.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
