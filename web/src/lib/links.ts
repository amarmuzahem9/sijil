/**
 * «بانتظار الربط» (docs/system.md v1.18 §6.5, specs/013 contracts/api.md). The rows hold only what
 * SAS checking needs: no identity number, card field or image.
 */
import { apiFetch } from './api';
import type { UnlinkReason } from './labels';

export interface LinkRow {
  id: number;
  number_label: string;
  full_name: string | null;
  username: string | null;
  phone: string | null;
  tower_name: string;
  tower_code: string;
  plan_name: string;
  marketer_name: string;
  approved_at: string | null;
  /** The current link; null while waiting. */
  linked_at: string | null;
  linked_by_name: string | null;
  link_id: number | null;
}

export interface LinkList {
  items: LinkRow[];
  total: number;
}

export const LINK_PAGE_SIZE = 50;

function listQuery(q: string | undefined, offset: number): string {
  const params = new URLSearchParams({ offset: String(offset), limit: String(LINK_PAGE_SIZE) });
  if (q) params.set('q', q);
  return params.toString();
}

/** Accepted, not linked; the longest waiting first. */
export const listAwaiting = (q: string | undefined, offset: number) =>
  apiFetch<LinkList>(`/api/admin/links/awaiting?${listQuery(q, offset)}`);

/** Linked, newest link first (specs/013 US3). */
export const listRecent = (q: string | undefined, offset: number) =>
  apiFetch<LinkList>(`/api/admin/links/recent?${listQuery(q, offset)}`);

/** «تم الربط». 409 `already_linked` when another admin linked first. */
export const linkRequest = (id: number) =>
  apiFetch<LinkRow>(`/api/admin/requests/${id}/link`, { method: 'POST' });

export interface UnlinkBody {
  reason: UnlinkReason;
  /** The current link the page showed (specs/013 research R2). */
  link_id: number;
}

/** «التراجع عن الربط» (specs/013 US3). */
export const unlinkRequest = (id: number, body: UnlinkBody) =>
  apiFetch<LinkRow>(`/api/admin/requests/${id}/unlink`, { method: 'POST', body });
