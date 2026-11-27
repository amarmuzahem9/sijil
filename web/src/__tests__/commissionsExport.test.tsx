/**
 * «تصدير» on «العمولات» (docs/system.md v1.25 §9; specs/019 US3, FR-015): the export of the chosen
 * month, saved as a file. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { CommissionReport } from '../lib/commissions';

const listMonths = vi.fn();
const getReport = vi.fn();
const exportMonth = vi.fn();
const saveBlob = vi.fn();
vi.mock('../lib/commissions', async (original) => ({
  ...(await original<typeof import('../lib/commissions')>()),
  listMonths: (...args: unknown[]) => listMonths(...args),
  getReport: (...args: unknown[]) => getReport(...args),
  exportMonth: (...args: unknown[]) => exportMonth(...args),
  saveBlob: (...args: unknown[]) => saveBlob(...args),
}));

import Commissions from '../pages/admin/commissions/Commissions';

function report(month: string): CommissionReport {
  return {
    month,
    month_label: month,
    finished: month !== '2026-11',
    total_amount: 10000,
    rows: [
      {
        marketer_id: 7,
        marketer_name: 'مسوّق تجريبي',
        count: 2,
        without_commission: 0,
        paid_before: 0,
        tier_min_count: 0,
        rate: 5000,
        amount: 10000,
        payable: true,
        payment: null,
        alerts: [],
      },
    ],
  };
}

beforeEach(() => {
  listMonths.mockReset();
  getReport.mockReset();
  exportMonth.mockReset();
  saveBlob.mockReset();
  listMonths.mockResolvedValue({ items: ['2026-11', '2026-10'], current: '2026-11' });
  getReport.mockImplementation((month: string) => Promise.resolve(report(month)));
  exportMonth.mockResolvedValue(new Blob(['synthetic']));
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

describe('«تصدير» of «العمولات» (specs/019 US3)', () => {
  it('exports the current month and saves the file', async () => {
    show();
    fireEvent.click(await screen.findByRole('button', { name: 'تصدير' }));
    await waitFor(() => expect(exportMonth).toHaveBeenCalledWith('2026-11'));
    await waitFor(() =>
      expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'sijil-commissions-2026-11.xlsx'),
    );
  });

  it('exports the month that was picked', async () => {
    show();
    fireEvent.mouseDown(await screen.findByLabelText('الشهر'));
    fireEvent.click(await screen.findByRole('option', { name: '2026-10' }));
    await waitFor(() => expect(getReport).toHaveBeenLastCalledWith('2026-10'));
    fireEvent.click(await screen.findByRole('button', { name: 'تصدير' }));
    await waitFor(() => expect(exportMonth).toHaveBeenCalledWith('2026-10'));
    await waitFor(() =>
      expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), 'sijil-commissions-2026-10.xlsx'),
    );
  });

  it('shows the Arabic answer of a refused export', async () => {
    exportMonth.mockRejectedValue(new ApiError('forbidden', 'ليست لديك صلاحية', 403));
    show();
    fireEvent.click(await screen.findByRole('button', { name: 'تصدير' }));
    expect(await screen.findByText('ليست لديك صلاحية')).toBeTruthy();
    expect(saveBlob).not.toHaveBeenCalled();
  });
});
