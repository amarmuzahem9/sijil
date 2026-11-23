/**
 * The marketer dashboard (specs/009 US4, FR-005c; owner's Q3): «إضافة اشتراك لمشترك موجود» opens
 * the same subscriber form as «إضافة مشترك جديد». There is no search; the checks decide the path.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  apiFetch: vi.fn().mockResolvedValue({ linked_this_month: 0, month_label: 'تشرين الثاني' }),
}));

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
