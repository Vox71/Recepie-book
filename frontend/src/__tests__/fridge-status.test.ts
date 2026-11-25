import { describe, expect, it } from 'vitest';

import {
  daysUntil,
  expirationHint,
  formatExpirationDate,
  getFridgeStatus,
} from '../components/fridge/fridgeStatus';

const TODAY = new Date(2026, 10, 25, 12, 0, 0); // 25 November 2026, local noon

describe('fridge expiry rules', () => {
  it('counts whole days and classifies fresh, soon and expired products', () => {
    expect(daysUntil('2026-11-25', TODAY)).toBe(0);
    expect(daysUntil('2026-11-27', TODAY)).toBe(2);
    expect(daysUntil('2026-11-23', TODAY)).toBe(-2);

    expect(getFridgeStatus('2026-11-30', TODAY)).toBe('fresh');
    expect(getFridgeStatus('2026-11-28', TODAY)).toBe('soon');
    expect(getFridgeStatus('2026-11-25', TODAY)).toBe('soon');
    expect(getFridgeStatus('2026-11-24', TODAY)).toBe('expired');
  });

  it('formats the date and the hint in Russian', () => {
    expect(formatExpirationDate('2026-11-27')).toBe('27 ноября');

    expect(expirationHint('2026-11-25', TODAY)).toBe('сегодня');
    expect(expirationHint('2026-11-26', TODAY)).toBe('завтра');
    expect(expirationHint('2026-11-27', TODAY)).toBe('через 2 дня');
    expect(expirationHint('2026-11-26', new Date(2026, 10, 25, 12))).toBe('завтра');
    expect(expirationHint('2026-11-23', TODAY)).toBe('просрочен 2 дня назад');
    expect(expirationHint('2026-10-26', TODAY)).toBe('просрочен 30 дней назад');
    expect(expirationHint('2026-11-28', TODAY)).toBe('через 3 дня');
    expect(expirationHint('2026-11-30', TODAY)).toBe('через 5 дней');
    expect(expirationHint('2026-11-21', TODAY)).toBe('просрочен 4 дня назад');
    expect(expirationHint('2026-11-14', TODAY)).toBe('просрочен 11 дней назад');
  });
});
