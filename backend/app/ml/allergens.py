"""Allergen dictionary and the safety filter of the recommendation module.

Sprint 2, task 6.1 (``docs/sprint-2-plan.md``): the module decides whether a recipe is
safe for a user with allergies.  The rules that make the decision trustworthy:

* the source of truth is ``recipe_ingredients`` (one row per ingredient, filled by the
  povarenok importer), not the flattened ``recipes.ingredients`` text; the text is only a
  fallback for recipes the parser has not seen (``allergen_service``);
* matching runs over lemmas (``app.ml.preprocessing``), so ``яйца``/``яйцо`` and
  ``peanuts``/``peanut`` are the same product;
* a group lists the products themselves (``молоко``, ``сливки``, ``творог``) instead of
  one catch-all word, and look-alikes are excluded explicitly:

  - ``blockers`` - a phrase that turns the product into a safe substitute: coconut milk
    (``кокосовое молоко``) is not milk, buckwheat flour (``гречневая мука``) is not gluten;
  - ``exceptions`` - homonyms that must never trigger the group: ``сырой`` (raw) is not
    ``сыр`` (cheese), ``печень`` (liver) is not ``печенье`` (biscuit) - the naive
    lemmatizer of the stub reduces both pairs to one lemma, so the raw tokens decide.

The dictionary lives in code, not in a database table: a new synonym needs a code review
instead of a migration (``docs/db_schema.md``, "чего в схеме нет").

A user allergy term is first mapped onto a group (``молочные продукты`` -> ``milk``).  A
term that names no group stays a plain term and is matched by lemma, so an unusual
allergy (``киви``) still filters recipes and never silently disappears.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from . import preprocessing


@dataclass(frozen=True)
class AllergenGroup:
    """One allergen group: its name, its word forms and the look-alike rules.

    ``terms`` are natural word forms (Russian and English) of the products of the group;
    they are lemmatized before matching, so ``молоко`` also finds ``молока``/``молоком``.
    ``blockers`` are phrases of token prefixes that make the ingredient a safe substitute
    (``(("кокос",),)`` cancels milk for "кокосовое молоко").  ``exceptions`` are exact
    tokens that are homonyms of a term and never trigger the group (``сырой``).
    """

    slug: str
    title: str
    terms: tuple[str, ...]
    blockers: tuple[tuple[str, ...], ...] = ()
    exceptions: tuple[str, ...] = ()


ALLERGEN_GROUPS: dict[str, AllergenGroup] = {
    "milk": AllergenGroup(
        slug="milk",
        title="Молоко и молочные продукты",
        terms=(
            "молоко",
            "молочный",
            "молочные продукты",
            "сливки",
            "сметана",
            "кефир",
            "йогурт",
            "творог",
            "творожный",
            "сыр",
            "сырный",
            "брынза",
            "моцарелла",
            "пармезан",
            "фета",
            "рикотта",
            "маскарпоне",
            "чеддер",
            "сулугуни",
            "простокваша",
            "ряженка",
            "айран",
            "мацони",
            "кумыс",
            "тан",
            "масло сливочное",
            "сливочное масло",
            "топленое масло",
            "сгущенка",
            "сгущенное молоко",
            "сухое молоко",
            "казеин",
            "лактоза",
            "сыворотка",
            "milk",
            "cream",
            "butter",
            "cheese",
            "yogurt",
            "yoghurt",
            "curd",
            "lactose",
            "casein",
            "whey",
        ),
        blockers=(
            ("кокос",),
            ("миндальн",),
            ("соев",),
            ("овсян",),
            ("рисов",),
            ("кешью",),
            ("макадами",),
            ("oat",),
            ("coconut",),
            ("almond",),
            ("soy",),
            ("rice",),
            ("cashew",),
            # Peanut butter is not dairy butter.
            ("peanut", "butter"),
        ),
        # Only the forms whose lemma collides with "сыр": raw potatoes are not cheese.
        exceptions=("сырой", "сырая", "сырое", "сырые", "сырого"),
    ),
    "gluten": AllergenGroup(
        slug="gluten",
        title="Глютен (злаки)",
        terms=(
            "глютен",
            "пшеница",
            "пшеничный",
            "пшеничная мука",
            "мука",
            "мучной",
            "хлеб",
            "хлебный",
            "хлебец",
            "батон",
            "булка",
            "булочка",
            "лаваш",
            "пита",
            "лепешка",
            "тортилья",
            "багет",
            "макароны",
            "макаронные изделия",
            "паста",
            "спагетти",
            "вермишель",
            "лапша",
            "рожь",
            "ржаной",
            "ячмень",
            "ячменный",
            "перловка",
            "овес",
            "овсяный",
            "овсяная мука",
            "овсяные хлопья",
            "геркулес",
            "манка",
            "манная крупа",
            "булгур",
            "кускус",
            "полба",
            "спельта",
            "солод",
            "отруби",
            "сухари",
            "панировка",
            "панировочные сухари",
            "тесто",
            "бисквит",
            "печенье",
            "крекер",
            "галеты",
            "вафли",
            "пряники",
            "соевый соус",
            "soy sauce",
            "пиво",
            "gluten",
            "wheat",
            "flour",
            "bread",
            "pasta",
            "noodles",
            "semolina",
            "barley",
            "rye",
            "oats",
            "malt",
            "bran",
            "couscous",
            "bulgur",
            "crackers",
            "biscuits",
        ),
        blockers=(
            ("гречк",),
            ("гречн",),
            ("рисов",),
            ("кукуруз",),
            ("картоф",),
            ("кокос",),
            ("киноа",),
            # Millet (пшено/пшённая мука), not wheat (пшеничная): the prefix "пшен"
            # itself would also block "пшеничная".
            ("пшенн",),
            ("пшено",),
            ("пшенк",),
            ("амарант",),
            ("нут",),
            ("чечевиц",),
            ("горохов",),
            ("льнян",),
            ("люпин",),
            ("тапиок",),
            ("батат",),
            ("томат",),
            # A product labelled gluten-free is what the user is looking for.
            ("безглютенов",),
            # Soy sauce contains wheat, soy flour does not: the blocker needs both words.
            ("соев", "мук"),
            ("миндальн", "мук"),
            ("buckwheat",),
            ("rice",),
            ("corn",),
            ("potato",),
            ("coconut",),
            ("quinoa",),
            ("millet",),
            ("chickpea",),
            ("lentil",),
            ("soy", "flour"),
            ("almond", "flour"),
        ),
        # "печень" (liver) and "печенье" (biscuit) share the lemma of the naive lemmatizer.
        exceptions=("печень", "печени", "печенью"),
    ),
    "eggs": AllergenGroup(
        slug="eggs",
        title="Яйца",
        terms=(
            "яйцо",
            "яйца",
            "яиц",
            "яичный",
            "яичная",
            "яичный белок",
            "желток",
            "белок",
            "майонез",
            "меланж",
            "альбумин",
            "eggs",
            "egg",
            "yolk",
            "mayonnaise",
            "albumin",
        ),
        # Soy and vegetable protein powders are not egg white.
        blockers=(("соев",), ("растительн",)),
        # "Eggplant" (баклажан) starts with "egg" but has nothing to do with eggs.
        exceptions=("eggplant", "eggplants"),
    ),
    "soy": AllergenGroup(
        slug="soy",
        title="Соя",
        terms=(
            "соя",
            "соевый",
            "соевая",
            "соевое",
            "соевые бобы",
            "соевый соус",
            "соевое молоко",
            "соевая мука",
            "тофу",
            "эдамаме",
            "мисо",
            "темпе",
            "soy",
            "soya",
            "tofu",
            "edamame",
            "miso",
            "tempeh",
        ),
    ),
    "peanut": AllergenGroup(
        slug="peanut",
        title="Арахис",
        terms=(
            "арахис",
            "арахисовый",
            "арахисовая паста",
            "земляной орех",
            "peanut",
            "peanuts",
            "groundnut",
        ),
    ),
    "nuts": AllergenGroup(
        slug="nuts",
        title="Орехи",
        terms=(
            "орех",
            "орехи",
            "ореховый",
            "орешки",
            "миндаль",
            "миндальный",
            "фундук",
            "лесной орех",
            "кешью",
            "фисташка",
            "фисташки",
            "грецкий орех",
            "кедровый орех",
            "кедровые орехи",
            "бразильский орех",
            "макадамия",
            "пекан",
            "nuts",
            "almond",
            "hazelnut",
            "cashew",
            "pistachio",
            "walnut",
            "pecan",
            "macadamia",
        ),
        # Coconut is a fruit and nutmeg is a spice: neither is a tree nut.
        blockers=(("кокос",), ("мускатн",), ("coconut",), ("nutmeg",)),
    ),
    "fish": AllergenGroup(
        slug="fish",
        title="Рыба",
        terms=(
            "рыба",
            "рыбный",
            "рыбная",
            "рыбное",
            "рыбные",
            "рыбный соус",
            "треска",
            "лосось",
            "семга",
            "форель",
            "сельдь",
            "селедка",
            "тунец",
            "минтай",
            "хек",
            "скумбрия",
            "горбуша",
            "камбала",
            "анчоус",
            "сардина",
            "сардины",
            "килька",
            "шпроты",
            "икра",
            "fish",
            "cod",
            "salmon",
            "trout",
            "herring",
            "tuna",
            "anchovy",
            "sardine",
            "caviar",
        ),
        # Zucchini "caviar" (икра кабачковая) is a vegetable spread.
        blockers=(("кабачков",), ("баклажан",)),
    ),
    "seafood": AllergenGroup(
        slug="seafood",
        title="Морепродукты (ракообразные и моллюски)",
        terms=(
            "морепродукты",
            "морской коктейль",
            "креветка",
            "креветки",
            "краб",
            "крабовое мясо",
            "крабовые палочки",
            "лангуст",
            "мидии",
            "устрица",
            "устрицы",
            "кальмар",
            "гребешок",
            "осьминог",
            "раки",
            "seafood",
            "shrimp",
            "prawn",
            "prawns",
            "crab",
            "lobster",
            "mussels",
            "oysters",
            "squid",
            "scallop",
            "octopus",
        ),
    ),
    "sesame": AllergenGroup(
        slug="sesame",
        title="Кунжут",
        terms=(
            "кунжут",
            "кунжутный",
            "кунжутное масло",
            "тахин",
            "тахини",
            "sesame",
            "tahini",
        ),
    ),
    "mustard": AllergenGroup(
        slug="mustard",
        title="Горчица",
        terms=(
            "горчица",
            "горчичный",
            "горчичный порошок",
            "mustard",
        ),
    ),
    "celery": AllergenGroup(
        slug="celery",
        title="Сельдерей",
        terms=(
            "сельдерей",
            "сельдерея",
            "сельдерейный",
            "celery",
            "celeriac",
        ),
    ),
    "sulphites": AllergenGroup(
        slug="sulphites",
        title="Сульфиты",
        terms=(
            "сульфиты",
            "сульфит",
            "диоксид серы",
            "сернистый ангидрид",
            "sulphites",
            "sulfites",
        ),
    ),
    "lupin": AllergenGroup(
        slug="lupin",
        title="Люпин",
        terms=(
            "люпин",
            "люпиновая мука",
            "lupin",
            "lupine",
        ),
    ),
}


# How a user names an allergy in /user_preferences (menu terms, not only ingredients).
# The key is the normalized term (app.ml.preprocessing.normalize_text).
ALLERGEN_ALIASES: dict[str, str] = {
    "молоко": "milk",
    "молочные продукты": "milk",
    "молочный": "milk",
    "молочка": "milk",
    "лактоза": "milk",
    "milk": "milk",
    "dairy": "milk",
    "lactose": "milk",
    "глютен": "gluten",
    "глютеновая непереносимость": "gluten",
    "пшеница": "gluten",
    "злаки": "gluten",
    "gluten": "gluten",
    "wheat": "gluten",
    "яйца": "eggs",
    "яйцо": "eggs",
    "яичный белок": "eggs",
    "eggs": "eggs",
    "egg": "eggs",
    "соя": "soy",
    "соевые продукты": "soy",
    "soy": "soy",
    "soya": "soy",
    "арахис": "peanut",
    "peanut": "peanut",
    "peanuts": "peanut",
    "орехи": "nuts",
    "орех": "nuts",
    "древесные орехи": "nuts",
    "nuts": "nuts",
    "tree nuts": "nuts",
    "рыба": "fish",
    "fish": "fish",
    "морепродукты": "seafood",
    "ракообразные": "seafood",
    "моллюски": "seafood",
    "seafood": "seafood",
    "shellfish": "seafood",
    "кунжут": "sesame",
    "sesame": "sesame",
    "горчица": "mustard",
    "mustard": "mustard",
    "сельдерей": "celery",
    "celery": "celery",
    "сульфиты": "sulphites",
    "сульфит": "sulphites",
    "sulphites": "sulphites",
    "sulfites": "sulphites",
    "люпин": "lupin",
    "lupin": "lupin",
}


@dataclass(frozen=True)
class AllergyQuery:
    """An allergy profile prepared for matching.

    ``groups`` are the dictionary groups the user is allergic to, ``terms`` are the terms
    that name no group (``киви``): they are matched by lemma, so an unusual allergy is
    never ignored just because the dictionary does not know it.
    """

    groups: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        """True when the profile can reject at least one recipe."""
        return bool(self.groups or self.terms)


def all_slugs() -> tuple[str, ...]:
    """Return the slugs of all groups in dictionary order."""
    return tuple(ALLERGEN_GROUPS)


def resolve_allergies(allergies: Sequence[str]) -> AllergyQuery:
    """Map the allergy terms of a user onto groups and plain terms.

    ``["молочные продукты", "киви"]`` becomes ``groups=("milk",)`` and
    ``terms=("киви",)``.
    """
    groups: list[str] = []
    terms: list[str] = []
    for allergy in allergies:
        term = (allergy or "").strip()
        if not term:
            continue
        slug = ALLERGEN_ALIASES.get(preprocessing.normalize_text(term)) or _group_of_term(term)
        if slug is None:
            if term not in terms:
                terms.append(term)
        elif slug not in groups:
            groups.append(slug)
    return AllergyQuery(groups=tuple(groups), terms=tuple(terms))


def matched_allergens(ingredient_names: Sequence[str], query: AllergyQuery) -> list[str]:
    """Return the allergies of ``query`` found among ``ingredient_names``.

    The answer mixes group slugs (``"milk"``) and plain terms (``"киви"``) and keeps the
    order of the dictionary, so both the log line and the message are reproducible.
    """
    names = [name for name in ingredient_names if name and name.strip()]
    if not names or not query:
        return []
    matched = [slug for slug in query.groups if any(_group_in(name, slug) for name in names)]
    if query.terms:
        matched.extend(preprocessing.mark_allergens("; ".join(names), query.terms))
    return matched


def is_safe(ingredient_names: Sequence[str], query: AllergyQuery) -> bool:
    """True when no ingredient of the recipe belongs to a group of ``query``."""
    return not matched_allergens(ingredient_names, query)


@lru_cache(maxsize=None)
def _term_lemmas(slug: str) -> tuple[frozenset[str], ...]:
    """Lemma sets of the terms of a group: a phrase matches when all its lemmas occur."""
    groups: list[frozenset[str]] = []
    for term in ALLERGEN_GROUPS[slug].terms:
        lemmas = frozenset(preprocessing.lemmatize_terms([term]))
        if lemmas:
            groups.append(lemmas)
    return tuple(groups)


def _group_in(name: str, slug: str) -> bool:
    """True when the ingredient name names a product of the group."""
    tokens = preprocessing.normalize_text(name).split()
    if not tokens:
        return False
    group = ALLERGEN_GROUPS[slug]
    # A homonym ("сырой", "печень") makes the ingredient ambiguous, not allergic.
    if any(token in group.exceptions for token in tokens):
        return False
    lemmas = set(preprocessing.lemmatize_terms([name]))
    if not any(term <= lemmas for term in _term_lemmas(slug)):
        return False
    return not _blocked(tokens, slug)


def _blocked(tokens: Sequence[str], slug: str) -> bool:
    """True when a blocker phrase of the group occurs in the ingredient tokens."""
    for phrase in ALLERGEN_GROUPS[slug].blockers:
        if all(any(token.startswith(stem) for token in tokens) for stem in phrase):
            return True
    return False


def _group_of_term(term: str) -> str | None:
    """Return the group whose products the term names, if any."""
    lemmas = set(preprocessing.lemmatize_terms([term]))
    if not lemmas:
        return None
    for slug in ALLERGEN_GROUPS:
        if any(trigger <= lemmas for trigger in _term_lemmas(slug)):
            return slug
    return None
