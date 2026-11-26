# Тропина Елизавета, вариант 4: пошаговая инструкция

**Ветка:** `refactor/pract5-engine`

**Файлы:** `backend/app/ml/engine.py`, `backend/app/services/smart_recommendation_service.py`,
`backend/tests/test_ml_engine.py`, `backend/tests/test_recommendation_model.py`.

**Что должно получиться:** элементы `outcome["recipes"]` — объекты `ScoredRecipe`, а не словари.
Сам `outcome` остаётся словарём с ключами `"recipes"` и `"stats"`.

## Шаг 1. Подготовить ветку

```bash
git switch main
git pull
git switch -c refactor/pract5-engine
git status
```

## Шаг 2. Добавить импорт и класс

В `backend/app/ml/engine.py` рядом с `import logging` добавить:

```python
from dataclasses import dataclass
```

Перед `recommend_safe_recipes` добавить:

```python
@dataclass(frozen=True)
class ScoredRecipe:
    """One candidate with its similarity to the profile and the final score."""

    recipe: dict
    similarity: float
    score: float
    matched_products: tuple[str, ...]
```

## Шаг 3. Обновить докстринг функции

В докстринге `recommend_safe_recipes` заменить описание формата:

```text
Every entry of ``recipes`` is a ``ScoredRecipe`` with the recipe row, its
similarity to the profile, the final score and the matched fridge products.
```

## Шаг 4. Заменить создание результатов

Было:

```python
    scored: list[dict] = []
    ...
        scored.append(
            {
                "recipe": row,
                "similarity": similarity,
                "score": similarity + FRIDGE_BONUS * share,
                "matched_products": matched_products,
            }
        )
```

Стало:

```python
    scored: list[ScoredRecipe] = []
    ...
        scored.append(
            ScoredRecipe(
                recipe=row,
                similarity=similarity,
                score=similarity + FRIDGE_BONUS * share,
                matched_products=tuple(matched_products),
            )
        )
```

## Шаг 5. Заменить сортировку и фильтр

Было:

```python
    ranked = sorted(scored, key=lambda entry: entry["score"], reverse=True)
    selected = [entry for entry in ranked if entry["score"] > 0][: max(limit, 0)]
```

Стало:

```python
    ranked = sorted(scored, key=lambda entry: entry.score, reverse=True)
    selected = [entry for entry in ranked if entry.score > 0][: max(limit, 0)]
```

## Шаг 6. Обновить сервис

В `backend/app/services/smart_recommendation_service.py` строка 73:

```python
selected = [entry.recipe for entry in outcome["recipes"]]
```

`outcome` и `stats` не меняются.

## Шаг 7. Обновить тесты

В `backend/tests/test_ml_engine.py` заменить:

```python
entry["recipe"]              -> entry.recipe
best["recipe"]               -> best.recipe
best["matched_products"]     -> best.matched_products
outcome["recipes"][1]["matched_products"] -> outcome["recipes"][1].matched_products
```

Строки для проверки: 76, 94, 95, 96, 107, 124. В
`backend/tests/test_recommendation_model.py` строка 113: `entry["recipe"]` → `entry.recipe`.

Удобно проверить перед тестами:

```bash
grep -RniE '\["(recipe|score|matched_products)"\]' backend/tests/test_ml_engine.py \
  backend/tests/test_recommendation_model.py backend/app/services/smart_recommendation_service.py
```

В этих местах не должно остаться обращений к элементам `outcome["recipes"]` как к словарю.

## Шаг 8. Проверить

```bash
cd backend
ruff check .
black --check .
pytest tests/test_ml_engine.py tests/test_recommendation_model.py -q
pytest
```

## Шаг 9. Коммит и push

```bash
git diff --stat
git diff --check
git add backend/app/ml/engine.py backend/app/services/smart_recommendation_service.py
git add backend/tests/test_ml_engine.py backend/tests/test_recommendation_model.py
git commit -m "refactor(ml): use ScoredRecipe instead of dicts"
git push -u origin refactor/pract5-engine
```

## Шаг 10. PR

Заголовок:

```text
refactor(ml): use ScoredRecipe instead of dicts
```

В описании:

- было: список словарей с ключами по договорённости;
- стало: `ScoredRecipe` с четырьмя полями;
- API и `outcome` не меняются;
- проверки и `git diff --stat`.

Ревьюер: Мокрецов Егор.

## Частые ошибки

- изменился `outcome`: он должен остаться словарём;
- `matched_products` остался списком, хотя поле объявлено tuple;
- не все тесты обновлены, и `pytest` падает на `KeyError`;
- в PR попали `knn.py` или `vectorizer.py`.
