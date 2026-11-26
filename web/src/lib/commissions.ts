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

// --- the admin report (contracts/api.md) ---------------------------------------------------------

export interface PaymentInfo {
  paid_by_name: string | null;
  paid_at: string;
  /** The paid requests still linked in the month; lower after an undo. */
  count_today: number;
}

/** «تراجع بعد الدفع» (FR-015). */
export interface PaymentAlert {
  number_label: string;
  at: string;
  reason: string;
}

export interface ReportRow {
  marketer_id: number;
  marketer_name: string;
  count: number;
  without_commission: number;
  paid_before: number;
  tier_min_count: number;
  rate: number;
  amount: number;
  payable: boolean;
  payment: PaymentInfo | null;
  alerts: PaymentAlert[];
}

export interface CommissionReport {
  month: string;
  month_label: string;
  finished: boolean;
  total_amount: number;
  rows: ReportRow[];
}

/** A request behind a row: no phone, username, identity number or image (FR-010). */
export interface DetailLine {
  id: number;
  number_label: string;
  full_name: string | null;
  type: string;
  tower_name: string;
  tower_code: string;
  /** Null for a paid request undone later. */
  linked_at: string | null;
}

export interface CommissionDetail {
  counted: DetailLine[];
  without_commission: DetailLine[];
  paid_before: (DetailLine & { paid_month: string })[];
}

export const listMonths = () =>
  apiFetch<{ items: string[]; current: string }>('/api/admin/commissions/months');

export const getReport = (month: string) =>
  apiFetch<CommissionReport>(`/api/admin/commissions?month=${encodeURIComponent(month)}`);

/** «تم الدفع» with the figures the confirmation showed (research R5). */
export const payMonth = (month: string, marketerId: number, count: number, amount: number) =>
  apiFetch<ReportRow>(
    `/api/admin/commissions/${encodeURIComponent(month)}/marketers/${marketerId}/pay`,
    { method: 'POST', body: { count, amount } },
  );

export const getDetail = (month: string, marketerId: number) =>
  apiFetch<CommissionDetail>(
    `/api/admin/commissions/${encodeURIComponent(month)}/marketers/${marketerId}`,
  );
