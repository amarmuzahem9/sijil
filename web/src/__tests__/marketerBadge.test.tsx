/**
 * The unread count on «الإشعارات» (specs/012 FR-020, research R6): in the bottom bar and the side
 * bar, hidden at 0, asked again every 15 s while the app is open.
 */
import { act, cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ unreadCount: vi.fn() }));

vi.mock('../lib/notifications', async (original) => ({
  ...(await original<typeof import('../lib/notifications')>()),
  ...api,
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'مسوّق تجريبي', role: 'marketer', permissions: [] },
    refreshUser: vi.fn().mockResolvedValue(undefined),
  }),
}));

import MarketerLayout from '../layouts/MarketerLayout';
import { UNREAD_POLL_MS } from '../lib/notifications';

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

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route element={<MarketerLayout />}>
            <Route path="/" element={<p>الرئيسية</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => setWidth(false));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('the unread badge', () => {
  it.each([false, true])('shows the count (desktop: %s)', async (desktop) => {
    setWidth(desktop);
    api.unreadCount.mockResolvedValue({ count: 3 });
    show();
    expect((await screen.findByTestId('unread-badge')).textContent).toBe('3');
  });

  it('shows nothing at 0', async () => {
    api.unreadCount.mockResolvedValue({ count: 0 });
    show();
    await act(async () => {});
    expect(api.unreadCount).toHaveBeenCalled();
    expect(screen.queryByTestId('unread-badge')).toBeNull();
  });

  it('asks again every 15 s', async () => {
    expect(UNREAD_POLL_MS).toBe(15_000);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api.unreadCount.mockResolvedValueOnce({ count: 0 }).mockResolvedValue({ count: 2 });
    show();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(api.unreadCount).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UNREAD_POLL_MS);
    });
    expect(api.unreadCount).toHaveBeenCalledTimes(2);
    expect((await screen.findByTestId('unread-badge')).textContent).toBe('2');
  });
});
