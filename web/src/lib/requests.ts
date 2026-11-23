/**
 * Submitted requests (specs/008 contracts/api.md): «إرسال», the marketer's list, and one request.
 * Errors arrive as ApiError with the server's Arabic message; the page shows it as is.
 */
import { apiFetch } from './api';
import { clientId } from './drafts';
import type { RequestStatus } from './requestStatus';

export type SubmittedStatus = Exclude<RequestStatus, 'draft'>;
export type RequestType = 'new' | 'additional' | 'return';
export type RequestResultCode =
  'approved' | 'pending_family' | 'pending_review' | 'pending_approval' | 'rejected' | 'linked';

export interface SubmittedRequest {
  id: number;
  number: number;
  number_label: string;
  type: RequestType;
  status: SubmittedStatus;
  reasons: ('family_exists' | 'numbers_edited' | 'return' | 'numbers_conflict')[];
  full_name: string;
  tower_code: string;
  area_name: string;
  plan_name: string;
  trial_price: number;
  second_price: number;
  phone: string;
  /** Null unless approved or linked. */
  username: string | null;
  submitted_at: string;
  approved_at: string | null;
  result: RequestResultCode;
}

export interface RequestListItem {
  id: number;
  number_label: string;
  full_name: string;
  status: SubmittedStatus;
  type: RequestType;
  submitted_at: string;
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
};

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
