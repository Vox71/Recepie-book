"""Quality metrics of the allergen filter on the labelled sample (sprint 2, task 6.1).

The sample (``tests/data/allergen_labeled_sample.json``) is a hand-labelled list of
recipes: every entry names the allergen groups a person found in its ingredient list.
The module compares the dictionary of ``app.ml.allergens`` with those labels and reports
precision, recall, F1 and ``violation_rate`` - the share of allergens the filter missed.

The acceptance criterion of the task is ``violation_rate = 0``: a missed allergen is a
health risk, while a false positive only removes one recipe from the answer.  The numbers
of the last run are recorded in ``docs/allergen-filter.md``.

Usage (from ``backend/``)::

    python -m app.ml.allergen_eval
    python -m app.ml.allergen_eval --sample tests/data/allergen_labeled_sample.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from . import allergens

DEFAULT_SAMPLE = Path("tests/data/allergen_labeled_sample.json")
DEFAULT_FAIL_UNDER_F1 = 0.95
DEFAULT_MAX_VIOLATION_RATE = 0.0


@dataclass(frozen=True)
class Metrics:
    """Confusion matrix of one group (or of the whole sample) over recipes."""

    labels: int
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        """Share of the predicted allergens that the labels confirm."""
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else 0.0

    @property
    def recall(self) -> float:
        """Share of the labelled allergens the filter found."""
        found = self.true_positives + self.false_negatives
        return self.true_positives / found if found else 0.0

    @property
    def f1(self) -> float:
        """Harmonic mean of precision and recall."""
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    @property
    def violation_rate(self) -> float:
        """Share of labelled allergens the filter missed (the safety criterion)."""
        return self.false_negatives / self.labels if self.labels else 0.0


@dataclass(frozen=True)
class Evaluation:
    """Result of one run over a labelled sample."""

    recipes: int
    overall: Metrics
    per_group: dict[str, Metrics]
    mismatches: tuple[dict, ...]


def load_sample(path: Path) -> list[dict]:
    """Read and check the labelled sample file."""
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path} must contain a non-empty JSON array of recipes")
    for entry in entries:
        if not isinstance(entry, dict) or "ingredients" not in entry or "allergens" not in entry:
            raise ValueError(f"{path}: every entry needs 'ingredients' and 'allergens'")
        if not isinstance(entry["ingredients"], list) or not isinstance(entry["allergens"], list):
            raise ValueError(f"{path}: 'ingredients' and 'allergens' must be arrays")
    return entries


def evaluate(sample: Sequence[dict], *, groups: Sequence[str] | None = None) -> Evaluation:
    """Compare the dictionary with the labels of ``sample``."""
    query = allergens.resolve_allergies(list(groups) if groups else list(allergens.all_slugs()))
    counters: dict[str, list[int]] = {slug: [0, 0, 0] for slug in allergens.all_slugs()}
    labels = true_positives = false_positives = false_negatives = 0
    mismatches: list[dict] = []
    for entry in sample:
        expected = {str(slug) for slug in entry.get("allergens") or []}
        predicted = set(allergens.matched_allergens(entry.get("ingredients") or [], query))
        if expected != predicted:
            mismatches.append(
                {
                    "name": entry.get("name"),
                    "ingredients": entry.get("ingredients"),
                    "expected": sorted(expected),
                    "predicted": sorted(predicted),
                }
            )
        labels += len(expected)
        for slug in expected | predicted:
            bucket = counters.setdefault(slug, [0, 0, 0])
            if slug in expected and slug in predicted:
                bucket[0] += 1
                true_positives += 1
            elif slug in predicted:
                bucket[1] += 1
                false_positives += 1
            else:
                bucket[2] += 1
                false_negatives += 1
    per_group = {
        slug: Metrics(
            labels=sum(1 for entry in sample if slug in (entry.get("allergens") or [])),
            true_positives=values[0],
            false_positives=values[1],
            false_negatives=values[2],
        )
        for slug, values in counters.items()
        if any(values)
    }
    return Evaluation(
        recipes=len(sample),
        overall=Metrics(
            labels=labels,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
        ),
        per_group=per_group,
        mismatches=tuple(mismatches),
    )


def format_report(evaluation: Evaluation) -> str:
    """Render the evaluation as the text table used in the report."""
    overall = evaluation.overall
    lines = [
        f"Recipes: {evaluation.recipes}, allergen labels: {overall.labels}",
        (
            f"precision={overall.precision:.3f} recall={overall.recall:.3f} "
            f"F1={overall.f1:.3f} violation_rate={overall.violation_rate:.3f}"
        ),
        "",
        f"{'group':<12}{'labels':>7}{'tp':>5}{'fp':>5}{'fn':>5}{'precision':>11}"
        f"{'recall':>8}{'F1':>7}",
    ]
    for slug, metrics in evaluation.per_group.items():
        lines.append(
            f"{slug:<12}{metrics.labels:>7}{metrics.true_positives:>5}"
            f"{metrics.false_positives:>5}{metrics.false_negatives:>5}"
            f"{metrics.precision:>11.3f}{metrics.recall:>8.3f}{metrics.f1:>7.3f}"
        )
    if evaluation.mismatches:
        lines.extend(["", "Mismatches:"])
        for mismatch in evaluation.mismatches:
            lines.append(
                f"  {mismatch['name']!r}: expected {mismatch['expected']}, "
                f"got {mismatch['predicted']}"
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluation from the command line; the exit code reports the verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument(
        "--fail-under-f1",
        type=float,
        default=DEFAULT_FAIL_UNDER_F1,
        help="return a non-zero code when F1 is below this value",
    )
    parser.add_argument(
        "--max-violation-rate",
        type=float,
        default=DEFAULT_MAX_VIOLATION_RATE,
        help="return a non-zero code when more allergens than this share are missed",
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    arguments = parser.parse_args(argv)

    evaluation = evaluate(load_sample(arguments.sample))
    overall = evaluation.overall
    if arguments.json:
        print(json.dumps(_as_json(evaluation), ensure_ascii=False, indent=2))
    else:
        print(format_report(evaluation))

    if overall.violation_rate > arguments.max_violation_rate:
        print("verdict: FAIL, missed allergens", file=sys.stderr)
        return 1
    if overall.f1 < arguments.fail_under_f1:
        print("verdict: FAIL, F1 is below the threshold", file=sys.stderr)
        return 1
    print("verdict: OK")
    return 0


def _as_json(evaluation: Evaluation) -> dict:
    """Serialize the evaluation for ``--json``."""
    overall = evaluation.overall
    return {
        "recipes": evaluation.recipes,
        "labels": overall.labels,
        "precision": round(overall.precision, 4),
        "recall": round(overall.recall, 4),
        "f1": round(overall.f1, 4),
        "violation_rate": round(overall.violation_rate, 4),
        "per_group": {
            slug: {
                "labels": metrics.labels,
                "precision": round(metrics.precision, 4),
                "recall": round(metrics.recall, 4),
                "f1": round(metrics.f1, 4),
            }
            for slug, metrics in evaluation.per_group.items()
        },
        "mismatches": list(evaluation.mismatches),
    }


if __name__ == "__main__":
    raise SystemExit(main())
