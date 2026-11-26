/**
 * «المسوّقون»: this month's count and expected commission (docs/system.md v1.23 §10 item 5;
 * specs/017 US5, FR-019). No «تم الدفع» here. Synthetic values only.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const listAccounts = vi.fn();
vi.mock('../lib/accounts', async (original) => {
  const real = await original<typeof import('../lib/accounts')>();
  return {
    ...real,
    accountsApi: { ...real.accountsApi, list: (...a: unknown[]) => listAccounts(...a) },
  };
});
const getMonthSummary = vi.fn();
vi.mock('../lib/commissions', async (original) => ({
  ...(await original<typeof import('../lib/commissions')>()),
  getMonthSummary: (...args: unknown[]) => getMonthSummary(...args),
}));
vi.mock('../auth/AuthProvider', async (original) => ({
  ...(await original<typeof import('../auth/AuthProvider')>()),
  useAuth: () => ({ user: { id: 1, role: 'admin', permissions: ['marketers'] } }),
}));

import Marketers from '../pages/admin/Marketers';

const ACCOUNT = {
  id: 7,
  name: 'مسوّق تجريبي',
  phone: '07710000001',
  role: 'marketer',
  permissions: [],
  is_active: true,
  must_change_password: false,
  created_at: '2026-11-01T08:00:00Z',
};

beforeEach(() => {
  listAccounts.mockReset();
  getMonthSummary.mockReset();
  listAccounts.mockResolvedValue([
    ACCOUNT,
    { ...ACCOUNT, id: 8, name: 'مسوّق بلا ربط', phone: '07710000002' },
  ]);
  getMonthSummary.mockResolvedValue({
    month_label: 'تشرين الثاني 2026',
    items: [{ marketer_id: 7, count: 31, amount: 217000 }],
  });
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Marketers />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Marketers month count (specs/017 US5)', () => {
  it('shows the count and the expected commission of this month', async () => {
    show();
    expect(
      (await screen.findAllByText('عدد الشهر: 31 · العمولة المتوقعة: 217,000 د.ع')).length,
    ).toBeGreaterThan(0);
    expect(
      (await screen.findAllByText('عدد الشهر: 0 · العمولة المتوقعة: 0 د.ع')).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'تم الدفع' })).toBeNull();
  });
});
