import type { RecipeNutritionDto } from '../../api/recipes';

type QuantityKind = 'mass' | 'volume' | 'count' | 'other';

interface Unit {
  text: string;
  kind: QuantityKind;
  multiplier: number;
}

interface ParsedQuantity {
  amount: number;
  unit: Unit;
  rangeEnd: number | null;
}

const VULGAR_FRACTIONS: Record<string, number> = {
  '½': 0.5,
  '¼': 0.25,
  '¾': 0.75,
  '⅓': 1 / 3,
  '⅔': 2 / 3,
  '⅛': 0.125,
  '⅜': 0.375,
  '⅝': 0.625,
  '⅞': 0.875,
};

const MASS_UNITS = new Set(['г', 'гр', 'грамм', 'грамма', 'граммов', 'g']);
const VOLUME_UNITS = new Set(['мл', 'миллилитр', 'миллилитра', 'миллилитров', 'ml']);
const KILOGRAM_UNITS = new Set(['кг', 'килограмм', 'килограмма', 'килограммов', 'kg']);
const LITRE_UNITS = new Set(['л', 'литр', 'литра', 'литров', 'l']);
const PIECE_UNITS = new Set(['шт', 'штука', 'штуки', 'штук', 'piece', 'pieces']);
const CLOVE_UNITS = new Set(['зуб', 'зубчик', 'зубчика', 'зубчиков', 'clove', 'cloves']);
const TABLESPOON_UNITS = new Set(['ст. л', 'ст.л', 'столовая ложка', 'столовые ложки']);
const TEASPOON_UNITS = new Set(['ч. л', 'ч.л', 'чайная ложка', 'чайные ложки']);
const PINCH_UNITS = new Set(['щепот', 'щепотка', 'щепотки', 'щепоток']);
const GLASS_UNITS = new Set(['стак', 'стакан', 'стакана', 'стаканов']);

function parseNumber(raw: string): number | null {
  const value = raw.trim().replace(',', '.');
  if (value in VULGAR_FRACTIONS) {
    return VULGAR_FRACTIONS[value];
  }
  if (value.includes('/')) {
    const [left, right] = value.split('/').map(Number);
    return Number.isFinite(left) && Number.isFinite(right) && right !== 0 ? left / right : null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizeUnit(raw: string): Unit {
  const original = raw.trim().replace(/\s+/g, ' ');
  const lower = original.toLowerCase().replace(/\.$/, '');

  if (MASS_UNITS.has(lower)) {
    return { text: 'г', kind: 'mass', multiplier: 1 };
  }
  if (KILOGRAM_UNITS.has(lower)) {
    return { text: 'г', kind: 'mass', multiplier: 1000 };
  }
  if (VOLUME_UNITS.has(lower)) {
    return { text: 'мл', kind: 'volume', multiplier: 1 };
  }
  if (LITRE_UNITS.has(lower)) {
    return { text: 'мл', kind: 'volume', multiplier: 1000 };
  }
  if (PIECE_UNITS.has(lower)) {
    return { text: 'шт.', kind: 'count', multiplier: 1 };
  }
  if (CLOVE_UNITS.has(lower)) {
    return { text: 'зуб.', kind: 'count', multiplier: 1 };
  }
  if (TABLESPOON_UNITS.has(lower)) {
    return { text: 'ст. л.', kind: 'count', multiplier: 1 };
  }
  if (TEASPOON_UNITS.has(lower)) {
    return { text: 'ч. л.', kind: 'count', multiplier: 1 };
  }
  if (PINCH_UNITS.has(lower)) {
    return { text: 'щепот.', kind: 'count', multiplier: 1 };
  }
  if (GLASS_UNITS.has(lower)) {
    return { text: 'стак.', kind: 'count', multiplier: 1 };
  }
  return { text: original, kind: 'other', multiplier: 1 };
}

function parseLeadingAmount(text: string): { amount: number; rest: string } | null {
  const match = text.match(/^(\d+\s*\/\s*\d+|\d+(?:[.,]\d+)?|[½¼¾⅓⅔⅛⅜⅝⅞])\s*(.*)$/);
  if (!match) {
    return null;
  }
  const amount = parseNumber(match[1]);
  return amount === null ? null : { amount, rest: match[2] };
}

function parseQuantity(text: string): ParsedQuantity | null {
  const normalized = text.replace(/\u00a0/g, ' ').trim();
  if (!normalized) {
    return null;
  }

  const range = normalized.match(
    /^(\d+\s*\/\s*\d+|\d+(?:[.,]\d+)?|[½¼¾⅓⅔⅛⅜⅝⅞])\s*[-–—]\s*(\d+\s*\/\s*\d+|\d+(?:[.,]\d+)?|[½¼¾⅓⅔⅛⅜⅝⅞])\s*(.*)$/,
  );
  if (range) {
    const start = parseNumber(range[1]);
    const end = parseNumber(range[2]);
    if (start !== null && end !== null) {
      return { amount: start, rangeEnd: end, unit: normalizeUnit(range[3]) };
    }
  }

  const parsed = parseLeadingAmount(normalized);
  if (!parsed) {
    return null;
  }
  return { amount: parsed.amount, rangeEnd: null, unit: normalizeUnit(parsed.rest) };
}

function formatNumber(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return String(rounded).replace('.', ',');
}

function formatAmount(value: number, unit: Unit): string {
  if (unit.kind === 'mass') {
    return `${Math.round(value)} ${unit.text}`;
  }
  return `${formatNumber(value)} ${unit.text}`.trim();
}

/**
 * Scale one free-form ingredient amount.
 *
 * Mass becomes grams, litres become millilitres, and countable units stay countable.  An
 * amount without a leading number (`по вкусу`, `соль`) is returned unchanged: pretending
 * that it can be multiplied would be a lie.
 */
export function scaleQuantity(text: string | null, factor: number): string {
  if (!text || !Number.isFinite(factor) || factor <= 0) {
    return text || '—';
  }

  const parsed = parseQuantity(text);
  if (!parsed) {
    return text;
  }

  const amount = parsed.amount * parsed.unit.multiplier * factor;
  if (parsed.rangeEnd !== null) {
    const end = parsed.rangeEnd * parsed.unit.multiplier * factor;
    return `${formatNumber(amount)}–${formatAmount(end, parsed.unit)}`;
  }
  return formatAmount(amount, parsed.unit);
}

export interface ScaledNutrition {
  caloriesTotal: number | null;
  proteinTotal: number | null;
  fatTotal: number | null;
  carbsTotal: number | null;
  caloriesPer100g: number | null;
  proteinPer100g: number | null;
  fatPer100g: number | null;
  carbsPer100g: number | null;
  caloriesPerServing: number | null;
  proteinPerServing: number | null;
  fatPerServing: number | null;
  carbsPerServing: number | null;
}

function scaleValue(value: number | null, factor: number): number | null {
  return value === null ? null : Math.round(value * factor * 10) / 10;
}

function perServing(value: number | null, servings: number): number | null {
  return value === null ? null : Math.round((value / servings) * 10) / 10;
}

/** Scale the totals of a recipe and derive the values per chosen serving. */
export function scaleNutrition(
  nutrition: RecipeNutritionDto | null,
  factor: number,
  servings: number,
): ScaledNutrition | null {
  if (!nutrition) {
    return null;
  }
  const caloriesTotal = scaleValue(nutrition.calories_total, factor);
  const proteinTotal = scaleValue(nutrition.protein_total, factor);
  const fatTotal = scaleValue(nutrition.fat_total, factor);
  const carbsTotal = scaleValue(nutrition.carbs_total, factor);
  return {
    caloriesTotal,
    proteinTotal,
    fatTotal,
    carbsTotal,
    caloriesPer100g: nutrition.calories_per_100g,
    proteinPer100g: nutrition.protein_per_100g,
    fatPer100g: nutrition.fat_per_100g,
    carbsPer100g: nutrition.carbs_per_100g,
    caloriesPerServing: perServing(caloriesTotal, servings),
    proteinPerServing: perServing(proteinTotal, servings),
    fatPerServing: perServing(fatTotal, servings),
    carbsPerServing: perServing(carbsTotal, servings),
  };
}

/** Display a nullable nutrition value with its unit. */
export function formatNutritionValue(value: number | null, unit: string): string {
  return value === null ? '—' : `${formatNumber(value)} ${unit}`;
}
