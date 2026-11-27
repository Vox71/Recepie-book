"""Tests of the honest ranking experiment: normalization, split and hybrid scorer."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ml import bm25, corpus, experiment, normalization

SAMPLE = Path(__file__).parent / "data" / "recommendation_sample.json"


def test_canonical_ingredients_merge_synonyms_and_drop_pantry():
    assert normalization.canonical_ingredients(
        ["Помидоры", "Томаты", "Куриное филе", "Соль", "Вода", "Картошка"]
    ) == ("томат", "курица", "фил", "картофель")


def test_bm25_prefers_a_document_with_the_query_term():
    index = bm25.BM25Index(
        [
            ("milk", "sugar", "rice"),
            ("tomato", "cucumber", "oil"),
            ("milk", "oats", "sugar", "honey"),
        ]
    )

    scores = index.scores(("milk", "sugar"))

    assert scores[0] > 0
    assert scores[2] > 0
    assert 1 not in scores
    assert scores[0] > scores[2]


def test_split_is_deterministic_and_has_no_overlap():
    entries = [corpus.RecipeEntry(f"r{index}", ("milk", f"item{index}")) for index in range(20)]
    first = experiment.split_indices(len(entries), seed=7)
    second = experiment.split_indices(len(entries), seed=7)

    assert first == second
    train, validation, test = first
    assert set(train).isdisjoint(validation)
    assert set(train).isdisjoint(test)
    assert set(validation).isdisjoint(test)
    assert len(train) + len(validation) + len(test) == len(entries)


def test_experiment_reports_validation_and_test_metrics_on_the_sample():
    entries = corpus.load_corpus(SAMPLE)
    result = experiment.run_experiment(entries, k=5, seed=42)

    assert result.recipes == len(entries)
    assert result.train_size + result.validation_size + result.test_size == result.recipes
    assert set(result.validation) == {"bm25", "cooccurrence", "hybrid"}
    assert set(result.test) == {"bm25", "cooccurrence", "hybrid"}
    assert result.validation["hybrid"].queries > 0
    assert result.test["hybrid"].queries > 0
    assert 0 <= result.test["hybrid"].precision_at_k <= 1
    assert 0 <= result.test["hybrid"].mrr <= 1
    with pytest.raises(ValueError):
        experiment.run_experiment([], k=5)
