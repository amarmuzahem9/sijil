/**
 * «الإشعارات» (specs/012 US2, US4, US5: FR-018, FR-019, FR-021, FR-022; contracts/api.md).
 * The list, the titles per kind, tap = read + open the request, «تعليم الكل كمقروء», and a deleted
 * request's row without a name. Synthetic values only.
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { NotificationItem } from '../lib/notifications';

const api = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
  unreadCount: vi.fn(),
}));

vi.mock('../lib/notifications', async (original) => ({
  ...(await original<typeof import('../lib/notifications')>()),
  ...api,
}));

import { formatBaghdad } from '../lib/time';
import Notifications from '../pages/marketer/Notifications';

function item(partial: Partial<NotificationItem> = {}): NotificationItem {
  return {
    id: 7,
    kind: 'approved',
    request_id: 17,
    number_label: 'T3C-1017',
    full_name: 'تجربة اختبار نموذج',
    deleted: false,
    reason_label: null,
    created_at: '2026-11-24T09:12:00Z',
    read_at: null,
    ...partial,
  };
}

beforeEach(() => {
  api.markRead.mockResolvedValue(undefined);
  api.markAllRead.mockResolvedValue(undefined);
  api.unreadCount.mockResolvedValue({ count: 0 });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function show(items: NotificationItem[], next_before: number | null = null) {
  api.listNotifications.mockResolvedValue({ items, next_before });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/notifications']}>
        <Routes>
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/requests/:id" element={<p>صفحة الطلب</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('«الإشعارات»', () => {
  it.each([
    ['approved', 'تمت الموافقة على الطلب', null],
    ['rejected', 'تم رفض الطلب', 'صورة البطاقة غير واضحة'],
    ['linked', 'تم ربط المشترك', null],
    ['unlinked', 'تم التراجع عن الربط', 'خطأ بالربط'],
  ] as const)('%s: title, number, name, reason and Baghdad time', async (kind, title, reason) => {
    show([item({ kind, reason_label: reason })]);
    const row = await screen.findByTestId('notification-7');
    expect(row.textContent).toContain(title);
    expect(row.textContent).toContain('#T3C-1017');
    expect(row.textContent).toContain('تجربة اختبار نموذج');
    if (reason) expect(row.textContent).toContain(reason);
    expect(row.textContent).toContain(formatBaghdad('2026-11-24T09:12:00Z'));
  });

  it('unread and read rows look different', async () => {
    show([item(), item({ id: 8, read_at: '2026-11-24T10:00:00Z' })]);
    expect((await screen.findByTestId('notification-7')).getAttribute('data-unread')).toBe('true');
    expect(screen.getByTestId('notification-8').getAttribute('data-unread')).toBe('false');
  });

  it('tapping marks it read and opens the request', async () => {
    show([item()]);
    fireEvent.click(await screen.findByTestId('notification-7'));
    await screen.findByText('صفحة الطلب');
    expect(api.markRead).toHaveBeenCalledWith(7);
  });

  it('a read row opens the request without marking it again', async () => {
    show([item({ read_at: '2026-11-24T10:00:00Z' })]);
    fireEvent.click(await screen.findByTestId('notification-7'));
    await screen.findByText('صفحة الطلب');
    expect(api.markRead).not.toHaveBeenCalled();
  });

  it('«تعليم الكل كمقروء» marks every row read', async () => {
    show([item(), item({ id: 8 })]);
    await screen.findByTestId('notification-7');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'تعليم الكل كمقروء' }));
    });
    expect(api.markAllRead).toHaveBeenCalledTimes(1);
  });

  it('loads older notifications on demand', async () => {
    show([item()], 7);
    await screen.findByTestId('notification-7');
    api.listNotifications.mockResolvedValueOnce({ items: [item({ id: 3 })], next_before: null });
    fireEvent.click(screen.getByRole('button', { name: 'عرض الأقدم' }));
    await screen.findByTestId('notification-3');
    expect(api.listNotifications).toHaveBeenLastCalledWith(7);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'عرض الأقدم' })).toBeNull());
  });

  it('empty: «لا توجد إشعارات»', async () => {
    show([]);
    expect(await screen.findByText('لا توجد إشعارات')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'تعليم الكل كمقروء' })).toBeNull();
  });
});

describe('a deleted request (specs/012 US4)', () => {
  it('shows the number and «محذوف», no name, and still opens', async () => {
    show([
      item({ id: 9, kind: 'deleted', full_name: null, deleted: true, reason_label: 'طلب مكرر' }),
      item({ id: 7, kind: 'rejected', full_name: null, deleted: true, reason_label: 'سبب آخر' }),
    ]);
    const deleted = await screen.findByTestId('notification-9');
    expect(deleted.textContent).toContain('تم حذف الطلب');
    expect(deleted.textContent).toContain('#T3C-1017');
    expect(deleted.textContent).toContain('طلب مكرر');
    const older = screen.getByTestId('notification-7');
    expect(older.textContent).toContain('محذوف');
    expect(older.textContent).not.toContain('تجربة اختبار نموذج');
    fireEvent.click(older);
    await screen.findByText('صفحة الطلب');
  });
});
