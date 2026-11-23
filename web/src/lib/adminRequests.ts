/**
 * Admin review (specs/010 contracts/api.md): «طلبات بالانتظار», the request file and its images.
 * Only the main admin and admins with `review` get answers; the server checks (Principle IX).
 */
import { apiFetch, apiFetchBlob } from './api';
import type { RequestType } from './requests';
import type { DeletionReason } from './labels';
import type { RequestStatus } from './requestStatus';

export type ReasonCode = 'family_exists' | 'numbers_edited' | 'return' | 'numbers_conflict';
export type ReasonState = 'open' | 'resolved' | 'not_applicable';
export type ReturnBasis = 'identity' | 'phone';
export type ReviewWarning = 'same_person' | 'id_conflict' | 'return_target_lost';
export type RejectionReason =
  'card_unclear' | 'numbers_mismatch' | 'under_15_days' | 'active_subscription' | 'other';
export type PinField = 'national_id' | 'family_number';
export type PinSource = 'reading' | 'mrz' | 'marketer' | 'typed';

export interface PendingItem {
  id: number;
  number_label: string;
  type: RequestType;
  reasons: ReasonCode[];
  marketer_name: string;
  full_name: string;
  tower_code: string;
  tower_name: string;
  submitted_at: string;
}

export interface PendingList {
  total: number;
  items: PendingItem[];
}

export interface LinkedRecord {
  source: string;
  ref: string;
  available: boolean;
  full_name: string | null;
  username: string | null;
  phone: string | null;
  tower_code: string | null;
  tower_name: string | null;
  registered_at: string | null;
  status: string | null;
  image_ids: string[];
  /** SAS «حسب آخر استيراد» (014); null until then. */
  expiry: string | null;
}

export interface ReviewReason {
  reason: ReasonCode;
  state: ReasonState;
  added_at_review: boolean;
  basis: ReturnBasis | null;
  fields: PinField[];
  record: LinkedRecord | null;
}

export interface NumberPin {
  value: string;
  source: PinSource;
  by: string;
  at: string;
}

export interface NumberView {
  reading: string | null;
  mrz: string | null;
  marketer: string;
  current: string;
  edited: boolean;
  pins: NumberPin[];
}

export interface Decision {
  status: 'approved' | 'rejected';
  /** Null: the automatic approval. */
  by: string | null;
  at: string;
  counts_commission: boolean | null;
  despite_warnings: ReviewWarning[];
  reason: RejectionReason | null;
  label: string | null;
}

/** The deletion mark (specs/011 contracts/api.md). */
export interface DeletedMark {
  at: string;
  by_name: string;
  reason: DeletionReason;
}

/** A deleted request (`deleted` set) carries only the kept fields: every personal field is null
 * and names, images, numbers, linked records and warnings are empty (specs/011 R9). */
export interface RequestFile {
  id: number;
  number_label: string;
  type: RequestType;
  status: Exclude<RequestStatus, 'draft'>;
  names: Record<string, string | null>;
  names_reading: Record<string, string | null>;
  full_name: string | null;
  national_id: string | null;
  family_number: string | null;
  birth_date: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  birth_place: string | null;
  issuing_authority: string | null;
  images: { id: string; side: 'front' | 'back' }[];
  location: { lat: number; lng: number; source: string; accuracy_m: number | null } | null;
  address: string | null;
  landmark: string | null;
  area_name: string;
  tower_code: string;
  tower_name: string;
  plan_name: string;
  trial_price: number;
  second_price: number;
  phone: string | null;
  otp_verified_at: string;
  username: string | null;
  marketer_name: string;
  submitted_at: string;
  numbers: { national_id: NumberView; family_number: NumberView } | null;
  reasons: ReviewReason[];
  warnings: ReviewWarning[];
  decision: Decision | null;
  deleted: DeletedMark | null;
  /** «حذف» is offered: the caller holds `delete` and the request is pending or rejected. */
  can_delete: boolean;
}

export function listPending(reason?: ReasonCode) {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : '';
  return apiFetch<PendingList>(`/api/admin/requests/pending${query}`);
}

export const getRequestFile = (id: number | string) =>
  apiFetch<RequestFile>(`/api/admin/requests/${encodeURIComponent(String(id))}`);

/** An object URL for a request image; each fetch is logged on the server (§13). The caller
 * revokes it with URL.revokeObjectURL when done. */
export async function requestImageUrl(imageId: string): Promise<string> {
  const blob = await apiFetchBlob(`/api/admin/request-images/${encodeURIComponent(imageId)}`);
  return URL.createObjectURL(blob);
}

export interface AcceptBody {
  /** Only for a return (system.md §6.4). */
  counts_commission?: boolean;
  /** The warnings shown when «القبول رغم التحذير؟» was confirmed (research R7). */
  confirm_warnings?: ReviewWarning[];
}

export interface RejectBody {
  reason: RejectionReason;
  /** Only with «سبب آخر». */
  note?: string;
}

export const accept = (id: number, body: AcceptBody) =>
  apiFetch<RequestFile>(`/api/admin/requests/${id}/accept`, { method: 'POST', body });

export interface DeleteBody {
  reason: DeletionReason;
  /** The request number as typed; the server parses it again (specs/011 R6). */
  confirm_number: string;
}

/** «حذف مشترك»: the file in its deleted form. */
export const deleteRequest = (id: number, body: DeleteBody) =>
  apiFetch<RequestFile>(`/api/admin/requests/${id}/delete`, { method: 'POST', body });

export const reject = (id: number, body: RejectBody) =>
  apiFetch<RequestFile>(`/api/admin/requests/${id}/reject`, { method: 'POST', body });

export interface PinBody {
  field: PinField;
  source: PinSource;
  /** Only with `typed`; the server reads the other sources itself (research R4). */
  value?: string;
}

export const pin = (id: number, body: PinBody) =>
  apiFetch<RequestFile>(`/api/admin/requests/${id}/pin`, { method: 'POST', body });

export interface HomeCounts {
  submitted: number;
  approved: number;
  pending: number;
  linked: number;
  rejected: number;
}

/** The admin home counts, Baghdad days and months (specs/010 research R10). Any admin. */
export const getHome = () => apiFetch<{ today: HomeCounts; month: HomeCounts }>('/api/admin/home');
