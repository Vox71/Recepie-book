# Волков Михаил, вариант 1: пошаговая инструкция

**Ветка:** `refactor/pract5-parser`

**Файлы:** только `backend/app/importer/pages.py`.

**Что должно получиться:** длинный `handle_starttag` разбит на диспетчер и маленькие методы.
Порядок проверок тегов не меняется, тесты остаются прежними.

## Шаг 1. Подготовить ветку

```bash
git switch main
git pull
git switch -c refactor/pract5-parser
```

Проверить, что рабочее дерево чистое:

```bash
git status
```

Если есть незакоммиченные изменения, сначала разобраться с ними, а потом создавать ветку.

## Шаг 2. Открыть файл и найти метод

Файл: `backend/app/importer/pages.py`.

Нужный метод начинается около строки 178:

```python
def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
```

Сейчас в нём разбор атрибутов и сразу длинная цепочка `if/elif`. Старые тела веток нужно
перенести в отдельные методы, а не переписать заново.

## Шаг 3. Заменить начало метода

В `handle_starttag` оставить разбор атрибутов и вызовы:

```python
def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
    """Dispatch a start tag to the small handler of that tag."""
    data = dict(attrs)
    props = (data.get("itemprop") or "").split()
    self.itemprops.update(props)
    classes = (data.get("class") or "").split()

    if tag == "h1" and "name" in props:
        self._start_name()
    elif tag == "div" and "nutrition" in props:
        self._start_nutrition()
    elif tag == "div" and ("description" in props or "article-text" in classes):
        self._start_description()
    elif tag == "time" and "totalTime" in props:
        self._start_time(data)
    elif tag == "span" and "recipeYield" in props:
        self._start_yield()
    elif tag == "span" and "recipeCategory" in props:
        self._start_category()
    elif tag == "li" and "recipeIngredient" in props:
        self._start_ingredient()
    elif tag == "span" and self._in_ingredient:
        self._start_ingredient_span()
    elif tag == "li" and "cooking-bl" in classes:
        self._start_step()
    elif tag == "img" and self._in_step and self._step_image is None:
        self._start_step_image(data, props)
    elif tag == "td" and self._in_nutrition:
        self._start_cell(classes)
    elif tag == "br" and self._in_step:
        self._add_step_newline()
    elif tag == "br" and self._in_cell:
        self._add_cell_space()
    elif self._in_step:
        self._add_step_space()
    elif self._capturing:
        self._add_buffer_space()
```

Важно: порядок `elif` должен остаться точно таким же. Это не косметика: от порядка зависит
разбор вложенных тегов.

## Шаг 4. Добавить маленькие методы

Вставить методы между `handle_starttag` и `handle_endtag`:

```python
    def _start_name(self) -> None:
        self._in_name += 1
        self._buffer = []

    def _start_nutrition(self) -> None:
        self._in_nutrition += 1
        self.cells = []

    def _start_description(self) -> None:
        self._in_description += 1
        self._buffer = []

    def _start_time(self, data: dict) -> None:
        self._in_time += 1
        self.time_datetime = data.get("datetime") or self.time_datetime
        self._buffer = []

    def _start_yield(self) -> None:
        self._in_yield += 1
        self._buffer = []

    def _start_category(self) -> None:
        self._in_category += 1
        self._buffer = []

    def _start_ingredient(self) -> None:
        self._in_ingredient += 1
        self._ingredient_spans = []

    def _start_ingredient_span(self) -> None:
        self._in_ingredient_span += 1
        self._buffer = []

    def _start_step(self) -> None:
        if self._in_step:
            # The previous <li> was never closed: keep its text as a step of its own.
            self._flush_step()
        self._in_step += 1
        self._step_text = []
        self._step_image = None

    def _start_step_image(self, data: dict, props: list[str]) -> None:
        src = data.get("src") or ""
        if "image" in props and src:
            self._step_image = src[:MAX_IMAGE_URL_LENGTH]

    def _start_cell(self, classes: list[str]) -> None:
        self._in_cell += 1
        self._cell_is_title = "nae-title" in classes
        self._cell_text = []

    def _add_step_newline(self) -> None:
        self._step_text.append("\n")

    def _add_cell_space(self) -> None:
        # "ккал<br/>2576.3 ккал": a space keeps the number separated from the label.
        self._cell_text.append(" ")

    def _add_step_space(self) -> None:
        # A nested tag inside a step separates words of the source text.
        self._step_text.append(" ")

    def _add_buffer_space(self) -> None:
        # Same for the other fragments: "<b>блюдо!</b> Пикантное" keeps its space.
        self._buffer.append(" ")
```

## Шаг 5. Проверить, что старый код удалён

Нужно убедиться, что тела веток не остались дважды. После правки `handle_starttag` должен
занимать около 25 строк.

```bash
cd backend
ruff check .
black --check .
pytest tests/test_importer_pages.py -q
pytest
```

Если `pytest` падает, сравнить новую версию с `main`:

```bash
git diff main -- backend/app/importer/pages.py
```

## Шаг 6. Закоммитить и запушить

```bash
git diff --stat
git diff --check
git add backend/app/importer/pages.py
git commit -m "refactor(importer): extract start tag handlers"
git push -u origin refactor/pract5-parser
```

В коммите должен быть только `pages.py`. Если в `git diff --stat` появились другие файлы, их
нужно убрать из индекса.

## Шаг 7. Открыть PR

Заголовок:

```text
refactor(importer): extract start tag handlers
```

В описании заполнить `.github/pull_request_template.md`:

- было: 59 строк и 24 проверки;
- стало: около 25 строк в диспетчере и 15 маленьких методов;
- поведение не меняется, тесты те же;
- проверки: `ruff`, `black`, `pytest`.

Ревьюер: Журавлев Владислав. После открытия PR сразу запросить review.

## Частые ошибки

- переставлены `elif` — парсер начнёт читать страницу иначе;
- тело ветки скопировано, но старое не удалено — появляется двойная обработка;
- в коммит попали тесты или чужие файлы;
- `handle_starttag` остался длинным, потому что вынесены не все ветки.
