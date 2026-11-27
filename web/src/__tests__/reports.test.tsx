/**
 * «التقارير والتصدير», the requests report (docs/system.md v1.25 §11; specs/019 US1, FR-003 to
 * FR-006, FR-016). Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { ReportOptions, ReportResult, ReportRow } from '../lib/reports';

const fetchReport = vi.fn();
const fetchOptions = vi.fn();
vi.mock('../lib/reports', async (original) => ({
  ...(await original<typeof import('../lib/reports')>()),
  fetchReport: (...args: unknown[]) => fetchReport(...args),
  fetchOptions: (...args: unknown[]) => fetchOptions(...args),
}));

import Reports from '../pages/admin/reports/Reports';

const OPTIONS: ReportOptions = {
  areas: [{ id: 1, name: 'منطقة تجريبية', active: true }],
  towers: [{ id: 3, code: 'ALM03', name: 'العلم 3', area_id: 1, active: true }],
  plans: [{ id: 2, name: 'فئة تجريبية', active: false }],
  marketers: [
    { id: 9, name: 'مسوّق تجريبي', archived: false, active: true },
    { id: 10, name: 'مسوّق مؤرشف', archived: true, active: false },
  ],
};

const ROW: ReportRow = {
  id: 42,
  number: 1042,
  number_label: 'T3C-1042',
  name: 'تجربة اختبار نموذج',
  deleted: false,
  tower: 'العلم 3 (ALM03)',
  plan: 'فئة تجريبية',
  marketer: 'مسوّق تجريبي',
  status: 'linked',
  type: 'new',
  submitted_at: '2026-11-02T09:00:00Z',
  linked_at: '2026-11-03T09:00:00Z',
};
const DELETED: ReportRow = {
  ...ROW,
  id: 43,
  number: 1043,
  number_label: 'T3C-1043',
  name: null,
  deleted: true,
  status: 'rejected',
  linked_at: null,
};

function result(rows: ReportRow[], total = rows.length): ReportResult {
  return {
    total,
    page: 1,
    page_size: 50,
    rows,
    summary: {
      by_status: [
        { status: 'linked', count: 1 },
        { status: 'rejected', count: 1 },
      ],
      by_tower: [{ tower_id: 3, tower: 'العلم 3 (ALM03)', count: 2 }],
      by_marketer: [{ marketer_id: 9, marketer: 'مسوّق تجريبي', count: 2 }],
    },
    can_export_identity: false,
  };
}

beforeEach(() => {
  fetchReport.mockReset();
  fetchOptions.mockReset();
  fetchOptions.mockResolvedValue(OPTIONS);
  fetchReport.mockResolvedValue(result([ROW, DELETED]));
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Reports />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const lastFilters = () => fetchReport.mock.lastCall?.[0] as Record<string, unknown>;
const lastPage = () => fetchReport.mock.lastCall?.[1] as number;

describe('Reports (specs/019 US1)', () => {
  it('opens on this month by submission date', async () => {
    show();
    await screen.findAllByTestId('report-row');
    expect(lastFilters()).toEqual({ period: 'month', date_kind: 'submitted' });
    expect(lastPage()).toBe(1);
  });

  it('switches the period and the date kind', async () => {
    show();
    await screen.findAllByTestId('report-row');
    fireEvent.click(screen.getByRole('button', { name: 'هذا الأسبوع' }));
    await waitFor(() => expect(lastFilters()).toMatchObject({ period: 'week' }));
    fireEvent.click(screen.getByRole('button', { name: 'تاريخ الربط' }));
    await waitFor(() => expect(lastFilters()).toMatchObject({ date_kind: 'linked' }));
  });

  it('asks for a range only when both days are set', async () => {
    show();
    await screen.findAllByTestId('report-row');
    fireEvent.click(screen.getByRole('button', { name: 'مدة محددة' }));
    const calls = fetchReport.mock.calls.length;
    fireEvent.change(screen.getByLabelText('من'), { target: { value: '2026-10-01' } });
    expect(fetchReport.mock.calls.length).toBe(calls);
    fireEvent.change(screen.getByLabelText('إلى'), { target: { value: '2026-10-31' } });
    await waitFor(() =>
      expect(lastFilters()).toEqual({
        period: 'range',
        from: '2026-10-01',
        to: '2026-10-31',
        date_kind: 'submitted',
      }),
    );
  });

  it('sends the chosen filters, archived marketers included', async () => {
    show();
    await screen.findAllByTestId('report-row');
    expect(screen.getByRole('option', { name: 'مسوّق مؤرشف (مؤرشف)' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('البرج'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('المسوّق'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('الحالة'), { target: { value: 'linked' } });
    fireEvent.change(screen.getByLabelText('النوع'), { target: { value: 'return' } });
    await waitFor(() =>
      expect(lastFilters()).toEqual({
        period: 'month',
        date_kind: 'submitted',
        tower_id: 3,
        marketer_id: 10,
        status: 'linked',
        type: 'return',
      }),
    );
    expect(lastPage()).toBe(1);
  });

  it('lists the rows with their status, and a deleted row without a name', async () => {
    show();
    const rows = await screen.findAllByTestId('report-row');
    expect(rows).toHaveLength(2);
    const first = within(rows[0]);
    expect(first.getByText('T3C-1042')).toBeTruthy();
    expect(first.getByText('تجربة اختبار نموذج')).toBeTruthy();
    expect(first.getByText('تم الربط')).toBeTruthy();
    expect(first.getByText('جديد')).toBeTruthy();
    expect(first.getByText(/العلم 3 \(ALM03\)/)).toBeTruthy();
    const link = rows[0].closest('a') ?? within(rows[0]).getByRole('link');
    expect(link.getAttribute('href')).toBe('/admin/subscribers/sijil/42');
    const deleted = within(rows[1]);
    expect(deleted.getByText('محذوف')).toBeTruthy();
    expect(deleted.getByText('مرفوض')).toBeTruthy();
    expect(deleted.queryByText('تجربة اختبار نموذج')).toBeNull();
  });

  it('shows the total and the three summaries, with no money', async () => {
    show();
    await screen.findAllByTestId('report-row');
    expect(screen.getByTestId('report-total').textContent).toBe('العدد: 2');
    const summary = within(screen.getByTestId('report-summary'));
    expect(summary.getByText('حسب الحالة')).toBeTruthy();
    expect(summary.getByText('حسب البرج')).toBeTruthy();
    expect(summary.getByText('حسب المسوّق')).toBeTruthy();
    expect(summary.getByText('مسوّق تجريبي')).toBeTruthy();
    expect(screen.queryByText(/د\.ع|المبلغ|العمولة/)).toBeNull();
  });

  it('pages with «التالي»', async () => {
    fetchReport.mockResolvedValue(result([ROW], 120));
    show();
    await screen.findAllByTestId('report-row');
    fireEvent.click(screen.getByRole('button', { name: 'التالي' }));
    await waitFor(() => expect(lastPage()).toBe(2));
    fireEvent.click(await screen.findByRole('button', { name: 'السابق' }));
    await waitFor(() => expect(lastPage()).toBe(1));
  });

  it('says when no request matches', async () => {
    fetchReport.mockResolvedValue(result([], 0));
    show();
    expect(await screen.findByText('لا توجد طلبات بهذه الفلاتر')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'تصدير' })).toBeNull();
  });

  it('shows the Arabic error of the server', async () => {
    fetchReport.mockRejectedValue(new ApiError('period_invalid', 'الفترة غير صحيحة', 422));
    show();
    expect(await screen.findByText('الفترة غير صحيحة')).toBeTruthy();
  });
});
