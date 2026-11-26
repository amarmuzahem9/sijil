/**
 * Commissions (docs/system.md v1.23 §4.2, §9; specs/017 contracts/api.md). The server computes
 * every count, tier and amount; the web only formats them.
 */
import { apiFetch } from './api';
import { formatMoney, formatNumber } from './money';

/** «باقيلك {remaining} وتصير {rate} للمشترك»; null in the top tier. */
export interface NextTier {
  remaining: number;
  rate: number;
}

/** One finished month for the marketer: never who paid or when (FR-007). */
export interface PastMonth {
  month: string;
  month_label: string;
  count: number;
  without_commission: number;
  rate: number;
  amount: number;
  paid: boolean;
}

export const listPastMonths = () =>
  apiFetch<{ items: PastMonth[] }>('/api/marketer/commissions/months');

/** «عندك 27، باقيلك 3 وتصير 7,000 للمشترك». */
export function nextTierText(count: number, next: NextTier): string {
  return `عندك ${formatNumber(count)}، باقيلك ${formatNumber(next.remaining)} وتصير ${formatNumber(next.rate)} للمشترك`;
}

/** «30 × 7,000 د.ع = 210,000 د.ع». */
export function amountText(count: number, rate: number, amount: number): string {
  return `${formatNumber(count)} × ${formatMoney(rate)} = ${formatMoney(amount)}`;
}
