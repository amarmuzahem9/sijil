/**
 * Submitted requests (specs/008 contracts/api.md): «إرسال», the marketer's list, and one request.
 * Errors arrive as ApiError with the server's Arabic message; the page shows it as is.
 */
import { apiFetch } from './api';
import { formatMoney } from './money';
import { clientId } from './drafts';
import type { RequestStatus } from './requestStatus';

export type SubmittedStatus = Exclude<RequestStatus, 'draft'>;
export type RequestType = 'new' | 'additional' | 'return';
export type RequestResultCode =
  | 'approved'
  | 'pending_family'
  | 'pending_review'
  | 'pending_approval'
  | 'rejected'
  | 'linked'
  // «محذوف» (specs/011 R11): only the number, type, status, tower and times are left.
  | 'deleted';

export interface SubmittedRequest {
  id: number;
  number: number;
  number_label: string;
  type: RequestType;
  status: SubmittedStatus;
  reasons: ('family_exists' | 'numbers_edited' | 'return' | 'numbers_conflict')[];
  /** Null fields below: a deleted request (`result` «deleted», specs/011 R11). */
  full_name: string | null;
  tower_code: string;
  /** Fixed at submission (system.md v1.12 §5). */
  tower_name: string;
  area_name: string | null;
  plan_name: string | null;
  trial_price: number | null;
  second_price: number | null;
  phone: string | null;
  /** «نسخ التفاصيل» (system.md v1.11 §5.5). */
  address: string | null;
  landmark: string | null;
  marketer_name: string | null;
  /** Null unless approved or linked. */
  username: string | null;
  submitted_at: string;
  approved_at: string | null;
  result: RequestResultCode;
  /** The admin's rejection (specs/010 FR-011): the fixed label, or the note for «سبب آخر». */
  rejection_reason: string | null;
  rejection_label: string | null;
  rejected_at: string | null;
  /** «محذوف» (specs/011): when, and the reason's Arabic name. */
  deleted_at?: string | null;
  deletion_label?: string | null;
  /** «رسالة الربط» composed by the server (system.md v1.17 §8.4): accepted or linked only. */
  link_message?: string | null;
}

export interface RequestListItem {
  id: number;
  number_label: string;
  /** Null on a deleted request. */
  full_name: string | null;
  status: SubmittedStatus;
  type: RequestType;
  submitted_at: string;
  tower_code: string;
  tower_name: string;
  rejection_label: string | null;
  deleted_at: string | null;
  deletion_label: string | null;
}

/** «PLUS | التجريبي … | الثاني …»; a deleted request has no prices (specs/011 R11). */
export function planLine(r: SubmittedRequest): string {
  if (r.trial_price === null || r.second_price === null) return r.plan_name ?? '—';
  return `${r.plan_name} | التجريبي ${formatMoney(r.trial_price)} | الثاني ${formatMoney(r.second_price)}`;
}

/** «نسخ التفاصيل» (system.md v1.11 §5.5): one line each, no phone, card numbers or images. */
export function requestDetailsText(r: SubmittedRequest): string {
  return [
    `رقم الطلب: #${r.number_label}`,
    `اسم المشترك: ${r.full_name}`,
    `البرج: ${r.tower_name} (${r.tower_code})`,
    `العنوان: ${r.address}، ${r.landmark}`,
    `اسم المستخدم: ${r.username ?? 'بانتظار الموافقة'}`,
    `الباقة: ${planLine(r)}`,
    `المسوّق: ${r.marketer_name}`,
  ].join('\n');
}

/** The screen after «إرسال» (FR-018). */
export const RESULT_TEXT: Record<RequestResultCode, string> = {
  approved: 'تمت الموافقة',
  pending_family: 'بانتظار موافقة المسؤول',
  pending_review: 'طلبك بانتظار التدقيق',
  // Return to service or a numbers conflict (specs/009).
  pending_approval: 'بانتظار موافقة المسؤول',
  rejected: 'تم رفض الطلب',
  linked: 'تم الربط',
  deleted: 'تم حذف الطلب',
};

/** The grey tag of a deleted request (§7.2 grey, specs/011 R11). */
export const DELETED_TAG = { label: 'محذوف', bg: '#eceff1', fg: '#455a64' } as const;

export const submitDraft = (draftId: string, version: number) =>
  apiFetch<SubmittedRequest>(`/api/drafts/${encodeURIComponent(draftId)}/submit`, {
    method: 'POST',
    body: { version },
    headers: { 'X-Client-Id': clientId },
  });

export function listRequests(statuses: SubmittedStatus[] = []) {
  const query = statuses.map((s) => `status=${encodeURIComponent(s)}`).join('&');
  return apiFetch<{ items: RequestListItem[] }>(`/api/requests${query ? `?${query}` : ''}`);
}

export const getRequest = (id: number | string) =>
  apiFetch<SubmittedRequest>(`/api/requests/${encodeURIComponent(String(id))}`);
