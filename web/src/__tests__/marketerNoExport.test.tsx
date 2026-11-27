/**
 * The marketer has no export (docs/system.md v1.25 §11; specs/019 US4, FR-014): nothing in the
 * marketer app leads to an export, on the phone or the large screen. Synthetic values only.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../lib/notifications', async (original) => ({
  ...(await original<typeof import('../lib/notifications')>()),
  unreadCount: vi.fn().mockResolvedValue({ count: 0 }),
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'مسوّق تجريبي', role: 'marketer', permissions: [] },
    refreshUser: vi.fn().mockResolvedValue(undefined),
  }),
}));

import MarketerLayout from '../layouts/MarketerLayout';

function setWidth(desktop: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: desktop && query.includes('min-width'),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    onchange: null,
    dispatchEvent: vi.fn(),
  }));
}

afterEach(cleanup);

describe('the marketer app (specs/019 US4)', () => {
  it.each([false, true])('has no export entry (desktop: %s)', async (desktop) => {
    setWidth(desktop);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Routes>
            <Route element={<MarketerLayout />}>
              <Route path="/" element={<p>صفحة تجريبية</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText('صفحة تجريبية')).toBeTruthy();
    expect(screen.getAllByText('الطلبات').length).toBeGreaterThan(0); // the navigation is there
    expect(screen.queryByText(/تصدير|التقارير/)).toBeNull();
    const links = screen.getAllByRole('link').map((a) => a.getAttribute('href') ?? '');
    expect(links.some((href) => /export|report/.test(href))).toBe(false);
  });
});
