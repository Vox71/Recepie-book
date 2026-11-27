"""Canonical ingredient terms for the ranking experiments.

The production TF-IDF model deliberately uses the rough lemmatizer of
``app.ml.preprocessing``.  This module adds a small product dictionary on top of it:
synonyms become one term and pantry products are removed, because "соль", "вода" and
"масло" occur in almost every recipe and only add noise to a ranking query.

The dictionary is intentionally small and explicit.  It is not a hidden model: every
mapping is visible, testable and can be extended without retraining an artifact.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .preprocessing import lemmatize_terms

# Canonical form -> variants after lemmatization.  Only unambiguous pairs are here:
# "куриный" and "курица" are merged, but "молоко" and "кокосовое молоко" are not.
SYNONYMS: dict[str, str] = {
    "помидор": "томат",
    "томат": "томат",
    "картошк": "картофель",
    "картофел": "картофель",
    "картофель": "картофель",
    "морковк": "морковь",
    "морковь": "морковь",
    "свекл": "свекла",
    "свекла": "свекла",
    "кабачк": "кабачок",
    "кабачок": "кабачок",
    "баклажан": "баклажан",
    "перц": "перец",
    "перец": "перец",
    "куриц": "курица",
    "курин": "курица",
    "курица": "курица",
    "рыб": "рыба",
    "рыба": "рыба",
    "рыбн": "рыба",
    "мяс": "мясо",
    "мясо": "мясо",
    "мясн": "мясо",
    "молок": "молоко",
    "молочн": "молоко",
    "молоко": "молоко",
    "сыр": "сыр",
    "сырн": "сыр",
    "сметан": "сметана",
    "сметана": "сметана",
    "творог": "творог",
    "творожн": "творог",
    "яйц": "яйцо",
    "яйцо": "яйцо",
    "яичн": "яйцо",
    "лук": "лук",
    "луков": "лук",
    "чеснок": "чеснок",
    "чесночн": "чеснок",
}

# Products that are almost always "already at home" and must not decide a recipe rank.
PANTRY = frozenset(
    {
        "соль",
        "вод",
        "вода",
        "сахар",
        "масл",
        "масло",
        "перец",
        "специи",
        "зелень",
        "сода",
        "уксус",
    }
)


def canonical_term(term: str) -> str:
    """Return the canonical lemma of one token/term."""
    lemmas = lemmatize_terms([term])
    if not lemmas:
        return ""
    lemma = lemmas[0]
    return SYNONYMS.get(lemma, lemma)


def canonical_ingredients(
    ingredients: Iterable[str], *, drop_pantry: bool = True
) -> tuple[str, ...]:
    """Canonical, deduplicated ingredient terms of one recipe.

    Multi-word names are tokenized by the same lemmatizer as the production model.  The
    order of first appearance is kept, so a caller can still inspect the source order.
    """
    result: list[str] = []
    seen: set[str] = set()
    for ingredient in ingredients:
        for lemma in lemmatize_terms([ingredient]):
            term = SYNONYMS.get(lemma, lemma)
            if not term or (drop_pantry and term in PANTRY):
                continue
            if term not in seen:
                seen.add(term)
                result.append(term)
    return tuple(result)


def canonical_query(ingredients: Sequence[str]) -> tuple[str, ...]:
    """Canonical terms of a query (the same dictionary, pantry removed)."""
    return canonical_ingredients(ingredients, drop_pantry=True)
