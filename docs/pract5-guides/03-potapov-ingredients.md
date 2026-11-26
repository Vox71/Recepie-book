# Потапов Артем, вариант 7

**Ветка:** `refactor/pract5-ingredients`

**Файл:** `backend/app/importer/povarenok.py`.

## Что делаем

`parse_ingredients` принимает строку, словарь или список и внутри разбирает всё через
`isinstance`. Функция длинная, и в ней легко запутаться.

Разбиваем на четыре части:

- `_is_missing_value()` — пустое значение;
- `_parse_ingredients_text()` — строка;
- `_pairs_from_container()` — словарь или список;
- `parse_ingredients()` — короткий диспетчер.

Логику не меняем: те же входы должны давать те же пары «название — количество».

## Как делать

1. Сначала вынеси проверку `None` и `NaN` в `_is_missing_value`.
2. Потом вынеси разбор строки в `_parse_ingredients_text`. Внутри остаются `strip()`,
   `MISSING_VALUES`, `_decode_literal()` и `_split_lines()`.
3. Разбор словаря и списка вынеси в `_pairs_from_container`. Если тип не тот — верни `None`.
4. В `parse_ingredients` оставь только:

   ```python
   if _is_missing_value(raw):
       return ()
   if isinstance(raw, str):
       return _parse_ingredients_text(raw)
   pairs = _pairs_from_container(raw)
   if pairs is None:
       return ()
   return _ingredients_from_pairs(pairs)
   ```

5. Проверь:

   ```bash
   cd backend
   ruff check .
   black --check .
   pytest tests/test_importer_povarenok.py -q
   pytest
   ```

## Что писать в PR

Заголовок:

```text
refactor(importer): split parse_ingredients
```

В описании: было 39 строк и вложенные `if/isinstance`, стало четыре функции по 5–15 строк.
Главная функция теперь читается сверху вниз.

## Что может спросить ревьюер

- «Почему `_is_missing_value` отдельно?» — потому что `None` и `NaN` проверяются в двух местах,
  а правило должно быть одно.
- «Не сломалась ли рекурсия?» — `_parse_ingredients_text` вызывает `parse_ingredients` для
  декодированного литерала, как и раньше.
- «Почему не стал менять `_split_line`?» — это отдельная маленькая функция, её не трогаем.

## Не трогай

`_split_lines`, `_split_line`, `_decode_literal`, `_ingredients_from_pairs`, `MISSING_VALUES` и
`MAX_*`. И не добавляй новые форматы данных — только разложи текущую логику.
