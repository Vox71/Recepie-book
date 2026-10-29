"""Allergen dictionary and the safety filter (sprint 2, task 6.1).

The unit cases need no database: the dictionary and the metrics script are pure
functions.  The two database cases prove the rule of the task - the filter reads
``recipe_ingredients`` and only falls back to the ``recipes.ingredients`` text.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.ml import allergen_eval, allergens
from app.models import favorites as favorites_model
from app.services import allergen_service

SAMPLE_PATH = Path(__file__).resolve().parent / "data" / "allergen_labeled_sample.json"
TOMORROW = date.today() + timedelta(days=1)


def _query(*allergies: str) -> allergens.AllergyQuery:
    return allergens.resolve_allergies(list(allergies))


FULL_QUERY = allergens.resolve_allergies(list(allergens.all_slugs()))


def test_every_group_and_alias_points_at_a_known_group():
    """The dictionary is consistent: no alias into nowhere, no empty group."""
    assert allergens.all_slugs() == tuple(allergens.ALLERGEN_GROUPS)
    assert len(set(allergens.all_slugs())) == len(allergens.all_slugs())
    for slug, group in allergens.ALLERGEN_GROUPS.items():
        assert group.slug == slug
        assert group.title
        assert group.terms, slug
    for alias, slug in allergens.ALLERGEN_ALIASES.items():
        assert slug in allergens.ALLERGEN_GROUPS, alias
        assert allergens.resolve_allergies([alias]).groups == (slug,), alias


def test_allergy_terms_resolve_into_groups_or_stay_plain_terms():
    """A menu term becomes a group; an unusual allergy never disappears."""
    assert _query("молочные продукты") == allergens.AllergyQuery(groups=("milk",))
    assert _query("КРЕВЕТКИ") == allergens.AllergyQuery(groups=("seafood",))
    assert _query("gluten") == allergens.AllergyQuery(groups=("gluten",))
    # Coconut is not a nut and names no group, so it stays a plain lemma term.
    assert _query("кокос") == allergens.AllergyQuery(terms=("кокос",))
    assert _query("киви") == allergens.AllergyQuery(terms=("киви",))
    assert _query("", "   ") == allergens.AllergyQuery()
    assert not allergens.AllergyQuery()


def test_repeated_allergy_terms_resolve_once():
    """A group and its alias, or the same unknown term twice, are not duplicated."""
    assert _query("молочные продукты", "молоко", "КРЕВЕТКИ", "seafood").groups == (
        "milk",
        "seafood",
    )
    assert _query("киви", "киви").terms == ("киви",)


def test_a_stop_word_allergy_stays_a_plain_term():
    """``без`` has no lemma: it cannot become a group and must not silently vanish."""
    assert _query("без") == allergens.AllergyQuery(terms=("без",))
    assert allergens.matched_allergens(["молоко"], _query("без")) == []


def test_matching_ignores_an_empty_or_punctuation_only_ingredient():
    """A nameless ingredient row neither matches nor breaks the filter."""
    milk = _query("молоко")
    assert allergens.matched_allergens([], milk) == []
    assert allergens.matched_allergens(["   ", "!!!"], milk) == []
    assert allergens.matched_allergens(["молоко"], allergens.AllergyQuery()) == []
    assert allergens.matched_allergens(["!!!", "молоко"], milk) == ["milk"]


def test_is_safe_answers_the_opposite_of_matched_allergens():
    """``is_safe`` is the boolean form of the filter that the module exposes."""
    milk = _query("молоко")
    assert allergens.is_safe(["кокосовое молоко"], milk) is True
    assert allergens.is_safe(["молоко"], milk) is False
    assert allergens.is_safe([], allergens.AllergyQuery()) is True


def test_a_dictionary_term_without_lemmas_is_skipped(monkeypatch):
    """Defensive: a term of the dictionary made of stop words does not break matching.

    No group of the real dictionary has such a term, so the case uses a synthetic one:
    it is the only way to prove that the guard of ``_term_lemmas`` works and that the
    remaining terms of the group still match.
    """
    group = allergens.AllergenGroup(slug="test_stop_word", title="Тест", terms=("без", "молоко"))
    monkeypatch.setitem(allergens.ALLERGEN_GROUPS, group.slug, group)
    allergens._term_lemmas.cache_clear()
    try:
        assert len(allergens._term_lemmas(group.slug)) == 1
        assert allergens._group_in("молоко", group.slug) is True
        assert allergens._group_in("без", group.slug) is False
    finally:
        allergens._term_lemmas.cache_clear()


PRODUCT_CASES = (
    ("Молоко 3,2%", {"milk"}),
    ("Сливки 10%", {"milk"}),
    ("Творог", {"milk"}),
    ("Масло сливочное", {"milk"}),
    ("Масло растительное", set()),
    ("Яйцо куриное", {"eggs"}),
    ("Яичный белок", {"eggs"}),
    ("Желток", {"eggs"}),
    ("Мука пшеничная", {"gluten"}),
    ("Хлеб ржаной", {"gluten"}),
    ("Макароны", {"gluten"}),
    ("Овсяные хлопья", {"gluten"}),
    # Soy sauce is brewed with wheat, so the ingredient carries both groups.
    ("Соевый соус", {"gluten", "soy"}),
    ("Тофу", {"soy"}),
    ("Арахис", {"peanut"}),
    ("Грецкий орех", {"nuts"}),
    ("Миндальное молоко", {"nuts"}),
    ("Миндальная мука", {"nuts"}),
    ("Треска", {"fish"}),
    ("Икра красная", {"fish"}),
    ("Креветки", {"seafood"}),
    ("Морской коктейль", {"seafood"}),
    ("Кунжут", {"sesame"}),
    ("Горчица", {"mustard"}),
    ("Сельдерей", {"celery"}),
    ("Сульфиты", {"sulphites"}),
    ("Люпиновая мука", {"lupin"}),
    ("Peanut butter", {"peanut"}),
    ("Soy sauce", {"soy", "gluten"}),
    ("Whole wheat bread", {"gluten"}),
    ("Butter", {"milk"}),
)

LOOKALIKE_CASES = (
    "Кокосовая стружка",
    "Кокосовое молоко",
    "Кокосовое масло",
    "Гречка",
    "Гречневая мука",
    "Рисовая мука",
    "Рисовая лапша",
    "Кукурузная мука",
    "Мускатный орех",
    "Картофель сырой",
    "Печень говяжья",
    "Икра кабачковая",
    "Томатная паста",
    "Хлеб безглютеновый",
    "Соевый белок",
    "Растительное масло",
    "Люпиновая мука",
    "Peanut butter",
    "Coconut milk",
    "Buckwheat flour",
    "Rice noodles",
    "Eggplant",
    "Nutmeg",
)


def test_matching_finds_word_forms_synonyms_and_phrases():
    """Every product of a group is recognised in any word form."""
    for ingredient, expected in PRODUCT_CASES:
        matched = set(allergens.matched_allergens([ingredient], FULL_QUERY))
        assert matched == expected, ingredient


def test_lookalikes_do_not_trigger_unrelated_allergens():
    """Coconut, buckwheat and the other look-alikes are not milk, gluten or nuts."""
    query = _query("молоко", "глютен", "орехи", "яйца")
    for ingredient in LOOKALIKE_CASES:
        assert allergens.matched_allergens([ingredient], query) == [], ingredient


def test_custom_allergy_term_is_matched_by_lemma():
    """An allergy outside the dictionary still filters the recipes."""
    query = _query("киви")
    assert allergens.matched_allergens(["Киви свежее", "Сахар"], query) == ["киви"]
    assert allergens.matched_allergens(["Яблоко", "Сахар"], query) == []


def test_labelled_sample_has_no_missed_allergens():
    """The acceptance criterion of the task: violation_rate = 0 on the sample."""
    evaluation = allergen_eval.evaluate(allergen_eval.load_sample(SAMPLE_PATH))
    assert evaluation.recipes >= 200
    assert evaluation.overall.labels > 200
    assert evaluation.overall.violation_rate == 0
    assert evaluation.overall.f1 >= 0.95
    assert evaluation.mismatches == ()
    assert set(evaluation.per_group) == set(allergens.all_slugs())


def test_metrics_count_a_missed_allergen():
    """A missed allergen is visible in both the metric and the violation rate."""
    sample = [
        {"name": "Курица", "ingredients": ["Куриная грудка"], "allergens": ["milk"]},
        {"name": "Молоко", "ingredients": ["Молоко"], "allergens": ["milk"]},
    ]
    evaluation = allergen_eval.evaluate(sample)
    assert evaluation.overall.true_positives == 1
    assert evaluation.overall.false_negatives == 1
    assert evaluation.overall.violation_rate == 0.5
    assert evaluation.overall.recall == 0.5
    assert [mismatch["name"] for mismatch in evaluation.mismatches] == ["Курица"]


def _insert_recipe(db, name: str, ingredients: str, ingredient_rows: list[str]) -> int:
    """Insert a recipe and its ``recipe_ingredients`` rows, returning its id."""
    row = db.fetch_one(
        "INSERT INTO recipes (recipe_name, ingredients) VALUES (%s, %s) RETURNING id",
        (name, ingredients),
    )
    recipe_id = int(row["id"])
    for order, ingredient in enumerate(ingredient_rows):
        db.execute(
            "INSERT INTO recipe_ingredients (recipe_id, ingredient_name, sort_order) "
            "VALUES (%s, %s, %s)",
            (recipe_id, ingredient, order),
        )
    return recipe_id


def test_ingredient_names_falls_back_to_the_text_when_a_row_has_no_id():
    """A recipe without an id (not from the database) is filtered by its text."""
    assert allergen_service.ingredient_names({"id": None, "ingredients": "молоко, соль"}) == [
        "молоко, соль"
    ]
    assert allergen_service.ingredient_names({"id": 7, "ingredients": "молоко"}, {7: ["соль"]}) == [
        "соль"
    ]
    assert allergen_service.ingredient_names({"id": 7, "ingredients": "молоко"}, {}) == ["молоко"]


def test_the_filter_reads_recipe_ingredients_instead_of_the_text(db):
    """recipe_ingredients decides; the text is only a fallback for rows without them."""
    # The text hides the milk, the normalized rows expose it.
    hidden = _insert_recipe(db, "Хитрый суп", "рис, вода", ["Рис", "Молоко"])
    # The text mentions milk, but the normalized rows make it coconut milk.
    lookalike = _insert_recipe(db, "Кокосовый суп", "молоко, вода", ["Кокосовое молоко", "Вода"])
    recipes = [
        {"id": hidden, "ingredients": "рис, вода"},
        {"id": lookalike, "ingredients": "молоко, вода"},
    ]
    safe, rejected = allergen_service.filter_safe_recipes(db, recipes, ["молоко"])
    assert rejected == 1
    assert [row["id"] for row in safe] == [lookalike]

    # A recipe without rows (created through POST /recipes) falls back to the text.
    manual = _insert_recipe(db, "Ручной суп", "молоко, вода", [])
    row = {"id": manual, "ingredients": "молоко, вода"}
    assert allergen_service.filter_safe_recipes(db, [row], ["молоко"]) == ([], 1)
    # Without an allergy profile nothing is rejected, not even a suspicious recipe.
    assert allergen_service.filter_safe_recipes(db, [row], []) == ([row], 0)


def test_recommendations_exclude_a_recipe_hidden_by_its_normalized_ingredients(
    db_client, db, register_user, add_fridge_items
):
    """The baseline endpoint filters by recipe_ingredients, not by the text."""
    user_id, token = register_user()
    assert (
        db_client.post(
            "/user_preferences", json={"user_id": user_id, "allergies": ["молоко"]}
        ).status_code
        == 200
    )
    safe_id = _insert_recipe(db, "Овощной суп", "морковь, вода", ["Морковь", "Вода"])
    _insert_recipe(db, "Молочный суп", "молоко, вода", ["Молоко", "Вода"])
    add_fridge_items(user_id, "вода", TOMORROW)

    response = db_client.get("/recommend_recipes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    recipes = response.get_json()["recipes"]
    assert [recipe["id"] for recipe in recipes] == [safe_id]
    assert [recipe["name"] for recipe in recipes] == ["Овощной суп"]


def test_smart_recommendations_filter_by_the_normalized_ingredients(
    db_app_factory, db_client, db, register_user, add_fridge_items
):
    """The stub pipeline passes the ingredient rows of recipe_ingredients to the filter."""
    smart_client = db_app_factory(SMART_RECOMMENDATIONS_ENABLED="true").test_client()
    user_id, token = register_user()
    assert (
        db_client.post(
            "/user_preferences", json={"user_id": user_id, "allergies": ["молоко"]}
        ).status_code
        == 200
    )
    safe_id = _insert_recipe(db, "Овощной суп", "морковь, вода", ["Морковь", "Вода"])
    _insert_recipe(db, "Молочный суп", "молоко, вода", ["Молоко", "Вода"])
    add_fridge_items(user_id, "вода", TOMORROW)
    assert favorites_model.add_favorite(db, user_id, safe_id) is True

    response = smart_client.get("/recommend_recipes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.get_json()
    assert [recipe["name"] for recipe in body["recipes"]] == ["Овощной суп"]
    assert "1 rejected by allergy" in body["message"]
