/** Expiry rules of the fridge page, kept out of the components so they can be tested. */
export type FridgeStatus = 'fresh' | 'soon' | 'expired';

export const STATUS_LABELS: Record<FridgeStatus, string> = {
  fresh: 'Свежий',
  soon: 'Скоро истекает',
  expired: 'Просрочен',
};

const MONTHS = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
];

function startOfDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function parseDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/** Whole days between the expiry date and today: negative means already expired. */
export function daysUntil(expirationDate: string, today = new Date()): number {
  const oneDay = 24 * 60 * 60 * 1000;
  return Math.round(
    (startOfDay(parseDate(expirationDate)).getTime() - startOfDay(today).getTime()) / oneDay,
  );
}

/** Three states used by the badge and the summary cards. */
export function getFridgeStatus(expirationDate: string, today = new Date()): FridgeStatus {
  const days = daysUntil(expirationDate, today);
  if (days < 0) {
    return 'expired';
  }
  if (days <= 3) {
    return 'soon';
  }
  return 'fresh';
}

/** "27 ноября" — the same format for every card, independent of the browser locale. */
export function formatExpirationDate(expirationDate: string): string {
  const date = parseDate(expirationDate);
  return `${date.getDate()} ${MONTHS[date.getMonth()]}`;
}

function plural(value: number, one: string, few: string, many: string): string {
  const mod10 = value % 10;
  const mod100 = value % 100;
  if (mod10 === 1 && mod100 !== 11) {
    return one;
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return few;
  }
  return many;
}

/** "сегодня", "через 2 дня", "просрочен 3 дня назад" for the card hint. */
export function expirationHint(expirationDate: string, today = new Date()): string {
  const days = daysUntil(expirationDate, today);
  if (days === 0) {
    return 'сегодня';
  }
  if (days === 1) {
    return 'завтра';
  }
  if (days > 1) {
    return `через ${days} ${plural(days, 'день', 'дня', 'дней')}`;
  }
  const overdue = Math.abs(days);
  return `просрочен ${overdue} ${plural(overdue, 'день', 'дня', 'дней')} назад`;
}
