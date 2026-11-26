/**
 * The marketer dashboard (specs/009 US4, FR-005c; owner's Q3): «إضافة اشتراك لمشترك موجود» opens
 * the same subscriber form as «إضافة مشترك جديد». There is no search; the checks decide the path.
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

const EMPTY = {
  linked_this_month: 0,
  linked_without_commission: 0,
  month_label: 'تشرين الثاني 2026',
  tier_rate: 5000,
  expected_amount: 0,
  next_tier: { remaining: 30, rate: 7000 } as { remaining: number; rate: number } | null,
  recent_links: [],
};

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue(EMPTY);
});

import Dashboard from '../pages/marketer/Dashboard';

afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Dashboard', () => {
  it('«إضافة اشتراك لمشترك موجود» is enabled and opens the same form', () => {
    show();
    const existing = screen.getByRole('link', { name: 'إضافة اشتراك لمشترك موجود' });
    const fresh = screen.getByRole('link', { name: 'إضافة مشترك جديد' });
    expect(existing.getAttribute('href')).toBe('/drafts/new');
    expect(existing.getAttribute('href')).toBe(fresh.getAttribute('href'));
    expect(existing.getAttribute('aria-disabled')).not.toBe('true');
    expect(screen.queryByText('قريباً')).toBeNull();
  });
});

describe('«تم الربط هذا الشهر» (specs/013 US2, FR-011, FR-014)', () => {
  it('shows the commission count and hides «بلا عمولة» at zero', async () => {
    apiFetch.mockResolvedValue({ ...EMPTY, linked_this_month: 27 });
    show();
    expect((await screen.findByTestId('linked-counter')).textContent).toBe(
      'تم الربط هذا الشهر: 27',
    );
    expect(screen.queryByText(/بلا عمولة/)).toBeNull();
    expect(screen.getByText('لا يوجد مشتركون مربوطون هذا الشهر')).toBeTruthy();
  });

  it('shows «و M بلا عمولة» under the count when M > 0', async () => {
    apiFetch.mockResolvedValue({ ...EMPTY, linked_this_month: 3, linked_without_commission: 2 });
    show();
    expect((await screen.findByTestId('linked-without-commission')).textContent).toBe(
      'و 2 بلا عمولة',
    );
  });

  it('lists the latest links with a green chip, each opening its request', async () => {
    apiFetch.mockResolvedValue({
      ...EMPTY,
      linked_this_month: 2,
      recent_links: [
        {
          id: 31,
          number_label: 'T3C-1031',
          full_name: 'عينة أولى',
          linked_at: '2026-11-24T09:00:00Z',
        },
        {
          id: 30,
          number_label: 'T3C-1030',
          full_name: 'عينة ثانية',
          linked_at: '2026-11-23T09:00:00Z',
        },
      ],
    });
    show();
    const list = await screen.findByTestId('recent-links');
    const links = within(list).getAllByRole('link');
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/requests/31', '/requests/30']);
    expect(within(links[0]).getByText('عينة أولى')).toBeTruthy();
    expect(within(links[0]).getByText('تم الربط')).toBeTruthy();
  });
});

describe('the tier and the expected amount (specs/017 US1, FR-006)', () => {
  it('shows the rate, the amount and «باقيلك»', async () => {
    apiFetch.mockResolvedValue({
      ...EMPTY,
      linked_this_month: 27,
      tier_rate: 5000,
      expected_amount: 135000,
      next_tier: { remaining: 3, rate: 7000 },
    });
    show();
    expect((await screen.findByTestId('tier-rate')).textContent).toBe(
      'الشريحة الحالية: 5,000 د.ع للمشترك',
    );
    expect(screen.getByTestId('expected-amount').textContent).toBe('المبلغ المتوقع: 135,000 د.ع');
    expect(screen.getByTestId('next-tier').textContent).toBe(
      'عندك 27، باقيلك 3 وتصير 7,000 للمشترك',
    );
  });

  it('hides «باقيلك» in the top tier', async () => {
    apiFetch.mockResolvedValue({
      ...EMPTY,
      linked_this_month: 50,
      tier_rate: 10000,
      expected_amount: 500000,
      next_tier: null,
    });
    show();
    expect((await screen.findByTestId('expected-amount')).textContent).toBe(
      'المبلغ المتوقع: 500,000 د.ع',
    );
    expect(screen.queryByTestId('next-tier')).toBeNull();
  });

  it('links to «الأشهر السابقة»', async () => {
    show();
    const link = await screen.findByRole('link', { name: 'الأشهر السابقة' });
    expect(link.getAttribute('href')).toBe('/commissions');
  });
});
