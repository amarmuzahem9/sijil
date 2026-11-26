/**
 * «تم الدفع» (docs/system.md v1.23 §9; specs/017 US3, FR-011, FR-012; research R5): the button
 * only on a payable row, the confirmation with the figures it sends, the Arabic refusals, and the
 * row turning «تم الدفع». Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { CommissionReport, ReportRow } from '../lib/commissions';

const listMonths = vi.fn();
const getReport = vi.fn();
const payMonth = vi.fn();
vi.mock('../lib/commissions', async (original) => ({
  ...(await original<typeof import('../lib/commissions')>()),
  listMonths: (...args: unknown[]) => listMonths(...args),
  getReport: (...args: unknown[]) => getReport(...args),
  payMonth: (...args: unknown[]) => payMonth(...args),
}));

import Commissions from '../pages/admin/commissions/Commissions';

const ROW: ReportRow = {
  marketer_id: 7,
  marketer_name: 'مسوّق تجريبي',
  count: 30,
  without_commission: 0,
  paid_before: 0,
  tier_min_count: 30,
  rate: 7000,
  amount: 210000,
  payable: true,
  payment: null,
  alerts: [],
};
const PAID_ROW: ReportRow = {
  ...ROW,
  payable: false,
  payment: { paid_by_name: 'أدمن تجريبي', paid_at: '2026-11-26T08:00:00Z', count_today: 30 },
};

function report(rows: ReportRow[]): CommissionReport {
  return {
    month: '2026-10',
    month_label: 'تشرين الأول 2026',
    finished: true,
    total_amount: rows.reduce((n, r) => n + r.amount, 0),
    rows,
  };
}

beforeEach(() => {
  listMonths.mockReset();
  getReport.mockReset();
  payMonth.mockReset();
  listMonths.mockResolvedValue({ items: ['2026-10'], current: '2026-10' });
  getReport.mockResolvedValue(report([ROW]));
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Commissions />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openDialog() {
  const [row] = await screen.findAllByTestId('commission-row');
  fireEvent.click(within(row).getByRole('button', { name: 'تم الدفع' }));
  return screen.findByRole('dialog');
}

describe('«تم الدفع» (specs/017 US3)', () => {
  it('confirms with the figures it sends, then shows the row paid', async () => {
    payMonth.mockResolvedValue(PAID_ROW);
    show();
    const dialog = await openDialog();
    expect(within(dialog).getByText('مسوّق تجريبي — 2026-10')).toBeTruthy();
    expect(within(dialog).getByTestId('pay-figures').textContent).toBe(
      '30 × 7,000 د.ع = 210,000 د.ع',
    );
    expect(within(dialog).getByText(/لا يمكن التراجع/)).toBeTruthy();

    getReport.mockResolvedValue(report([PAID_ROW]));
    fireEvent.click(within(dialog).getByRole('button', { name: 'تأكيد الدفع' }));
    await waitFor(() => expect(payMonth).toHaveBeenCalledWith('2026-10', 7, 30, 210000));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    const [row] = await screen.findAllByTestId('commission-row');
    await waitFor(() =>
      expect(within(row).getByTestId('row-paid').textContent).toContain('أدمن تجريبي'),
    );
    expect(within(row).queryByRole('button', { name: 'تم الدفع' })).toBeNull();
  });

  it('has no button on a row that is not payable', async () => {
    getReport.mockResolvedValue(report([{ ...ROW, payable: false }]));
    show();
    const [row] = await screen.findAllByTestId('commission-row');
    expect(within(row).queryByRole('button', { name: 'تم الدفع' })).toBeNull();
  });

  it.each([
    ['already_paid', 'تم تسجيل الدفع لهذا الشهر مسبقاً'],
    ['commission_changed', 'تغيّرت الأرقام، راجعها من جديد'],
    ['nothing_to_pay', 'لا يوجد عدد محسوب لهذا الشهر'],
    ['month_not_finished', 'لا يُسجَّل الدفع قبل نهاية الشهر'],
  ])('shows the Arabic message of %s and reloads the row', async (code, message) => {
    payMonth.mockRejectedValue(new ApiError(code, message, 409));
    show();
    const dialog = await openDialog();
    const calls = getReport.mock.calls.length;
    fireEvent.click(within(dialog).getByRole('button', { name: 'تأكيد الدفع' }));
    expect(await within(dialog).findByText(message)).toBeTruthy();
    await waitFor(() => expect(getReport.mock.calls.length).toBeGreaterThan(calls));
  });
});
