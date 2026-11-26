# Потапов Артем, вариант 7: пошаговая инструкция

**Ветка:** `refactor/pract5-ingredients`

**Файл:** `backend/app/importer/povarenok.py`.

**Что должно получиться:** `parse_ingredients` становится коротким диспетчером, а разбор строки,
контейнера и пустого значения выносится в три функции.

## Шаг 1. Подготовить ветку

```bash
git switch main
git pull
git switch -c refactor/pract5-ingredients
git status
```

## Шаг 2. Заменить тело `parse_ingredients`

Файл: `backend/app/importer/povarenok.py`, функция около строки 139.

Новое тело:

```python
def parse_ingredients(raw: Any) -> tuple[Ingredient, ...]:
    """Turn the ``ingredients`` column into normalized ``(name, quantity)`` pairs."""
    if _is_missing_value(raw):
        return ()
    if isinstance(raw, str):
        return _parse_ingredients_text(raw)
    pairs = _pairs_from_container(raw)
    if pairs is None:
        return ()
    return _ingredients_from_pairs(pairs)
```

Докстринг можно оставить коротким: подробности теперь в helper-функциях.

## Шаг 3. Добавить helper-функции

Сразу после `parse_ingredients` вставить:

```python
def _is_missing_value(raw: Any) -> bool:
    """Empty value: None or NaN of a pandas column."""
    return raw is None or (isinstance(raw, float) and math.isnan(raw))


def _parse_ingredients_text(text: str) -> tuple[Ingredient, ...]:
    """Ingredients written as text: a literal, or 'Мука: 300 г; Соль'."""
    stripped = text.strip()
    if stripped.casefold() in MISSING_VALUES:
        return ()
    decoded = _decode_literal(stripped)
    if decoded is not None:
        return parse_ingredients(decoded)
    return _ingredients_from_pairs(_split_lines(stripped))


def _pairs_from_container(raw: Any) -> list[tuple[Any, Any]] | None:
    """Pairs of a mapping or of a list/tuple; None for an unsupported type."""
    if isinstance(raw, Mapping):
        return list(raw.items())
    if isinstance(raw, (list, tuple)):
        pairs: list[tuple[Any, Any]] = []
        for item in raw:
            if isinstance(item, Mapping):
                pairs.extend(item.items())
            elif isinstance(item, str):
                pairs.append(_split_line(item))
            else:
                pairs.append((item, None))
        return pairs
    return None
```

Импорты `math`, `Mapping`, `Any` уже есть в файле. Новые импорты не нужны.

## Шаг 4. Убедиться, что старые ветки удалены

В `parse_ingredients` не должно остаться старых `isinstance`-веток. В файле должна быть одна
короткая функция и три helper-функции.

Функции `_split_lines`, `_split_line`, `_decode_literal`, `_ingredients_from_pairs` не меняются.

## Шаг 5. Проверить

```bash
cd backend
ruff check .
black --check .
pytest tests/test_importer_povarenok.py -q
pytest
```

Если тест падает, сравнить поведение на примерах:

- `None` → `()`;
- `float("nan")` → `()`;
- `"Мука: 300 г; Соль"` → две пары;
- `{"Мука": "300 г"}` → одна пара;
- `["Мука: 300 г", {"Соль": "щепотка"}]` → две пары.

## Шаг 6. Коммит и push

```bash
git diff --stat
git diff --check
git add backend/app/importer/povarenok.py
git commit -m "refactor(importer): split parse_ingredients"
git push -u origin refactor/pract5-ingredients
```

В коммите только `povarenok.py`. Если добавлены тесты, они идут отдельным коммитом или в этом
же PR, но с понятным сообщением.

## Шаг 7. PR

Заголовок:

```text
refactor(importer): split parse_ingredients
```

В описании:

- было: 39 строк и вложенные `if/isinstance`;
- стало: четыре функции по 5–15 строк;
- поведение не меняется;
- проверки и `git diff --stat`.

Ревьюер: Савчук Иван.

## Частые ошибки

- helper-функции оставлены внутри `parse_ingredients`;
- старые ветки `isinstance` не удалены;
- изменён `_split_line` или `_decode_literal`, хотя их не трогаем;
- в `_pairs_from_container` возвращается `[]` вместо `None` для неизвестного типа — тогда
  непонятно, это пустые данные или неподдерживаемый формат.
