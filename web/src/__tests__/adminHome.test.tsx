/**
 * The admin home (specs/010 US5: FR-021): «اليوم» and «هذا الشهر», each with مرفوعة، مقبولة،
 * بالانتظار، تم الربط، مرفوضة. Counts only.
 */
import { cleanup, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { formatNumber } from '../lib/money';

const getHome = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  getHome: (...args: unknown[]) => getHome(...args),
}));

import AdminHome from '../pages/admin/Home';

beforeEach(() => {
  getHome.mockReset();
  getHome.mockResolvedValue({
    today: { submitted: 3, approved: 1, pending: 2, linked: 0, rejected: 1 },
    month: { submitted: 1240, approved: 1100, pending: 2, linked: 0, rejected: 40 },
  });
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AdminHome />
    </QueryClientProvider>,
  );
}

function tile(row: string, label: string) {
  return within(screen.getByRole('region', { name: row })).getByRole('group', { name: label });
}

describe('AdminHome', () => {
  it('shows today and this month with the five counts each', async () => {
    show();
    await screen.findByRole('region', { name: 'اليوم' });

    const today: [string, number][] = [
      ['مرفوعة', 3],
      ['مقبولة', 1],
      ['بالانتظار', 2],
      ['تم الربط', 0],
      ['مرفوضة', 1],
    ];
    for (const [label, n] of today)
      expect(tile('اليوم', label).textContent).toContain(formatNumber(n));

    expect(tile('هذا الشهر', 'مرفوعة').textContent).toContain(formatNumber(1240));
    expect(tile('هذا الشهر', 'مرفوضة').textContent).toContain(formatNumber(40));
  });

  it('says the times are Baghdad time', async () => {
    show();
    expect(await screen.findByText(/بتوقيت بغداد/)).toBeTruthy();
  });
});
