# Мокрецов Егор, вариант 8: пошаговая инструкция

**Ветка:** `refactor/pract5-enrich`

**Файлы:** `backend/app/importer/enrich.py`, `backend/app/importer/cli.py`,
`backend/tests/test_importer_pages.py`.

**Что должно получиться:** `enrich_recipes` принимает два аргумента — базу и `EnrichOptions`.
Все вызовы в CLI и тестах обновлены, значения по умолчанию не изменились.

## Шаг 1. Подготовить ветку

```bash
git switch main
git pull
git switch -c refactor/pract5-enrich
git status
```

## Шаг 2. Добавить `EnrichOptions`

В `backend/app/importer/enrich.py` после класса `EnrichmentStats` (около строки 102) добавить:

```python
@dataclass(frozen=True)
class EnrichOptions:
    """All settings of one enrichment run."""

    limit: int = DEFAULT_LIMIT
    delay: float = DEFAULT_DELAY_SECONDS
    force: bool = False
    refresh: bool = False
    cache_dir: str | Path = DEFAULT_CACHE_DIR
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    dry_run: bool = False
    opener: Callable = fetch_recipe_page
```

Все нужные имена уже импортированы в файле. `dataclass` тоже уже импортирован.

## Шаг 3. Заменить сигнатуру `enrich_recipes`

Было:

```python
def enrich_recipes(
    db: Database,
    *,
    limit: int = DEFAULT_LIMIT,
    delay: float = DEFAULT_DELAY_SECONDS,
    force: bool = False,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    dry_run: bool = False,
    opener: Callable = fetch_recipe_page,
) -> EnrichmentStats:
    """Enrich up to ``limit`` recipes and return the counters of the run.
```

Стало:

```python
def enrich_recipes(db: Database, options: EnrichOptions) -> EnrichmentStats:
    """Enrich up to ``options.limit`` recipes and return the counters of the run.
```

## Шаг 4. Заменить имена внутри функции

По всему телу `enrich_recipes` заменить:

```text
limit     -> options.limit
delay     -> options.delay
force     -> options.force
refresh   -> options.refresh
cache_dir -> options.cache_dir
timeout   -> options.timeout
dry_run   -> options.dry_run
opener    -> options.opener
```

Например:

```python
rows = db.fetch_all(
    CANDIDATES_SQL, (options.force, PARSER_VERSION, options.limit)
)
```

и:

```python
html, from_cache = load_page(
    recipe_id,
    url,
    cache_dir=options.cache_dir,
    timeout=options.timeout,
    delay=options.delay,
    refresh=options.refresh,
    opener=options.opener,
)
```

`save_page`, `load_page`, SQL и названия полей не меняются.

## Шаг 5. Обновить CLI

В `backend/app/importer/cli.py` в импорт из `.enrich` добавить `EnrichOptions`:

```python
from .enrich import (
    DEFAULT_CACHE_DIR,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_LIMIT,
    EnrichOptions,
    enrich_recipes,
    page_summary,
)
```

Вызов около строки 160 заменить на:

```python
stats = enrich_recipes(
    database,
    EnrichOptions(
        limit=args.limit or DEFAULT_LIMIT,
        delay=args.delay,
        force=args.force,
        refresh=args.refresh,
        cache_dir=args.pages_dir,
        timeout=args.timeout,
        dry_run=args.dry_run,
    ),
)
```

## Шаг 6. Обновить тесты

В `backend/tests/test_importer_pages.py` добавить `EnrichOptions` в импорт:

```python
from app.importer.enrich import (
    EnrichOptions,
    cache_path,
    enrich_recipes,
    load_page,
    page_summary,
)
```

Заменить вызовы:

```python
stats = enrich_recipes(
    db,
    EnrichOptions(
        cache_dir=tmp_path,
        delay=0.0,
        opener=make_page_opener(fixture_html(FULL)),
    ),
)

stats = enrich_recipes(
    db,
    EnrichOptions(
        cache_dir=tmp_path,
        delay=0.0,
        opener=make_page_opener(fixture_html(PARTIAL)),
    ),
)

first = enrich_recipes(
    db, EnrichOptions(cache_dir=tmp_path, delay=0.0, opener=forbidden)
)
second = enrich_recipes(
    db, EnrichOptions(cache_dir=tmp_path, delay=0.0, opener=forbidden)
)
forced = enrich_recipes(
    db, EnrichOptions(cache_dir=tmp_path, delay=0.0, opener=forbidden, force=True)
)
stats = enrich_recipes(
    db, EnrichOptions(cache_dir=tmp_path, delay=0.0, opener=opener)
)
```

Строки для проверки: 273, 319, 339, 342, 346, 361.

## Шаг 7. Проверить

```bash
cd backend
ruff check .
black --check .
pytest tests/test_importer_pages.py -q
pytest
```

Перед тестами полезно проверить, что старых вызовов не осталось:

```bash
grep -RniE 'enrich_recipes\(db, (limit|delay|force|refresh|cache_dir|timeout|dry_run|opener)' backend
```

## Шаг 8. Коммит и push

```bash
git diff --stat
git diff --check
git add backend/app/importer/enrich.py backend/app/importer/cli.py
git add backend/tests/test_importer_pages.py
git commit -m "refactor(importer): group enrich options"
git push -u origin refactor/pract5-enrich
```

## Шаг 9. PR

Заголовок:

```text
refactor(importer): group enrich options
```

В описании:

- было: 8 параметров;
- стало: `db` + `EnrichOptions`;
- значения по умолчанию не изменились;
- SQL и поля не менялись;
- проверки и `git diff --stat`.

Ревьюер: Волков Михаил.

## Частые ошибки

- в `EnrichOptions` перепутаны значения по умолчанию;
- не все вызовы в тестах обновлены;
- в `cli.py` остался старый длинный вызов;
- изменён `load_page` или SQL, хотя их трогать не нужно.
