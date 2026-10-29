"""Tests of the v1 recommendation model (sprint 2, tasks 6.0 and 6.2).

The file covers the trained artifact and its metrics without a database: the IDF
weights, save/load of the JSON file, the graceful fallback when the file is missing or
broken, the engine switching to the model, the leave-one-ingredient-out protocol and the
CLI of both commands.  The last case checks the database source of the corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.ml import corpus, engine, evaluate, model as model_module, vectorizer

SAMPLE = Path(__file__).parent / "data" / "recommendation_sample.json"

RICE_SIDE = {"id": 1, "recipe_name": "rice side", "ingredients": "rice, salt"}
FRIED_RICE = {"id": 2, "recipe_name": "fried rice", "ingredients": "rice, salt, oil"}
SAFFRON_DESSERT = {"id": 3, "recipe_name": "saffron dessert", "ingredients": "saffron, sugar"}
SMALL_CORPUS = (RICE_SIDE, FRIED_RICE, SAFFRON_DESSERT)


def _fit(texts: list[str], **kwargs) -> model_module.TfidfModel:
    """Fit the model with a fixed training timestamp (the tests compare artifacts)."""
    return model_module.fit(texts, trained_at="2026-10-29T00:00:00+00:00", **kwargs)


def test_fit_weights_rare_lemmas_above_common_ones():
    """Task 6.0: IDF grows as a lemma gets rarer, and an unseen lemma gets the max."""
    model = _fit(["milk rice salt", "milk salt", "milk sugar", "rice salt"])
    assert model.documents == 4
    assert model.vocabulary_size == 4
    # salt occurs in three recipes, sugar in one, so sugar describes a dish better.
    assert model.weight("sugar") > model.weight("rice") > model.weight("milk")
    assert model.default_idf > max(model.idf.values())
    assert model.weight("pepper") == pytest.approx(model.default_idf)
    # A product named twice weighs the same as a product named once.
    assert model.vector("milk, milk, sugar") == model.vector("milk, sugar")
    with pytest.raises(ValueError):
        model_module.fit(["", "   "])


def test_artifact_round_trip_and_the_stat_cache(tmp_path):
    """Task 6.0: the model is a JSON file, it survives a round trip and is re-read once."""
    model = _fit(["milk rice salt", "milk sugar"], source="file:tests")
    path = model.save(tmp_path / "nested" / "v1.json")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == model_module.ARTIFACT_VERSION
    assert payload["documents"] == 2
    assert payload["source"] == "file:tests"

    loaded = model_module.TfidfModel.load(path)
    assert loaded is not None
    assert loaded.idf == pytest.approx(model.idf)
    assert loaded.default_idf == pytest.approx(model.default_idf)
    assert loaded.trained_at == model.trained_at

    model_module.clear_cache()
    first = model_module.load_cached(path)
    assert model_module.load_cached(path) is first  # the stat cache returned the same object
    # A retrained artifact is picked up without a restart.
    _fit(["milk rice salt", "milk sugar"], source="retrained").save(path)
    second = model_module.load_cached(path)
    assert second is not None and second.source == "retrained"


def test_missing_or_broken_artifact_keeps_the_bag_of_lemmas_fallback(tmp_path):
    """Acceptance criterion: no artifact (or a broken one) must not break the service."""
    missing = tmp_path / "absent.json"
    assert model_module.TfidfModel.load(missing) is None
    assert model_module.load_cached(missing) is None
    assert (
        model_module.model_for_settings(Settings({"SMART_RECOMMENDATIONS_ARTIFACT": str(missing)}))
        is None
    )

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert model_module.TfidfModel.load(broken) is None

    wrong_version = tmp_path / "old.json"
    wrong_version.write_text(json.dumps({"version": 99, "idf": {"milk": 1.0}}), encoding="utf-8")
    assert model_module.TfidfModel.load(wrong_version) is None

    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"version": 1, "idf": {}, "default_idf": 1.0}), encoding="utf-8")
    assert model_module.TfidfModel.load(empty) is None


@pytest.mark.parametrize("use_model", [False, True])
def test_engine_ranks_with_the_model_when_the_artifact_exists(tmp_path, use_model):
    """Task 6.0: with the artifact the ranking is IDF-based, without it the old one."""
    texts = [row["ingredients"] for row in SMALL_CORPUS]
    path = _fit(texts).save(tmp_path / "v1.json")
    settings = Settings({"SMART_RECOMMENDATIONS_ARTIFACT": str(path)})
    model = model_module.model_for_settings(settings) if use_model else None

    outcome = engine.recommend_safe_recipes(
        favourites=[],
        fridge_products=["saffron", "salt"],
        allergies=[],
        recipes=list(SMALL_CORPUS),
        limit=5,
        neighbours=10,
        settings=settings,
        model=model,
    )
    names = [entry["recipe"]["recipe_name"] for entry in outcome["recipes"]]
    if use_model:
        assert outcome["stats"]["vectorizer"] == vectorizer.TFIDF_BACKEND
        assert outcome["stats"]["model_documents"] == 3
        # saffron is rarer than salt, so the dessert wins over the rice side dish.
        assert names[0] == "saffron dessert"
    else:
        assert outcome["stats"]["vectorizer"] == vectorizer.SPARSE_BACKEND
        assert outcome["stats"]["model_documents"] is None
        assert names[0] == "rice side"


def test_leave_one_ingredient_out_protocol_counts_every_metric():
    """Task 6.2: the metrics follow their definitions on a corpus with a known answer.

    The first two recipes are identical, so the held-out product of one is always inside
    the other one and every such query hits at the first position; the third recipe shares
    no product with them, so its two queries are skipped (nothing relevant to find).  With
    two identical recipes the strategies tie, hence ``improved`` is false.
    """
    entries = [
        corpus.RecipeEntry("rice with saffron", ("rice", "saffron")),
        corpus.RecipeEntry("rice with saffron again", ("rice", "saffron")),
        corpus.RecipeEntry("oil with salt", ("oil", "salt")),
    ]
    result = evaluate.evaluate(entries, k=5)
    assert result.baseline.queries == 4
    assert result.skipped_queries == 2
    for metrics in (result.baseline, result.model):
        assert metrics.precision_at_1 == pytest.approx(1.0)
        assert metrics.precision_at_k == pytest.approx(4 / 4 / 5)
        assert metrics.recall_at_k == pytest.approx(1.0)
        assert metrics.hit_rate == pytest.approx(1.0)
        assert metrics.mrr == pytest.approx(1.0)
    assert [(bucket.name, bucket.queries) for bucket in result.buckets] == [("rare", 4)]
    assert result.improved is False


def test_v1_is_better_than_the_baseline_on_the_committed_corpus():
    """The acceptance criterion of task 6.0, measured on the corpus of the repository."""
    entries = corpus.load_corpus(SAMPLE)
    assert len(entries) >= 100
    result = evaluate.evaluate(entries, k=5)
    assert result.recipes == len(entries)
    assert result.vocabulary > 100
    assert result.baseline.queries > 500
    assert result.model.precision_at_k > result.baseline.precision_at_k
    assert result.model.mrr > result.baseline.mrr
    assert result.model.hit_rate >= result.baseline.hit_rate
    assert result.improved is True


def test_cli_prints_the_numbers_and_gates_a_regression(tmp_path, capsys):
    """Both commands are runnable and the evaluator reports a regression by exit code."""
    artifact = tmp_path / "v1.json"
    assert model_module.main(["--sample", str(SAMPLE), "--out", str(artifact), "--json"]) == 0
    assert artifact.exists()
    assert json.loads(artifact.read_text(encoding="utf-8"))["documents"] >= 100
    capsys.readouterr()

    assert evaluate.main(["--sample", str(SAMPLE), "--model", str(artifact)]) == 0
    report = capsys.readouterr().out
    assert "baseline" in report and "v1" in report
    assert "P@5" in report and "MRR" in report
    assert "verdict: OK" in report

    tiny = tmp_path / "tiny.json"
    tiny.write_text(
        json.dumps(
            [
                {"name": "rice with saffron", "ingredients": ["rice", "saffron"]},
                {"name": "rice with salt", "ingredients": ["rice", "salt"]},
                {"name": "saffron with salt", "ingredients": ["saffron", "salt"]},
            ]
        ),
        encoding="utf-8",
    )
    assert evaluate.main(["--sample", str(tiny), "--allow-regression"]) == 0
    assert evaluate.main(["--sample", str(tiny)]) == 1
    assert "FAIL" in capsys.readouterr().err
    assert evaluate.main(["--sample", str(tmp_path / "absent.json")]) == 1


def test_the_corpus_is_read_from_the_database(db, database_url):
    """Task 6.0: the trainer takes ``recipe_ingredients`` first and the text second."""
    db.execute(
        "INSERT INTO recipes (recipe_name, ingredients) VALUES (%s, %s)",
        ("Cheese plate", "cheese — 200 г, grapes — 100 г"),
    )
    db.execute(
        "INSERT INTO recipes (recipe_name, ingredients) VALUES (%s, %s)",
        ("Empty bowl", "ингредиенты не указаны"),
    )
    first, second = [int(row["id"]) for row in db.fetch_all("SELECT id FROM recipes ORDER BY id")]
    db.execute(
        """
        INSERT INTO recipe_ingredients (recipe_id, ingredient_name, quantity_text, sort_order)
        VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
        """,
        (first, "cheese", "200 г", 1, first, "grapes", "100 г", 2),
    )

    entries = corpus.from_database(database_url)
    assert entries == [corpus.RecipeEntry("Cheese plate", ("cheese", "grapes"))]
    trained = model_module.fit([entry.text for entry in entries])
    assert trained.documents == 1
    assert trained.weight("cheese") == pytest.approx(1.0)
    assert trained.weight("pepper") == pytest.approx(trained.default_idf)
    # The fallback path: no rows in recipe_ingredients, the text column is parsed.
    fallback = corpus.from_rows(
        [{"id": second, "recipe_name": "Empty bowl", "ingredients": "cheese: 200 г"}]
    )
    assert fallback == [corpus.RecipeEntry("Empty bowl", ("cheese",))]
