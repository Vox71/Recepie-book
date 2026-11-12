"""Reader of a povarenok.ru recipe page (sprint 3, task 2).

The Kaggle dataset behind ``recipes.source_url`` holds only ``url``, ``name`` and
``ingredients``.  The page itself is much richer, and it is marked up with
**schema.org microdata** (``itemprop``), not JSON-LD: a parser that follows ``itemprop``
survives the CSS redesigns the site does regularly, while a parser of class names does not
(``docs/povarenok-pages.md``).

What the page publishes (measured on a live sample, ``docs/povarenok-pages.md``):

* ``h1[itemprop=name]``, ``div.article-text[itemprop=description]``, ``img[itemprop=image]``;
* ``li[itemprop=recipeIngredient]`` — the same ingredients the dataset already has;
* ``ul[itemprop=recipeInstructions] > li.cooking-bl`` — the steps, each with text and an
  optional photo (``img[itemprop=image]``);
* ``<time itemprop="totalTime" datetime="PT40M">40 минут</time>`` — a machine readable
  duration, present on about half of the recipes;
* ``span[itemprop=recipeYield]`` — portions, present on about four recipes out of ten;
* ``div[itemprop=nutrition]`` — calories and macros for the whole dish and per 100 g;
* **no** difficulty at all, so ``recipes.difficulty_level`` stays NULL.

The module is pure: :func:`parse_recipe_page` takes HTML and returns a dataclass, so every
test runs offline against a saved page.  :func:`fetch_recipe_page` is the only network
call; it takes a URL and an injectable ``opener``, decodes ``windows-1251`` and turns
HTTP problems into :class:`PageError` (CONTRIBUTION.md §7: a network call always has a
timeout).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# The site answers 403 to anonymous clients such as "curl/8" but accepts a named bot, so
# the importer introduces itself instead of pretending to be a browser.
USER_AGENT = "RecepieBookBot/0.1 (+https://github.com/Vox71/Recepie-book; educational project)"
DEFAULT_TIMEOUT_SECONDS = 20

# Bounds of the target columns and of the answer: a page with 200 steps is a broken page,
# not a recipe, and recipes.instruction is truncated the same way the API truncates it
# (MAX_INSTRUCTION_LENGTH in app/validation.py).
MAX_STEPS = 50
MAX_STEP_TEXT = 2000
MAX_INSTRUCTION_LENGTH = 10_000
MAX_IMAGE_URL_LENGTH = 255  # recipe_steps.image_url

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
# ISO 8601 duration of the "totalTime" microdata: PT40M, PT1H20M, PT90M, P1DT2H.
DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)
GROUP_TOTAL = "total"
GROUP_PER_100G = "per_100g"


class PageError(RuntimeError):
    """The page cannot be read or is not a recipe page (HTTP error, wrong markup)."""


@dataclass(frozen=True)
class Ingredient:
    """One ``li[itemprop=recipeIngredient]`` of the page."""

    name: str
    quantity: str | None = None


@dataclass(frozen=True)
class Nutrition:
    """Calories and macros of the page; every value is optional.

    The page publishes two groups of four numbers: the whole dish and 100 g of it.
    Per-serving values are derivable from ``recipes.servings`` and are not stored.
    """

    calories_total: float | None = None
    protein_total: float | None = None
    fat_total: float | None = None
    carbs_total: float | None = None
    calories_per_100g: float | None = None
    protein_per_100g: float | None = None
    fat_per_100g: float | None = None
    carbs_per_100g: float | None = None

    def is_empty(self) -> bool:
        """``True`` when the page gave no number at all (then nothing is stored)."""
        return all(
            value is None
            for value in (
                self.calories_total,
                self.protein_total,
                self.fat_total,
                self.carbs_total,
                self.calories_per_100g,
                self.protein_per_100g,
                self.fat_per_100g,
                self.carbs_per_100g,
            )
        )


@dataclass(frozen=True)
class ParsedPage:
    """What one recipe page says, in the terms of ``app/schema.sql``."""

    source_url: str
    name: str | None = None
    description: str | None = None
    steps: tuple[str, ...] = ()
    step_images: tuple[str | None, ...] = ()
    cooking_time_minutes: int | None = None
    servings: int | None = None
    nutrition: Nutrition | None = None
    ingredients: tuple[Ingredient, ...] = field(default_factory=tuple)
    categories: tuple[str, ...] = ()

    @property
    def instruction_text(self) -> str | None:
        """Return the numbered text of the steps (``recipes.instruction``), or ``None``.

        The rows of ``recipe_steps`` are the source of truth; this text is written to
        ``recipes.instruction`` as well, so a client that knows nothing about steps keeps
        showing an instruction (openapi.yaml still declares only ``instructions``).
        """
        if not self.steps:
            return None
        text = "\n".join(f"{number}. {step}" for number, step in enumerate(self.steps, 1))
        return text[:MAX_INSTRUCTION_LENGTH]


class _RecipeParser(HTMLParser):
    """Collect the microdata of one recipe page.

    ``HTMLParser`` is used instead of a third-party library on purpose: the page is read
    by ``itemprop`` only, the needed fragments are flat lists, and the importer then needs
    no dependency the production image does not already have.  Nested tags are handled
    with counters, because ``HTMLParser`` reports an end tag even for an element it never
    opened - a broken page must not crash the import.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.itemprops: set[str] = set()
        self.name = ""
        self.description = ""
        self.time_datetime: str | None = None
        self.time_text = ""
        self.servings_text = ""
        self.steps: list[tuple[str, str | None]] = []
        self.categories: list[str] = []
        self.ingredients: list[tuple[str, str | None]] = []
        self.cells: list[tuple[bool, str]] = []

        self._buffer: list[str] = []
        self._in_name = 0
        self._in_description = 0
        self._in_time = 0
        self._in_yield = 0
        self._in_category = 0
        self._in_ingredient = 0
        self._in_ingredient_span = 0
        self._ingredient_spans: list[str] = []
        self._in_step = 0
        self._step_text: list[str] = []
        self._step_image: str | None = None
        self._in_nutrition = 0
        self._in_cell = 0
        self._cell_is_title = False
        self._cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        props = (data.get("itemprop") or "").split()
        self.itemprops.update(props)
        classes = (data.get("class") or "").split()

        if tag == "h1" and "name" in props:
            self._in_name += 1
            self._buffer = []
        elif tag == "div" and "nutrition" in props:
            self._in_nutrition += 1
            self.cells = []
        elif tag == "div" and ("description" in props or "article-text" in classes):
            self._in_description += 1
            self._buffer = []
        elif tag == "time" and "totalTime" in props:
            self._in_time += 1
            self.time_datetime = data.get("datetime") or self.time_datetime
            self._buffer = []
        elif tag == "span" and "recipeYield" in props:
            self._in_yield += 1
            self._buffer = []
        elif tag == "span" and "recipeCategory" in props:
            self._in_category += 1
            self._buffer = []
        elif tag == "li" and "recipeIngredient" in props:
            self._in_ingredient += 1
            self._ingredient_spans = []
        elif tag == "span" and self._in_ingredient:
            self._in_ingredient_span += 1
            self._buffer = []
        elif tag == "li" and "cooking-bl" in classes:
            if self._in_step:
                # The previous <li> was never closed: keep its text as a step of its own.
                self._flush_step()
            self._in_step += 1
            self._step_text = []
            self._step_image = None
        elif tag == "img" and self._in_step and self._step_image is None:
            src = data.get("src") or ""
            if "image" in props and src:
                self._step_image = src[:MAX_IMAGE_URL_LENGTH]
        elif tag == "td" and self._in_nutrition:
            self._in_cell += 1
            self._cell_is_title = "nae-title" in classes
            self._cell_text = []
        elif tag == "br" and self._in_step:
            self._step_text.append("\n")
        elif tag == "br" and self._in_cell:
            # "ккал<br/>2576.3 ккал": a space keeps the number separated from the label.
            self._cell_text.append(" ")
        elif self._in_step:
            # A nested tag inside a step separates words of the source text.
            self._step_text.append(" ")
        elif self._capturing:
            # Same for the other fragments: "<b>блюдо!</b> Пикантное" keeps its space.
            self._buffer.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._in_name:
            self._in_name -= 1
            self.name = _clean(self._take())
        elif tag == "div" and self._in_nutrition and not self._in_cell:
            self._in_nutrition -= 1
        elif tag == "div" and self._in_description:
            self._in_description -= 1
            self.description = _clean_multiline(self._take())
        elif tag == "time" and self._in_time:
            self._in_time -= 1
            self.time_text = _clean(self._take())
        elif tag == "span" and self._in_yield:
            self._in_yield -= 1
            self.servings_text = _clean(self._take())
        elif tag == "span" and self._in_category:
            self._in_category -= 1
            text = _clean(self._take())
            if text:
                self.categories.append(text)
        elif tag == "span" and self._in_ingredient_span:
            self._in_ingredient_span -= 1
            text = _clean(self._take())
            if text:
                self._ingredient_spans.append(text)
        elif tag == "li" and self._in_ingredient:
            self._in_ingredient -= 1
            if self._ingredient_spans:
                name = self._ingredient_spans[0]
                quantity = self._ingredient_spans[1] if len(self._ingredient_spans) > 1 else None
                self.ingredients.append((name, quantity))
            self._ingredient_spans = []
        elif tag == "li" and self._in_step:
            self._flush_step()
        elif tag == "ul" and self._in_step:
            # Unclosed <li> of a broken page: flush what was collected instead of losing it.
            self._flush_step()
        elif tag == "td" and self._in_cell:
            self._in_cell -= 1
            self.cells.append((self._cell_is_title, _clean("".join(self._cell_text))))
            self._cell_text = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)
        if self._in_step:
            # Steps are collected separately: the <li> may hold a photo and paragraphs.
            self._step_text.append(data)
        elif self._capturing:
            self._buffer.append(data)

    @property
    def _capturing(self) -> bool:
        """``True`` while one of the captured fragments is open."""
        return bool(
            self._in_name
            or self._in_description
            or self._in_time
            or self._in_yield
            or self._in_category
            or self._in_ingredient_span
        )

    def _take(self) -> str:
        """Return the captured text and reset the buffer."""
        text = "".join(self._buffer)
        self._buffer = []
        return text

    def _flush_step(self) -> None:
        """Close the current step (also used when a broken page forgets ``</li>``)."""
        if not self._in_step:
            return
        text = _clean_multiline("".join(self._step_text))[:MAX_STEP_TEXT]
        if text:
            self.steps.append((text, self._step_image))
        self._step_text = []
        self._step_image = None
        self._in_step = 0


def parse_recipe_page(html: str, *, source_url: str) -> ParsedPage:
    """Parse one saved recipe page; raise :class:`PageError` for a non-recipe page.

    ``source_url`` is only carried through to the result: the parser never fetches.
    """
    parser = _RecipeParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - HTMLParser is lenient, but be explicit
        raise PageError(f"{source_url}: cannot parse HTML: {exc}") from exc

    steps = tuple(text for text, _ in parser.steps[:MAX_STEPS])
    images = tuple(image for _, image in parser.steps[:MAX_STEPS])
    if not parser.itemprops:
        raise PageError(f"{source_url}: no schema.org microdata found, not a recipe page")
    if not parser.name and not steps:
        raise PageError(f"{source_url}: neither a name nor steps found, not a recipe page")

    return ParsedPage(
        source_url=source_url,
        name=parser.name or None,
        description=parser.description or None,
        steps=steps,
        step_images=images,
        cooking_time_minutes=_cooking_time(parser.time_datetime, parser.time_text),
        servings=_servings(parser.servings_text),
        nutrition=_nutrition(parser.cells),
        ingredients=tuple(
            Ingredient(name=name, quantity=quantity) for name, quantity in parser.ingredients
        ),
        categories=tuple(parser.categories),
    )


def fetch_recipe_page(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    opener: Callable = urlopen,
) -> str:
    """Download one page and decode it; every failure becomes :class:`PageError`.

    ``opener`` is injectable so the network logic is tested without the network, like the
    Kaggle download in ``app/importer/source.py``.
    """
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru,en;q=0.8",
        },
    )
    try:
        # ``timeout`` is a keyword: the second positional argument of ``urlopen`` is
        # the request body, not the timeout.
        with opener(request, timeout=timeout) as response:
            raw = response.read()
            content_type = ""
            headers = getattr(response, "headers", None)
            if headers is not None:
                content_type = headers.get("Content-Type", "") or ""
    except HTTPError as exc:
        raise PageError(f"{url}: HTTP {exc.code}") from exc
    except URLError as exc:
        raise PageError(f"{url}: {exc.reason}") from exc
    except OSError as exc:
        raise PageError(f"{url}: {exc}") from exc
    return raw.decode(_charset(content_type), errors="replace")


def _clean(text: str) -> str:
    """Collapse every run of whitespace into one space and trim the ends."""
    return " ".join(text.split())


def _clean_multiline(text: str) -> str:
    """Collapse spaces per line, keep the line breaks (a ``<br>`` of a step) and drop empties."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _first_number(text: str) -> float | None:
    """Return the first number of ``text`` (``"2576.3 ккал"`` → ``2576.3``)."""
    match = NUMBER_RE.search(text.replace(",", "."))
    return float(match.group(0)) if match else None


def _charset(content_type: str) -> str:
    """Pick the encoding of the answer: the site serves ``windows-1251``."""
    lowered = (content_type or "").lower()
    if "1251" in lowered:
        return "cp1251"
    if "koi8" in lowered:
        return "koi8-r"
    return "utf-8"


def _minutes_from_duration(value: str) -> int | None:
    """Turn an ISO 8601 duration of ``itemprop="totalTime"`` into minutes.

    ``PT40M`` → 40, ``PT1H20M`` → 80, ``PT90M`` → 90, ``P1DT2H`` → 1560.  A duration
    longer than a day is not a cooking time, so it is dropped by the caller's range check.
    """
    match = DURATION_RE.match(value.strip().upper())
    if not match:
        return None
    parts = {name: int(raw or 0) for name, raw in match.groupdict().items()}
    minutes = parts["days"] * 1440 + parts["hours"] * 60 + parts["minutes"]
    minutes += round(parts["seconds"] / 60)
    return minutes or None


def _minutes_from_text(text: str) -> int | None:
    """Parse a human duration ("40 минут", "1 час 20 минут") when ``datetime`` is absent."""
    if not text:
        return None
    hours = re.search(r"(\d+)\s*(?:час|ч\.)", text, flags=re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*(?:минут|мин)", text, flags=re.IGNORECASE)
    if hours or minutes:
        return (int(hours.group(1)) if hours else 0) * 60 + (
            int(minutes.group(1)) if minutes else 0
        )
    number = _first_number(text)
    return int(number) if number is not None else None


def _cooking_time(datetime_value: str | None, text: str) -> int | None:
    """Cooking time in minutes, bounded by ``recipes.cooking_time_minutes`` (1..1440)."""
    # The machine readable duration is authoritative: when it is present but broken, the
    # text is not guessed ("3 дня" would otherwise become 3 minutes).
    minutes = (
        _minutes_from_duration(datetime_value)
        if datetime_value is not None
        else _minutes_from_text(text)
    )
    if minutes is None or not 1 <= minutes <= 1440:
        return None
    return minutes


def _servings(text: str) -> int | None:
    """Servings of ``itemprop="recipeYield"``, bounded by ``recipes.servings`` (1..100)."""
    number = _first_number(text)
    if number is None:
        return None
    servings = int(number)
    return servings if 1 <= servings <= 100 else None


def _nutrition(cells: list[tuple[bool, str]]) -> Nutrition | None:
    """Read the two groups of the nutrition table: the whole dish and 100 g of it.

    The table has a title cell per group (``Готового блюда``, ``100 г блюда``, ``Порции``)
    followed by four cells in a fixed order: calories, protein, fat, carbs.  Only the
    first two groups are stored (``recipe_nutrition``); ``Порции`` is derivable.
    """
    groups: dict[str, list[float]] = {GROUP_TOTAL: [], GROUP_PER_100G: []}
    current: str | None = None
    for is_title, cell in cells:
        if is_title:
            lowered = cell.lower()
            if "готового" in lowered:
                current = GROUP_TOTAL
            elif "100" in cell:
                current = GROUP_PER_100G
            else:
                current = None
            continue
        if current is None or len(groups[current]) >= 4:
            continue
        number = _first_number(cell)
        if number is not None:
            groups[current].append(number)

    total = (groups[GROUP_TOTAL] + [None] * 4)[:4]
    per_100g = (groups[GROUP_PER_100G] + [None] * 4)[:4]
    nutrition = Nutrition(
        calories_total=total[0],
        protein_total=total[1],
        fat_total=total[2],
        carbs_total=total[3],
        calories_per_100g=per_100g[0],
        protein_per_100g=per_100g[1],
        fat_per_100g=per_100g[2],
        carbs_per_100g=per_100g[3],
    )
    return None if nutrition.is_empty() else nutrition
