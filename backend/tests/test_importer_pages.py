"""Page parser and enrichment of imported recipes (sprint 3, task 2).

Everything here runs **offline**: the parser takes saved pages from
``tests/data/pages`` (real markup, cut down to the needed blocks), and the network call
is replaced with a fake ``opener`` - the same trick ``tests/test_importer_povarenok.py``
uses for the Kaggle download.  A test that needed the site would fail on a build machine
without network and would depend on the site staying unchanged.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from app.importer.enrich import cache_path, enrich_recipes, load_page, page_summary
from app.importer.pages import PageError, fetch_recipe_page, parse_recipe_page

FIXTURES = Path(__file__).parent / "data" / "pages"
FULL = "povarenok_page_full.html"
NO_TIME = "povarenok_page_no_time.html"
PARTIAL = "povarenok_page_partial.html"
URL = "https://www.povarenok.ru/recipes/show/184919/"


def fixture_html(name: str) -> str:
    """Return one saved page as text."""
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    """Minimal answer of ``urlopen``: ``read`` plus headers and the context manager."""

    def __init__(self, body: bytes, content_type: str = "text/html; charset=windows-1251") -> None:
        self._body = io.BytesIO(body)
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body.read()

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info) -> None:
        self._body.close()


def make_opener(body: str, *, encoding: str = "utf-8", calls: list | None = None):
    """Return an ``opener`` that serves ``body`` and records the request."""
    charset = "windows-1251" if encoding == "cp1251" else "utf-8"

    def opener(request, *, timeout):
        if calls is not None:
            calls.append((request, timeout))
        return FakeResponse(body.encode(encoding), f"text/html; charset={charset}")

    return opener


def make_page_opener(body: str, calls: list | None = None):
    """Return an ``opener`` of ``load_page``/``enrich_recipes``: a URL in, HTML out."""

    def opener(url, *, timeout):
        if calls is not None:
            calls.append((url, timeout))
        return body

    return opener


def test_parse_full_page() -> None:
    """A page with steps, time, servings and nutrition yields all of them."""
    page = parse_recipe_page(fixture_html(FULL), source_url=URL)

    assert page.name == "Капустница по-Чешски"
    assert page.steps and len(page.steps) == 7
    assert page.cooking_time_minutes == 40
    assert page.servings == 6
    assert len(page.ingredients) == 12
    assert page.ingredients[0].name
    assert page.categories == ("Бульоны и супы", "Горячие супы", "Щи")
    assert page.description and page.description.startswith("Есть супы")
    # Every step of this page has a photo.
    assert all(
        image and image.startswith("https://www.povarenok.ru/") for image in page.step_images
    )
    # The numbered text is what recipes.instruction receives.
    assert page.instruction_text is not None
    assert page.instruction_text.startswith("1. ")
    assert "\n2. " in page.instruction_text


def test_nutrition_of_the_full_page() -> None:
    """The two groups of the table land in the eight numeric fields."""
    nutrition = parse_recipe_page(fixture_html(FULL), source_url=URL).nutrition

    assert nutrition is not None
    assert nutrition.calories_total == pytest.approx(2156.0)
    assert nutrition.protein_total == pytest.approx(200.6)
    assert nutrition.fat_total == pytest.approx(116.5)
    assert nutrition.carbs_total == pytest.approx(39.4)
    assert nutrition.calories_per_100g == pytest.approx(65.7)
    assert nutrition.carbs_per_100g == pytest.approx(1.2)
    assert not nutrition.is_empty()


def test_a_page_without_time_and_servings() -> None:
    """Both fields are optional: about half of the pages do not publish them."""
    page = parse_recipe_page(fixture_html(NO_TIME), source_url=URL)

    assert page.cooking_time_minutes is None
    assert page.servings is None
    # The rest of the page is still parsed.
    assert len(page.steps) == 10
    assert page.nutrition is not None


def test_a_page_without_steps_and_nutrition() -> None:
    """Nothing to write is not an error: the parser returns empty values."""
    page = parse_recipe_page(fixture_html(PARTIAL), source_url=URL)

    assert page.steps == ()
    assert page.step_images == ()
    assert page.instruction_text is None
    assert page.nutrition is None
    assert page.name == "Капустница по-Чешски"
    assert page.servings == 6


def test_step_text_keeps_the_line_breaks_of_the_source() -> None:
    """A ``<br>`` of the page is a line break inside one step, not a new step."""
    page = parse_recipe_page(fixture_html(NO_TIME), source_url=URL)
    first = page.steps[0]

    assert "\n" in first
    assert len(page.steps) == 10


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ('<time itemprop="totalTime" datetime="PT40M">40 минут</time>', 40),
        ('<time itemprop="totalTime" datetime="PT1H20M">1 час 20 минут</time>', 80),
        ('<time itemprop="totalTime" datetime="PT90M">90 минут</time>', 90),
        # Without datetime the text itself is parsed.
        ('<time itemprop="totalTime">1 час 20 минут</time>', 80),
        # Out of the range of recipes.cooking_time_minutes (1..1440) -> dropped.
        ('<time itemprop="totalTime" datetime="PT3D">3 дня</time>', None),
        ('<time itemprop="totalTime">много</time>', None),
    ],
)
def test_cooking_time_is_read_from_the_microdata(markup: str, expected: int | None) -> None:
    """``totalTime`` is an ISO 8601 duration; a wrong one does not become a number."""
    html = f'<html><body><h1 itemprop="name">Блюдо</h1>{markup}</body></html>'

    page = parse_recipe_page(html, source_url=URL)

    assert page.cooking_time_minutes == expected


def test_a_page_without_microdata_is_rejected() -> None:
    """A page of the site that is not a recipe page must fail with a clear error."""
    with pytest.raises(PageError, match="no schema.org microdata"):
        parse_recipe_page("<html><body><p>Привет</p></body></html>", source_url=URL)


def test_a_page_with_microdata_but_no_name_is_rejected() -> None:
    """Nutrition alone is not a recipe: neither a name nor steps means "not a recipe"."""
    html = '<div itemprop="nutrition"><strong itemprop="calories">10 ккал</strong></div>'

    with pytest.raises(PageError, match="not a recipe page"):
        parse_recipe_page(html, source_url=URL)


def test_broken_markup_does_not_crash_the_parser() -> None:
    """An unclosed ``li`` of the steps must not raise; the collected text is kept.

    The page is written by people with an editor, so unclosed tags happen.  The parser
    cannot split two steps that were never closed - it keeps their text as one step
    instead of losing the instruction (garbage in, but no crash and no silent empty field).
    """
    html = (
        '<h1 itemprop="name">Сломанная страница</h1>'
        '<ul itemprop="recipeInstructions">'
        '<li class="cooking-bl"><div><p>Первый шаг.</p></div>'
        '<li class="cooking-bl"><div><p>Второй шаг.</p></div>'
        "</ul>"
    )

    page = parse_recipe_page(html, source_url=URL)

    assert page.name == "Сломанная страница"
    assert page.steps == ("Первый шаг.", "Второй шаг.")


def test_fetch_decodes_windows_1251_and_identifies_itself() -> None:
    """The site serves cp1251 and refuses anonymous clients, so both are handled."""
    calls: list = []
    opener = make_opener('<h1 itemprop="name">Щи</h1>', encoding="cp1251", calls=calls)

    html = fetch_recipe_page(URL, timeout=7, opener=opener)

    assert "Щи" in html
    request, timeout = calls[0]
    assert timeout == 7
    assert request.get_header("User-agent").startswith("RecepieBookBot/")


def test_fetch_turns_http_error_into_page_error() -> None:
    """A 403 of the site is a readable error, and the run can stop on it."""

    def opener(request, *, timeout):
        raise HTTPError(URL, 403, "Forbidden", {}, None)

    with pytest.raises(PageError, match="HTTP 403"):
        fetch_recipe_page(URL, opener=opener)


def test_fetch_turns_network_error_into_page_error() -> None:
    """A timeout of the network is a ``PageError`` too, never a raw ``URLError``."""

    def opener(request, *, timeout):
        raise URLError("timed out")

    with pytest.raises(PageError, match="timed out"):
        fetch_recipe_page(URL, opener=opener)


def test_page_summary_describes_the_page() -> None:
    """The summary is what ``--url`` and ``--dry-run`` print: a flat, loggable dict."""
    summary = page_summary(parse_recipe_page(fixture_html(FULL), source_url=URL))

    assert summary["url"] == URL
    assert summary["steps"] == 7
    assert summary["time_minutes"] == 40
    assert summary["servings"] == 6
    assert summary["nutrition"]["calories_total"] == pytest.approx(2156.0)
    assert summary["first_step"].startswith("Приготовить бульон")
    # JSON-ready: the CLI writes it with json.dumps.
    assert json.loads(json.dumps(summary, ensure_ascii=False))["steps"] == 7


# -- enrichment against PostgreSQL -------------------------------------------------------


def insert_recipe(db, url: str, name: str = "Импортированный") -> int:
    """Insert an imported recipe (the row the dataset importer creates)."""
    row = db.fetch_one(
        """
        INSERT INTO recipes (source_url, recipe_name, ingredients)
        VALUES (%s, %s, 'вода — 1 л')
        RETURNING id
        """,
        (url, name),
    )
    return int(row["id"])


def write_cache(cache_dir: Path, recipe_id: int, html: str) -> None:
    """Put a page into the HTML cache, as the first run of the importer would."""
    path = cache_path(cache_dir, recipe_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def test_enrich_saves_the_parsed_page(db, tmp_path) -> None:
    """Steps, time, servings, nutrition and the parser mark reach the database."""
    recipe_id = insert_recipe(db, URL)

    stats = enrich_recipes(
        db, cache_dir=tmp_path, delay=0.0, opener=make_page_opener(fixture_html(FULL))
    )

    assert stats.candidates == 1
    assert (stats.fetched, stats.from_cache, stats.updated, stats.failed) == (1, 0, 1, 0)
    assert stats.with_nutrition == 1

    recipe = db.fetch_one(
        """
        SELECT instruction, cooking_time_minutes, servings, parsed_at, parser_version
        FROM recipes WHERE id = %s
        """,
        (recipe_id,),
    )
    assert recipe["instruction"].startswith("1. ")
    assert recipe["cooking_time_minutes"] == 40
    assert recipe["servings"] == 6
    assert recipe["parsed_at"] is not None
    assert recipe["parser_version"] == "pages/1"

    steps = db.fetch_all(
        "SELECT step_number, text, image_url FROM recipe_steps WHERE recipe_id = %s "
        "ORDER BY step_number",
        (recipe_id,),
    )
    assert [step["step_number"] for step in steps] == [1, 2, 3, 4, 5, 6, 7]
    assert all(step["text"] for step in steps)
    assert steps[0]["image_url"].startswith("https://www.povarenok.ru/")

    nutrition = db.fetch_one(
        """
        SELECT calories_total, protein_total, carbs_per_100g, source
        FROM recipe_nutrition WHERE recipe_id = %s
        """,
        (recipe_id,),
    )
    assert float(nutrition["calories_total"]) == pytest.approx(2156.0)
    assert float(nutrition["carbs_per_100g"]) == pytest.approx(1.2)
    assert nutrition["source"] == "povarenok"


def test_enrich_marks_a_page_without_steps(db, tmp_path) -> None:
    """A page without steps writes no rows but is marked parsed, so it is not refetched."""
    recipe_id = insert_recipe(db, URL)

    stats = enrich_recipes(
        db, cache_dir=tmp_path, delay=0.0, opener=make_page_opener(fixture_html(PARTIAL))
    )

    assert stats.without_steps == 1
    assert stats.updated == 1
    assert db.fetch_all("SELECT 1 FROM recipe_steps WHERE recipe_id = %s", (recipe_id,)) == []
    recipe = db.fetch_one("SELECT parsed_at, servings FROM recipes WHERE id = %s", (recipe_id,))
    assert recipe["parsed_at"] is not None
    assert recipe["servings"] == 6


def test_enrich_is_idempotent_and_uses_the_cache(db, tmp_path) -> None:
    """The second run touches nothing, and even ``--force`` goes to the cache, not the site."""
    recipe_id = insert_recipe(db, URL)
    write_cache(tmp_path, recipe_id, fixture_html(FULL))

    def forbidden(request, *, timeout):
        raise AssertionError("the cached page must be used instead of the network")

    first = enrich_recipes(db, cache_dir=tmp_path, delay=0.0, opener=forbidden)
    assert (first.updated, first.from_cache, first.fetched) == (1, 1, 0)

    second = enrich_recipes(db, cache_dir=tmp_path, delay=0.0, opener=forbidden)
    assert second.candidates == 0
    assert second.updated == 0

    forced = enrich_recipes(db, cache_dir=tmp_path, delay=0.0, opener=forbidden, force=True)
    assert forced.candidates == 1
    assert (forced.updated, forced.fetched) == (1, 0)


def test_enrich_counts_a_failed_page_and_keeps_going(db, tmp_path) -> None:
    """One broken page does not stop the run and stays marked as not parsed."""
    broken_id = insert_recipe(db, "https://www.povarenok.ru/recipes/show/1/", "Сломанная")
    good_id = insert_recipe(db, URL, "Хорошая")

    def opener(url, *, timeout):
        if url.endswith("/1/"):
            raise PageError(f"{url}: HTTP 404")
        return fixture_html(FULL)

    stats = enrich_recipes(db, cache_dir=tmp_path, delay=0.0, opener=opener)

    assert stats.candidates == 2
    assert (stats.failed, stats.updated) == (1, 1)
    marks = {
        int(row["id"]): row["parsed_at"]
        for row in db.fetch_all("SELECT id, parsed_at FROM recipes")
    }
    assert marks[broken_id] is None
    assert marks[good_id] is not None


def test_load_page_reports_where_the_html_came_from(tmp_path) -> None:
    """The cache is written on the first call and reused afterwards (no second request)."""
    calls: list = []
    opener = make_page_opener(fixture_html(FULL), calls=calls)

    first, from_cache_first = load_page(1, URL, cache_dir=tmp_path, delay=0.0, opener=opener)
    second, from_cache_second = load_page(1, URL, cache_dir=tmp_path, delay=0.0, opener=opener)

    assert (from_cache_first, from_cache_second) == (False, True)
    assert first == second
    assert len(calls) == 1
    assert cache_path(tmp_path, 1).is_file()
