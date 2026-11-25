/**
 * The backup warning on the main admin's home (specs/016 FR-017, SC-005). Other admins get an
 * empty list from the server, so they never see it.
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

describe('Home backup warning', () => {
  it('shows each warning and links to the backup page', async () => {
    getHome.mockResolvedValue({
      today: COUNTS,
      month: COUNTS,
      backup_warnings: ['last_failed', 'service_down'],
    });
    show();
    expect(await screen.findByText('فشل آخر نسخ احتياطي')).toBeTruthy();
    expect(screen.getByText('خدمة النسخ متوقفة')).toBeTruthy();
    const link = screen.getByRole('link', { name: 'صفحة النسخ الاحتياطي' });
    expect(link.getAttribute('href')).toBe('/admin/backup');
  });

  it('shows nothing when there is no warning', async () => {
    getHome.mockResolvedValue({ today: COUNTS, month: COUNTS, backup_warnings: [] });
    show();
    await screen.findByRole('region', { name: 'اليوم' });
    expect(screen.queryByRole('link', { name: 'صفحة النسخ الاحتياطي' })).toBeNull();
  });
});
