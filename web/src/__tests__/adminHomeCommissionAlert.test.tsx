/**
 * «يوجد تراجع بعد الدفع» on the admin home (docs/system.md v1.23 §9; specs/017 US4, FR-015): shown
 * while the server counts an undo after payment in the last 30 days. The server sends null to
 * admins without `commissions`.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const getHome = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  getHome: (...args: unknown[]) => getHome(...args),
}));

import AdminHome from '../pages/admin/Home';

const COUNTS = { submitted: 0, approved: 0, pending: 0, linked: 0, rejected: 0 };

beforeEach(() => getHome.mockReset());
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <AdminHome />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe('Home commission alert (specs/017 US4)', () => {
  it('warns and links to «العمولات» when there is an alert', async () => {
    getHome.mockResolvedValue({ today: COUNTS, month: COUNTS, commission_alerts: 2 });
    show();
    expect(await screen.findByText('يوجد تراجع بعد الدفع')).toBeTruthy();
    const link = screen.getByRole('link', { name: 'صفحة العمولات' });
    expect(link.getAttribute('href')).toBe('/admin/commissions');
  });

  it.each([0, null, undefined])('shows nothing for %s', async (value) => {
    getHome.mockResolvedValue({ today: COUNTS, month: COUNTS, commission_alerts: value });
    show();
    await screen.findByRole('region', { name: 'اليوم' });
    expect(screen.queryByText('يوجد تراجع بعد الدفع')).toBeNull();
  });
});
