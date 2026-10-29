"""Task 6.2 of sprint 2: ranking metrics of the v1 model against the baseline.

The question the numbers answer is the one of the fridge: *the user has a few products -
does the service find recipes that actually use them?*  The protocol is
**leave-one-ingredient-out**, the one named in ``docs/sprint-2-plan.md``:

1. take a recipe of the corpus and hide one of its ingredients ``x``;
2. the rest of its ingredient list is the query - as if those products were in the fridge;
3. rank the whole corpus by cosine similarity (the same ranking the endpoint uses);
4. the relevant recipes are those whose ingredient list contains ``x`` (by lemma).

Over all recipes and all their ingredients this gives one number per metric:

* ``P@1`` - share of queries whose first recommendation uses the hidden product;
* ``P@k`` - share of the ``k`` recommended recipes that use it;
* ``R@k`` - share of relevant recipes found in the top ``k`` (capped at ``k``);
* ``Hit@k`` - share of queries with at least one relevant recipe in the top ``k``;
* ``MRR@k`` - mean of ``1 / rank`` of the first relevant recipe.

Two strategies run on the same queries and the same corpus:

* ``baseline`` - the bag-of-lemmas vector of ``app.ml.vectorizer`` (weight 1.0 per lemma),
  i.e. what the module did before task 6.0;
* ``v1`` - the TF-IDF model of ``app.ml.model``.

The command fails (exit code 1) when v1 is not better than the baseline on ``P@k`` and
``MRR`` - that is the acceptance criterion of task 6.0.  The numbers of the last run are
recorded in ``docs/recommendation-model.md``.

Usage (from ``backend/``)::

    python -m app.ml.evaluate
    python -m app.ml.evaluate --k 10 --json
    python -m app.ml.evaluate --from-db --limit 20000
    python -m app.ml.evaluate --model app/ml/artifacts/v1.json   # the artifact production uses
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..config import Settings
from . import corpus, model as model_module, vectorizer
from .preprocessing import lemmatize_terms

logger = logging.getLogger(__name__)

DEFAULT_K = 5
EXIT_OK = 0
EXIT_FAILED = 1

STRATEGIES = ("baseline", "v1")

BUCKET_NAMES = ("all", "rare", "medium", "common")
"""Query groups by how many recipes of the corpus use the hidden product."""

RARE_MAX_DOCUMENTS = 5
MEDIUM_MAX_DOCUMENTS = 20


@dataclass(frozen=True)
class Metrics:
    """Mean ranking quality over the queries of one strategy."""

    queries: int
    k: int
    precision_at_1: float
    precision_at_k: float
    recall_at_k: float
    hit_rate: float
    mrr: float

    def as_dict(self) -> dict:
        """Plain dictionary for ``--json`` and for the report."""
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
class Bucket:
    """Metrics of one group of queries, split by how common the hidden product is."""

    name: str
    queries: int
    baseline: Metrics
    model: Metrics

    @property
    def precision_gain(self) -> float:
        """Difference of ``P@k`` between v1 and the baseline, in shares."""
        return self.model.precision_at_k - self.baseline.precision_at_k


@dataclass(frozen=True)
class Evaluation:
    """Result of one run: the corpus size, the queries and both strategies."""

    recipes: int
    vocabulary: int
    k: int
    skipped_queries: int
    baseline: Metrics
    model: Metrics
    buckets: tuple[Bucket, ...]

    @property
    def improved(self) -> bool:
        """True when v1 is better than the baseline on both gated metrics."""
        return (
            self.model.precision_at_k > self.baseline.precision_at_k
            and self.model.mrr > self.baseline.mrr
        )


def evaluate(
    entries: Sequence[corpus.RecipeEntry],
    *,
    k: int = DEFAULT_K,
    model: "model_module.TfidfModel | None" = None,
) -> Evaluation:
    """Score both strategies on ``entries`` with the leave-one-ingredient-out protocol."""
    if not entries:
        raise ValueError("the corpus is empty: nothing to evaluate")
    texts = [entry.text for entry in entries]
    model = model or model_module.fit(texts, source="corpus")
    baseline_vectors = [vectorizer.sparse_vector(text) for text in texts]
    model_vectors = [model.vector(text) for text in texts]
    index = _lemma_index(baseline_vectors)
    ingredient_lemmas = [
        [frozenset(lemmatize_terms([name])) for name in entry.ingredients] for entry in entries
    ]

    totals: dict[str, dict[str, list[float]]] = {
        name: {bucket: [0.0] * 5 for bucket in BUCKET_NAMES} for name in STRATEGIES
    }
    counts: dict[str, int] = {bucket: 0 for bucket in BUCKET_NAMES}
    queries = 0
    skipped = 0
    for position, lemmas in enumerate(ingredient_lemmas):
        for hidden, target in enumerate(lemmas):
            if not target:
                continue
            relevant = _relevant(index, target, exclude=position)
            if not relevant:
                skipped += 1  # the product occurs in this recipe only: nothing to find
                continue
            query_text = ", ".join(
                entry_ingredient
                for index_of, entry_ingredient in enumerate(entries[position].ingredients)
                if index_of != hidden
            )
            profiles = {
                "baseline": vectorizer.sparse_vector(query_text),
                "v1": model.vector(query_text),
            }
            if not profiles["baseline"]:
                skipped += 1
                continue
            queries += 1
            bucket = _bucket(index, target)
            counts["all"] += 1
            counts[bucket] += 1
            for name, vectors in (("baseline", baseline_vectors), ("v1", model_vectors)):
                ranking = _rank(profiles[name], vectors, index, k=k, exclude=position)
                _accumulate(totals[name]["all"], ranking, relevant, k)
                _accumulate(totals[name][bucket], ranking, relevant, k)

    if not queries:
        raise ValueError("no query with a relevant recipe: the corpus is too small")
    return Evaluation(
        recipes=len(entries),
        vocabulary=model.vocabulary_size,
        k=k,
        skipped_queries=skipped,
        baseline=_metrics(totals["baseline"]["all"], queries, k),
        model=_metrics(totals["v1"]["all"], queries, k),
        buckets=tuple(
            Bucket(
                name=bucket,
                queries=counts[bucket],
                baseline=_metrics(totals["baseline"][bucket], counts[bucket], k),
                model=_metrics(totals["v1"][bucket], counts[bucket], k),
            )
            for bucket in BUCKET_NAMES
            if bucket != "all" and counts[bucket]
        ),
    )


def _lemma_index(vectors: Sequence[Mapping[str, float]]) -> dict[str, set[int]]:
    """Inverted index lemma -> recipes that mention it (relevance and candidate search).

    The corpus of the real dataset is too big for a full scan per query, so the candidates
    of a query are the recipes that share at least one lemma with it.  Everything else has
    a cosine similarity of exactly 0 and is never recommended by the engine either
    (``app.ml.engine`` drops recipes with a non-positive score), so the ranking is the same
    as the one of a full scan.
    """
    index: dict[str, set[int]] = {}
    for position, vector in enumerate(vectors):
        for lemma in vector:
            index.setdefault(lemma, set()).add(position)
    return index


def _relevant(index: Mapping[str, set[int]], target: frozenset[str], *, exclude: int) -> set[int]:
    """Recipes whose ingredient list contains every lemma of the hidden product."""
    found: set[int] | None = None
    for lemma in target:
        positions = index.get(lemma, set())
        found = set(positions) if found is None else found & positions
        if not found:
            return set()
    return (found or set()) - {exclude}


def _bucket(index: Mapping[str, set[int]], target: frozenset[str]) -> str:
    """Bucket of a query: how many recipes of the corpus use the hidden product.

    The split exists because the two strategies can only differ on products that are
    *not* everywhere: ``соль`` occurs in half of the corpus, so both rank the same, while
    ``шафран`` is exactly the word IDF is for.  The report of task 6.2 shows both totals
    and this breakdown, so a reader can see where the gain comes from.
    """
    documents = min(len(index.get(lemma, set())) for lemma in target)
    if documents <= RARE_MAX_DOCUMENTS:
        return "rare"
    if documents <= MEDIUM_MAX_DOCUMENTS:
        return "medium"
    return "common"


def _rank(
    profile: Mapping[str, float],
    vectors: Sequence[Mapping[str, float]],
    index: Mapping[str, set[int]],
    *,
    k: int,
    exclude: int,
) -> list[int]:
    """Top-``k`` recipe positions by cosine similarity, the source recipe left out."""
    candidates: set[int] = set()
    for lemma in profile:
        candidates |= index.get(lemma, set())
    scored: list[tuple[int, float]] = []
    for position in candidates:
        if position == exclude:
            continue
        similarity = vectorizer.similarity(profile, vectors[position])
        if similarity > 0:
            scored.append((position, similarity))
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [position for position, _ in scored[: max(k, 0)]]


def _accumulate(totals: list[float], ranking: Sequence[int], relevant: set[int], k: int) -> None:
    """Add one query to the running sums: P@1, P@k, R@k, hit, reciprocal rank."""
    hits = sum(1 for position in ranking if position in relevant)
    totals[0] += 1.0 if ranking and ranking[0] in relevant else 0.0
    totals[1] += hits / k if k else 0.0
    totals[2] += hits / min(len(relevant), k) if k else 0.0
    totals[3] += 1.0 if hits else 0.0
    for position, recipe in enumerate(ranking, start=1):
        if recipe in relevant:
            totals[4] += 1.0 / position
            break


def _metrics(totals: Sequence[float], queries: int, k: int) -> Metrics:
    """Turn the running sums into the mean metrics of one strategy."""
    return Metrics(
        queries=queries,
        k=k,
        precision_at_1=totals[0] / queries,
        precision_at_k=totals[1] / queries,
        recall_at_k=totals[2] / queries,
        hit_rate=totals[3] / queries,
        mrr=totals[4] / queries,
    )


def format_report(evaluation: Evaluation) -> str:
    """Render the evaluation as the text table used in the report."""
    k = evaluation.k
    header = (
        f"{'strategy':<10}{'P@1':>8}{f'P@{k}':>8}{f'R@{k}':>8}"
        f"{f'Hit@{k}':>9}{'MRR':>8}{'queries':>9}"
    )
    lines = [
        f"Corpus: {evaluation.recipes} recipe(s), vocabulary {evaluation.vocabulary} lemma(s), "
        f"k={k}, skipped queries {evaluation.skipped_queries}",
        "",
        header,
    ]
    for name, metrics in (("baseline", evaluation.baseline), ("v1", evaluation.model)):
        lines.append(
            f"{name:<10}{metrics.precision_at_1:>8.3f}{metrics.precision_at_k:>8.3f}"
            f"{metrics.recall_at_k:>8.3f}{metrics.hit_rate:>9.3f}{metrics.mrr:>8.3f}"
            f"{metrics.queries:>9}"
        )
    baseline, model = evaluation.baseline, evaluation.model
    lines.extend(
        [
            "",
            f"v1 - baseline: P@{k} {model.precision_at_k - baseline.precision_at_k:+.3f}, "
            f"R@{k} {model.recall_at_k - baseline.recall_at_k:+.3f}, "
            f"Hit@{k} {model.hit_rate - baseline.hit_rate:+.3f}, "
            f"MRR {model.mrr - baseline.mrr:+.3f}",
        ]
    )
    if evaluation.buckets:
        lines.extend(
            [
                "",
                "by product frequency (recipes that use the hidden product):",
                f"{'bucket':<10}{'queries':>9}{'P@k base':>10}{'P@k v1':>9}{'gain':>8}"
                f"{'MRR base':>10}{'MRR v1':>9}",
            ]
        )
        for bucket in evaluation.buckets:
            lines.append(
                f"{bucket.name:<10}{bucket.queries:>9}"
                f"{bucket.baseline.precision_at_k:>10.3f}{bucket.model.precision_at_k:>9.3f}"
                f"{bucket.precision_gain:>+8.3f}{bucket.baseline.mrr:>10.3f}"
                f"{bucket.model.mrr:>9.3f}"
            )
    lines.append(
        "verdict: OK, v1 is better than the baseline on P@k and MRR"
        if evaluation.improved
        else "verdict: FAIL, v1 is not better than the baseline on P@k and MRR"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Arguments of ``python -m app.ml.evaluate``."""
    parser = argparse.ArgumentParser(
        prog="python -m app.ml.evaluate",
        description="Ranking metrics of the v1 model against the bag-of-lemmas baseline.",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=corpus.DEFAULT_CORPUS,
        help=f"corpus file (default: {corpus.DEFAULT_CORPUS})",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="evaluate on the recipes of DATABASE_URL instead of a file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=corpus.DEFAULT_DATABASE_LIMIT,
        help=f"recipes read from the database (default: {corpus.DEFAULT_DATABASE_LIMIT})",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        help=f"cut-off of the metrics (default: {DEFAULT_K})",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="evaluate this artifact instead of fitting a model on the corpus",
    )
    parser.add_argument(
        "--allow-regression",
        action="store_true",
        help="return 0 even when v1 is not better than the baseline",
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluation from the command line; the exit code reports the verdict."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args(argv)
    settings = Settings.from_env()
    try:
        entries = _entries(arguments, settings)
        model = _model(arguments)
        evaluation = evaluate(entries, k=arguments.k, model=model)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED

    if arguments.json:
        print(json.dumps(_as_json(evaluation), ensure_ascii=False, indent=2))
    else:
        print(format_report(evaluation))
    if evaluation.improved or arguments.allow_regression:
        return EXIT_OK
    print("verdict: FAIL, v1 is not better than the baseline", file=sys.stderr)
    return EXIT_FAILED


def _entries(arguments: argparse.Namespace, settings: Settings) -> list[corpus.RecipeEntry]:
    """Corpus of the run: the database when asked, the file otherwise."""
    if not arguments.from_db:
        return corpus.load_corpus(arguments.sample)
    if not settings.database_url:
        raise ValueError("--from-db needs DATABASE_URL to be set")
    return corpus.from_database(settings.database_url, limit=arguments.limit or None)


def _model(arguments: argparse.Namespace) -> "model_module.TfidfModel | None":
    """Artifact given by ``--model``; ``None`` means "fit on the corpus of this run"."""
    if arguments.model is None:
        return None
    model = model_module.TfidfModel.load(arguments.model)
    if model is None:
        raise ValueError(f"cannot read the artifact {arguments.model}")
    return model


def _as_json(evaluation: Evaluation) -> dict:
    """Serialize the evaluation for ``--json``."""
    return {
        "recipes": evaluation.recipes,
        "vocabulary": evaluation.vocabulary,
        "k": evaluation.k,
        "skipped_queries": evaluation.skipped_queries,
        "baseline": evaluation.baseline.as_dict(),
        "v1": evaluation.model.as_dict(),
        "by_frequency": {
            bucket.name: {
                "queries": bucket.queries,
                f"p@{evaluation.k}": round(bucket.model.precision_at_k, 4),
                "baseline": bucket.baseline.as_dict(),
                "v1": bucket.model.as_dict(),
            }
            for bucket in evaluation.buckets
        },
        "improved": evaluation.improved,
    }


if __name__ == "__main__":
    raise SystemExit(main())
