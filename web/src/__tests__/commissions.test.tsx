/**
 * «العمولات» (docs/system.md v1.23 §9; specs/017 US2, FR-008 to FR-010): the month picker, the
 * rows, the total and the details of a row. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CommissionDetail, CommissionReport, ReportRow } from '../lib/commissions';

const listMonths = vi.fn();
const getReport = vi.fn();
const getDetail = vi.fn();
vi.mock('../lib/commissions', async (original) => ({
  ...(await original<typeof import('../lib/commissions')>()),
  listMonths: (...args: unknown[]) => listMonths(...args),
  getReport: (...args: unknown[]) => getReport(...args),
  getDetail: (...args: unknown[]) => getDetail(...args),
}));

import Commissions from '../pages/admin/commissions/Commissions';

const ROW: ReportRow = {
  marketer_id: 7,
  marketer_name: 'مسوّق تجريبي',
  count: 30,
  without_commission: 1,
  paid_before: 1,
  tier_min_count: 30,
  rate: 7000,
  amount: 210000,
  payable: true,
  payment: null,
  alerts: [],
};
const PAID: ReportRow = {
  ...ROW,
  marketer_id: 8,
  marketer_name: 'مسوّق ثانٍ تجريبي',
  count: 2,
  without_commission: 0,
  paid_before: 0,
  tier_min_count: 0,
  rate: 5000,
  amount: 10000,
  payable: false,
  payment: { paid_by_name: 'أدمن تجريبي', paid_at: '2026-11-02T08:00:00Z', count_today: 2 },
};

function report(month: string, rows: ReportRow[]): CommissionReport {
  return {
    month,
    month_label: month === '2026-11' ? 'تشرين الثاني 2026' : 'تشرين الأول 2026',
    finished: month !== '2026-11',
    total_amount: rows.reduce((n, r) => n + r.amount, 0),
    rows,
  };
}

const DETAIL: CommissionDetail = {
  counted: [
    {
      id: 42,
      number_label: 'T3C-1042',
      full_name: 'تجربة اختبار نموذج',
      type: 'new',
      tower_name: 'العلم 3',
      tower_code: 'ALM03',
      linked_at: '2026-10-03T09:00:00Z',
    },
  ],
  without_commission: [],
  paid_before: [
    {
      id: 40,
      number_label: 'T3C-1040',
      full_name: 'عينة اختبار',
      type: 'return',
      tower_name: 'العلم 3',
      tower_code: 'ALM03',
      linked_at: '2026-10-05T09:00:00Z',
      paid_month: '2026-09',
    },
  ],
};

beforeEach(() => {
  listMonths.mockReset();
  getReport.mockReset();
  getDetail.mockReset();
  listMonths.mockResolvedValue({ items: ['2026-11', '2026-10'], current: '2026-11' });
  getReport.mockImplementation((month: string) =>
    Promise.resolve(month === '2026-10' ? report(month, [ROW, PAID]) : report(month, [])),
  );
  getDetail.mockResolvedValue(DETAIL);
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Commissions />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function pickOctober() {
  fireEvent.mouseDown(await screen.findByLabelText('الشهر'));
  fireEvent.click(await screen.findByRole('option', { name: '2026-10' }));
}

describe('Commissions (specs/017 US2)', () => {
  it('opens on the current month', async () => {
    show();
    expect(await screen.findByText('لا يوجد ربط في هذا الشهر')).toBeTruthy();
    expect(getReport).toHaveBeenCalledWith('2026-11');
    expect(screen.getByTestId('commission-total').textContent).toBe('مجموع الشهر: 0 د.ع');
  });

  it('shows a row per marketer with its figures, state and the total', async () => {
    show();
    await pickOctober();
    const rows = await screen.findAllByTestId('commission-row');
    expect(rows).toHaveLength(2);
    const first = within(rows[0]);
    expect(first.getByText('مسوّق تجريبي')).toBeTruthy();
    expect(first.getByText('غير مدفوع')).toBeTruthy();
    expect(first.getByTestId('row-amount').textContent).toBe('30 × 7,000 د.ع = 210,000 د.ع');
    expect(first.getByTestId('row-extra').textContent).toBe('بلا عمولة: 1 · مدفوع سابقاً: 1');
    const second = within(rows[1]);
    expect(second.getByText('تم الدفع')).toBeTruthy();
    expect(second.getByTestId('row-paid').textContent).toContain('أدمن تجريبي');
    expect(screen.getByTestId('commission-total').textContent).toBe('مجموع الشهر: 220,000 د.ع');
  });

  it('opens the details of a row with its three lists', async () => {
    show();
    await pickOctober();
    const [first] = await screen.findAllByTestId('commission-row');
    fireEvent.click(within(first).getByRole('button', { name: 'التفاصيل' }));
    expect(getDetail).toHaveBeenCalledWith('2026-10', 7);
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('T3C-1042')).toBeTruthy();
    expect(within(dialog).getByText('المحسوبة (1)')).toBeTruthy();
    expect(within(dialog).getByText('بلا عمولة (0)')).toBeTruthy();
    expect(within(dialog).getByText('مدفوع سابقاً (1)')).toBeTruthy();
    expect(within(dialog).getByText('دُفع في 2026-09')).toBeTruthy();
    // No identity data in the dialog.
    expect(within(dialog).queryByText(/07\d{9}/)).toBeNull();
  });
});
