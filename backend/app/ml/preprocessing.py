"""Component 1 of the stub module: preprocessing of the recipe texts.

``ml_planning/ml_plan`` asks for "нормализация рецептов, удаление стоп-слов,
лемматизация".  Normalization and stop words are exact, the lemmatizer is a *naive*
suffix table (one ending per token) instead of ``pymorphy2``: the stub must not add a
dependency, while the property the module needs is preserved - the same product in
different forms has to produce the same lemma (``яйца``/``яйцо``, ``peanuts``/``peanut``).
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

WORD_PATTERN = re.compile(r"[a-zа-я0-9]+")
CYRILLIC_PATTERN = re.compile(r"^[а-я]")

STOP_WORDS = frozenset(
    {
        "а",
        "без",
        "в",
        "во",
        "для",
        "до",
        "если",
        "есть",
        "же",
        "из",
        "или",
        "к",
        "как",
        "на",
        "не",
        "но",
        "о",
        "от",
        "по",
        "с",
        "со",
        "так",
        "у",
        "что",
        "это",
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "or",
        "the",
        "to",
        "with",
    }
)

# Longest endings first: exactly one of them is stripped from every token, so the
# number of forms per product stays small.  ``й``/``ь`` endings are not stripped:
# removing them would merge different words (``чай`` -> ``ча``).
CYRILLIC_SUFFIXES = (
    "ами",
    "ями",
    "ого",
    "ему",
    "ыми",
    "ими",
    "ов",
    "ев",
    "ах",
    "ях",
    "ам",
    "ям",
    "ая",
    "ое",
    "ые",
    "ой",
    "ий",
    "ый",
    "ы",
    "и",
    "а",
    "я",
    "о",
    "е",
    "у",
    "ю",
)
LATIN_SUFFIXES = ("ies", "es", "s")
MIN_LEMMA_LENGTH = 3


def normalize_text(value: str) -> str:
    """Lower-case ``value``, replace ``ё`` with ``е`` and drop punctuation.

    ``"МолОко, ЯЙЦА!"`` becomes ``"молоко яйца"``.
    """
    lowered = (value or "").lower().replace("ё", "е")
    return " ".join(WORD_PATTERN.findall(lowered))


def tokenize(value: str) -> list[str]:
    """Split ``value`` into tokens: normalization plus removal of the stop words."""
    return [token for token in normalize_text(value).split() if token not in STOP_WORDS]


def lemmatize(token: str) -> str:
    """Reduce a single token to a rough base form (one suffix is stripped).

    Tokens shorter than ``MIN_LEMMA_LENGTH`` and tokens without a known ending are
    returned unchanged.
    """
    if len(token) <= MIN_LEMMA_LENGTH:
        return token
    suffixes = CYRILLIC_SUFFIXES if CYRILLIC_PATTERN.match(token) else LATIN_SUFFIXES
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) - len(suffix) >= MIN_LEMMA_LENGTH:
            return token[: -len(suffix)]
    return token


def lemmatize_terms(terms: Iterable[str]) -> list[str]:
    """Tokenize, drop stop words and lemmatize every term, keeping the first occurrence.

    ``["Milk, sugar, rice"]`` becomes ``["milk", "sugar", "rice"]``.
    """
    lemmas: list[str] = []
    for term in terms:
        for token in tokenize(term):
            lemma = lemmatize(token)
            if lemma not in lemmas:
                lemmas.append(lemma)
    return lemmas


def mark_allergens(ingredients: str, allergies: Sequence[str]) -> list[str]:
    """Return the allergies of ``allergies`` that occur in ``ingredients``.

    The comparison runs over lemmas, so ``peanuts`` in a recipe is found by the allergy
    ``peanut``; an allergy of several words (``peanut butter``) matches only when the
    recipe mentions all of them.
    """
    if not allergies:
        return []
    ingredient_lemmas = set(lemmatize_terms([ingredients]))
    if not ingredient_lemmas:
        return []
    matched: list[str] = []
    for allergy in allergies:
        parts = lemmatize_terms([allergy])
        if parts and all(part in ingredient_lemmas for part in parts):
            matched.append(allergy)
    return matched
