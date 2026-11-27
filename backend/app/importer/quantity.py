"""Normalization of free-form ingredient amounts.

``recipe_ingredients.quantity_text`` keeps the source spelling (``"250 мл"``,
``"3 шт"``, ``"1 кг"``); the two normalized columns answer the questions the UI and the
future portion calculation need: how much, and in which unit.  Mass is converted to grams
and volume to millilitres; countable units stay countable.  A range (``"1–2 шт."``) is not
reduced to one number, so it remains text-only: inventing an average would be wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..db import Database

_NUMBER = r"\d+\s*/\s*\d+|\d+(?:[.,]\d+)?"
_RANGE_RE = re.compile(rf"^(?:{_NUMBER})\s*[-–—]\s*(?:{_NUMBER})\s*.*$")
_QUANTITY_RE = re.compile(rf"^({_NUMBER})\s*(.*)$")
_VULGAR_FRACTIONS = {
    "½": Decimal("0.5"),
    "¼": Decimal("0.25"),
    "¾": Decimal("0.75"),
    "⅓": Decimal(1) / Decimal(3),
    "⅔": Decimal(2) / Decimal(3),
    "⅛": Decimal("0.125"),
    "⅜": Decimal("0.375"),
    "⅝": Decimal("0.625"),
    "⅞": Decimal("0.875"),
}

_MASS = {"г", "гр", "грамм", "грамма", "граммов", "g"}
_KILOGRAMS = {"кг", "килограмм", "килограмма", "килограммов", "kg"}
_VOLUME = {"мл", "миллилитр", "миллилитра", "миллилитров", "ml"}
_LITRES = {"л", "литр", "литра", "литров", "l"}
_PIECES = {"шт", "штука", "штуки", "штук", "piece", "pieces"}
_CLOVES = {"зуб", "зубчик", "зубчика", "зубчиков", "clove", "cloves"}
_TABLESPOONS = {"ст. л", "ст.л", "столовая ложка", "столовые ложки"}
_TEASPOONS = {"ч. л", "ч.л", "чайная ложка", "чайные ложки"}
_PINCHES = {"щепот", "щепотка", "щепотки", "щепоток"}
_GLASSES = {"стак", "стакан", "стакана", "стаканов"}


@dataclass(frozen=True)
class QuantityValue:
    """Normalized amount and unit; both are ``None`` when the text is not numeric."""

    value: Decimal | None = None
    unit: str | None = None


def _number(raw: str) -> Decimal | None:
    value = raw.strip().replace(",", ".")
    if value in _VULGAR_FRACTIONS:
        return _VULGAR_FRACTIONS[value]
    if "/" in value:
        left, right = (part.strip() for part in value.split("/", 1))
        try:
            denominator = Decimal(right)
            return Decimal(left) / denominator if denominator else None
        except (InvalidOperation, ValueError):
            return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _unit(raw: str) -> tuple[str | None, Decimal]:
    """Return ``(canonical unit, multiplier)`` for a source unit."""
    original = " ".join(raw.split())
    lower = original.lower().rstrip(".")
    if lower in _MASS:
        return "г", Decimal(1)
    if lower in _KILOGRAMS:
        return "г", Decimal(1000)
    if lower in _VOLUME:
        return "мл", Decimal(1)
    if lower in _LITRES:
        return "мл", Decimal(1000)
    if lower in _PIECES:
        return "шт.", Decimal(1)
    if lower in _CLOVES:
        return "зуб.", Decimal(1)
    if lower in _TABLESPOONS:
        return "ст. л.", Decimal(1)
    if lower in _TEASPOONS:
        return "ч. л.", Decimal(1)
    if lower in _PINCHES:
        return "щепот.", Decimal(1)
    if lower in _GLASSES:
        return "стак.", Decimal(1)
    return (original or None), Decimal(1)


def parse_quantity(text: str | None) -> QuantityValue:
    """Parse one source amount; ranges and non-numeric text stay unnormalized."""
    if not text:
        return QuantityValue()
    normalized = " ".join(text.replace("\u00a0", " ").split())
    if not normalized or _RANGE_RE.match(normalized):
        return QuantityValue()
    match = _QUANTITY_RE.match(normalized)
    if not match:
        return QuantityValue()
    amount = _number(match.group(1))
    if amount is None:
        return QuantityValue()
    unit, multiplier = _unit(match.group(2))
    return QuantityValue(value=amount * multiplier, unit=unit)


def backfill_quantities(db: Database) -> int:
    """Fill the normalized columns of rows that currently have ``NULL`` values.

    The import writes them for new rows; this function upgrades rows imported before the
    migration without downloading the dataset again.  A row that cannot be normalized
    stays ``NULL`` and keeps its original ``quantity_text``.
    """
    rows = db.fetch_all(
        "SELECT id, quantity_text FROM recipe_ingredients "
        "WHERE quantity_value IS NULL AND quantity_unit IS NULL"
    )
    updated = 0
    with db.cursor() as cur:
        for row in rows:
            parsed = parse_quantity(row["quantity_text"])
            if parsed.value is None and parsed.unit is None:
                continue
            cur.execute(
                "UPDATE recipe_ingredients SET quantity_value = %s, quantity_unit = %s "
                "WHERE id = %s",
                (parsed.value, parsed.unit, row["id"]),
            )
            updated += 1
    return updated
