/**
 * The marketer's notifications (docs/system.md v1.17 §4.4, specs/012 contracts/api.md).
 * A row holds no personal data: the subscriber's name comes from the request at read time and is
 * null once the request is deleted (011).
 */
import { apiFetch } from './api';

export type NotificationKind = 'approved' | 'rejected' | 'linked' | 'unlinked' | 'deleted';

export interface NotificationItem {
  id: number;
  kind: NotificationKind;
  request_id: number;
  number_label: string;
  full_name: string | null;
  deleted: boolean;
  /** The reason's fixed label (rejection, undo, deletion); never the reviewer's note. */
  reason_label: string | null;
  created_at: string;
  read_at: string | null;
}

export interface NotificationPage {
  items: NotificationItem[];
  next_before: number | null;
}

export const KIND_TITLES: Record<NotificationKind, string> = {
  approved: 'تمت الموافقة على الطلب',
  rejected: 'تم رفض الطلب',
  linked: 'تم ربط المشترك',
  unlinked: 'تم التراجع عن الربط',
  deleted: 'تم حذف الطلب',
};

/** The badge asks the server this often while the app is open (research R6). */
export const UNREAD_POLL_MS = 15_000;

export const notificationKeys = {
  all: ['notifications'] as const,
  list: ['notifications', 'list'] as const,
  unread: ['notifications', 'unread'] as const,
};

export function listNotifications(before?: number) {
  const query = before === undefined ? '' : `?before=${encodeURIComponent(before)}`;
  return apiFetch<NotificationPage>(`/api/notifications${query}`);
}

export const unreadCount = () => apiFetch<{ count: number }>('/api/notifications/unread-count');

export const markRead = (id: number) =>
  apiFetch<void>(`/api/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' });

export const markAllRead = () => apiFetch<void>('/api/notifications/read-all', { method: 'POST' });
