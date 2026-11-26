/**
 * «الأشهر السابقة» (docs/system.md v1.23 §4.2; specs/017 FR-007): finished months with their
 * count, «بلا عمولة», rate, amount and «تم الدفع» / «غير مدفوع». Never who paid.
 */
import { cleanup, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.fn();
vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

import PastMonths from '../pages/marketer/PastMonths';

beforeEach(() => apiFetch.mockReset());
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PastMonths />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PastMonths', () => {
  it('lists each month with its figures and payment state', async () => {
    apiFetch.mockResolvedValue({
      items: [
        {
          month: '2026-10',
          month_label: 'تشرين الأول 2026',
          count: 2,
          without_commission: 1,
          rate: 5000,
          amount: 10000,
          paid: false,
        },
        {
          month: '2026-09',
          month_label: 'أيلول 2026',
          count: 30,
          without_commission: 0,
          rate: 7000,
          amount: 210000,
          paid: true,
        },
      ],
    });
    show();
    expect(apiFetch).toHaveBeenCalledWith('/api/marketer/commissions/months');
    const rows = await screen.findAllByTestId('past-month');
    expect(rows).toHaveLength(2);

    const october = within(rows[0]);
    expect(october.getByText('تشرين الأول 2026')).toBeTruthy();
    expect(october.getByText('غير مدفوع')).toBeTruthy();
    expect(october.getByTestId('past-month-count').textContent).toBe('تم الربط: 2');
    expect(october.getByTestId('past-month-without').textContent).toBe('و 1 بلا عمولة');
    expect(october.getByTestId('past-month-amount').textContent).toBe('2 × 5,000 د.ع = 10,000 د.ع');

    const september = within(rows[1]);
    expect(september.getByText('تم الدفع')).toBeTruthy();
    expect(september.queryByTestId('past-month-without')).toBeNull();
    expect(september.getByTestId('past-month-amount').textContent).toBe(
      '30 × 7,000 د.ع = 210,000 د.ع',
    );
  });

  it('says when there is no past month', async () => {
    apiFetch.mockResolvedValue({ items: [] });
    show();
    expect(await screen.findByText('لا توجد أشهر سابقة')).toBeTruthy();
  });
});
