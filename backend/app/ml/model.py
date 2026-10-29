"""Task 6.0 of sprint 2: the TF-IDF model v1 of the recommendation module.

The stub of ``app/ml`` vectorized an ingredient list as a bag of lemmas: every word got
the weight 1.0, so ``соль``, ``масло`` and ``вода`` pulled the answer as strongly as
``шафран``.  Version 1 fits inverse document frequencies (IDF) on the recipe corpus and
weights every lemma by it: a product that occurs in a few recipes describes a dish, a
product that occurs in half of them does not.

What the model is, and what it is not:

* it is *unsupervised*: nothing but the ingredient lists of the catalogue is needed, so
  it can be retrained on the imported dataset without any user data;
* it is *not* SBERT: ``ml_planning/ml_plan`` names sentence embeddings as the target
  vectorizer, v1 keeps the sparse TF-IDF vector and SBERT stays an ablation on the
  optional ML stack (``EMBEDDINGS_ENABLED``);
* it is *one artifact*: a dictionary of IDF weights in JSON, so a deployment carries the
  trained model as a file and needs no extra dependency.  ``joblib``/``pickle`` are not
  used on purpose: a JSON file is readable, diffable and cannot execute code when it is
  loaded from a volume that somebody else can write.

Usage (from ``backend/``)::

    python -m app.ml.model                                   # fit on the committed sample
    python -m app.ml.model --from-db --limit 150000           # fit on the imported dataset
    python -m app.ml.model --sample data/povarenok --out /tmp/v1.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from ..config import Settings
from . import corpus
from .preprocessing import lemmatize_terms

logger = logging.getLogger(__name__)

ARTIFACT_VERSION = 1
"""Format version of the artifact; a file with another version is ignored."""

DEFAULT_ARTIFACT = Path(__file__).resolve().parent / "artifacts" / "v1.json"
"""Where ``python -m app.ml.model`` writes the model and where the service looks for it."""

EXIT_OK = 0
EXIT_FAILED = 1

_CACHE: dict[str, tuple[tuple[int, int], "TfidfModel"]] = {}
"""Loaded artifacts keyed by path: the service reloads a file only when it changes."""


@dataclass(frozen=True)
class TfidfModel:
    """IDF weights of one corpus: the trained artifact of version 1."""

    idf: Mapping[str, float]
    default_idf: float
    documents: int
    source: str = "sample"
    trained_at: str = ""
    version: int = ARTIFACT_VERSION

    @property
    def vocabulary_size(self) -> int:
        """Number of lemmas the model has seen during training."""
        return len(self.idf)

    def weight(self, lemma: str) -> float:
        """IDF of ``lemma``; an unseen lemma gets ``default_idf`` (the largest weight).

        A product the corpus has never seen is the most specific product there is, so it
        must not be quieter than a common one - that is also what keeps the endpoint
        working for a catalogue imported after the artifact was built.
        """
        return self.idf.get(lemma, self.default_idf)

    def vector(self, text: str) -> dict[str, float]:
        """TF-IDF vector of ``text``: lemma -> ``tf * idf`` with ``tf`` equal to 1.

        ``app.ml.preprocessing.lemmatize_terms`` keeps the first occurrence of a lemma, so
        a product named twice in one list does not double its weight; cosine similarity
        normalizes the length anyway.
        """
        return {lemma: self.weight(lemma) for lemma in lemmatize_terms([text])}

    def as_dict(self) -> dict:
        """Serialize the artifact (sorted keys keep two runs byte-identical)."""
        return {
            "version": self.version,
            "trained_at": self.trained_at,
            "documents": self.documents,
            "source": self.source,
            "default_idf": round(self.default_idf, 6),
            "idf": {lemma: round(weight, 6) for lemma, weight in sorted(self.idf.items())},
        }

    @classmethod
    def from_dict(cls, payload: object) -> "TfidfModel":
        """Rebuild the model from ``as_dict`` output; raises ``ValueError`` on bad input."""
        if not isinstance(payload, Mapping):
            raise ValueError("artifact must be a JSON object")
        version = int(payload["version"])
        if version != ARTIFACT_VERSION:
            raise ValueError(f"unsupported artifact version {version}")
        weights = payload["idf"]
        if not isinstance(weights, Mapping) or not weights:
            raise ValueError("artifact has no IDF weights")
        return cls(
            idf={str(lemma): float(weight) for lemma, weight in weights.items()},
            default_idf=float(payload["default_idf"]),
            documents=int(payload["documents"]),
            source=str(payload.get("source") or "unknown"),
            trained_at=str(payload.get("trained_at") or ""),
            version=version,
        )

    def save(self, path: str | Path) -> Path:
        """Write the artifact atomically: a reader never sees a half-written file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.as_dict(), ensure_ascii=False, separators=(",", ":"))
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=f"{target.name}.")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(temporary, target)
        except OSError:
            Path(temporary).unlink(missing_ok=True)
            raise
        logger.info("Artifact saved: %s (%s lemma(s))", target, self.vocabulary_size)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "TfidfModel | None":
        """Read an artifact; ``None`` when the file is missing or unusable.

        The caller keeps the bag-of-lemmas fallback, so an absent or broken artifact never
        breaks the endpoint (an acceptance criterion of task 6.0).
        """
        target = Path(path)
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.info(
                "No model artifact at %s: the module keeps the bag-of-lemmas fallback", target
            )
            return None
        except (OSError, ValueError):
            logger.warning(
                "Model artifact %s is unreadable, using the fallback", target, exc_info=True
            )
            return None
        try:
            return cls.from_dict(payload)
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "Model artifact %s has an unexpected format, using the fallback",
                target,
                exc_info=True,
            )
            return None


def fit(
    texts: Sequence[str], *, source: str = "sample", trained_at: str | None = None
) -> TfidfModel:
    """Fit IDF weights on ``texts`` (the smooth formula of ``sklearn``'s vectorizer).

    ``idf = ln((1 + N) / (1 + df)) + 1`` keeps every weight positive and never divides by
    zero, while a lemma of one recipe still gets a bigger weight than a lemma of a
    thousand recipes.  ``default_idf`` is the weight of a lemma with ``df = 0``.
    """
    documents = [text for text in texts if text and text.strip()]
    if not documents:
        raise ValueError("the corpus is empty: nothing to fit the model on")
    frequencies: dict[str, int] = {}
    for text in documents:
        for lemma in set(lemmatize_terms([text])):
            frequencies[lemma] = frequencies.get(lemma, 0) + 1
    total = len(documents)
    return TfidfModel(
        idf={lemma: _idf(frequency, total) for lemma, frequency in frequencies.items()},
        default_idf=_idf(0, total),
        documents=total,
        source=source,
        trained_at=trained_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def load_cached(path: str | Path) -> TfidfModel | None:
    """Return the artifact at ``path``, re-reading the file only when it changed.

    The endpoint calls this on every request, so a stat-based cache keeps the JSON parse
    out of the hot path while a retrained artifact is still picked up without a restart.
    """
    target = Path(path)
    try:
        stat = target.stat()
    except OSError:
        return TfidfModel.load(target)
    key = str(target.resolve())
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    model = TfidfModel.load(target)
    if model is None:
        _CACHE.pop(key, None)
    else:
        _CACHE[key] = (stamp, model)
    return model


def model_for_settings(settings: Settings) -> TfidfModel | None:
    """Artifact configured for this installation (``SMART_RECOMMENDATIONS_ARTIFACT``)."""
    path = settings.smart_recommendations_artifact or str(DEFAULT_ARTIFACT)
    return load_cached(path)


def clear_cache() -> None:
    """Forget loaded artifacts (tests, and a manual retrain of a running process)."""
    _CACHE.clear()


def _idf(document_frequency: int, documents: int) -> float:
    """Smooth inverse document frequency of one lemma."""
    return math.log((1 + documents) / (1 + document_frequency)) + 1.0


def build_parser() -> argparse.ArgumentParser:
    """Arguments of ``python -m app.ml.model``."""
    parser = argparse.ArgumentParser(
        prog="python -m app.ml.model",
        description="Fit the v1 TF-IDF model and save it as a JSON artifact.",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=corpus.DEFAULT_CORPUS,
        help=f"dataset file to fit on (default: {corpus.DEFAULT_CORPUS})",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="fit on the recipes of DATABASE_URL instead of a file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=corpus.DEFAULT_DATABASE_LIMIT,
        help=f"recipes read from the database (default: {corpus.DEFAULT_DATABASE_LIMIT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="artifact path (default: SMART_RECOMMENDATIONS_ARTIFACT or app/ml/artifacts/v1.json)",
    )
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Fit the model from the command line; the exit code reports the result."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args(argv)
    settings = Settings.from_env()
    try:
        entries = _entries(arguments, settings)
        model = fit([entry.text for entry in entries], source=_source(arguments))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    target = Path(arguments.out or settings.smart_recommendations_artifact or DEFAULT_ARTIFACT)
    model.save(target)
    summary = {
        "documents": model.documents,
        "vocabulary": model.vocabulary_size,
        "default_idf": round(model.default_idf, 4),
        "source": model.source,
        "artifact": str(target),
    }
    if arguments.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"documents={model.documents} vocabulary={model.vocabulary_size} "
            f"default_idf={summary['default_idf']:.3f} source={model.source}"
        )
        print(f"artifact: {target} ({target.stat().st_size} bytes)")
    return EXIT_OK


def _entries(arguments: argparse.Namespace, settings: Settings) -> list[corpus.RecipeEntry]:
    """Corpus of the run: the database when asked, the file otherwise."""
    if not arguments.from_db:
        return corpus.load_corpus(arguments.sample)
    if not settings.database_url:
        raise ValueError("--from-db needs DATABASE_URL to be set")
    return corpus.from_database(settings.database_url, limit=arguments.limit or None)


def _source(arguments: argparse.Namespace) -> str:
    """Short label of the training corpus, stored inside the artifact."""
    return "database" if arguments.from_db else f"file:{arguments.sample}"


if __name__ == "__main__":
    raise SystemExit(main())
