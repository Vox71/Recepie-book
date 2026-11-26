# Тропина Елизавета, вариант 4

**Ветка:** `refactor/pract5-engine`

**Файлы:** `backend/app/ml/engine.py`, `backend/app/services/smart_recommendation_service.py`,
`backend/tests/test_ml_engine.py`, `backend/tests/test_recommendation_model.py`.

## Что делаем

В `recommend_safe_recipes` результаты складываются в словари с ключами `"recipe"`,
`"similarity"`, `"score"`, `"matched_products"`. Если в ключе опечатка, Python не заметит —
получится пустое значение.

Заменяем словарь на `ScoredRecipe` с четырьмя полями. Внешний `outcome` остаётся словарём с
ключами `"recipes"` и `"stats"` — это важно, API не должен измениться.

## Как делать

1. Добавь `from dataclasses import dataclass`.
2. Перед функцией объяви:

   ```python
   @dataclass(frozen=True)
   class ScoredRecipe:
       recipe: dict
       similarity: float
       score: float
       matched_products: tuple[str, ...]
   ```

3. Поменяй `scored: list[dict]` на `list[ScoredRecipe]`.
4. Вместо `scored.append({...})` создавай `ScoredRecipe(...)`, а `matched_products` приводи к
   `tuple`.
5. В сортировке и фильтре замени `entry["score"]` на `entry.score`.
6. В `smart_recommendation_service.py` замени `entry["recipe"]` на `entry.recipe`.
7. В тестах поправь обращения к полям.
8. Проверь:

   ```bash
   cd backend
   ruff check .
   black --check .
   pytest tests/test_ml_engine.py tests/test_recommendation_model.py -q
   pytest
   ```

## Что писать в PR

Заголовок:

```text
refactor(ml): use ScoredRecipe instead of dicts
```

В описании: было «словарь по договорённости», стало четыре явных поля. Опечатка теперь ловится
при запуске, а не превращается в пустое значение. Контракт API не менялся.

## Что может спросить ревьюер

- «Почему `matched_products` — tuple, а не list?» — чтобы объект был неизменяемым, как и весь
  `ScoredRecipe`.
- «Почему `recipe: dict`, а не отдельный тип?» — на этом шаге это строка из базы; отдельный DTO
  для рецепта — уже другая задача.
- «Точно ли API не меняется?» — `outcome["recipes"]` внутри стал объектами, но сервис сразу
  превращает их обратно в `entry.recipe`; в JSON уходит то же самое.

## Осторожно

Не меняй `knn.py`, `vectorizer.py`, статистику `stats` и названия полей ответа API. В тестах
меняются только обращения к элементам результата.
