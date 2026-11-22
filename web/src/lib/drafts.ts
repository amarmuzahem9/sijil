/**
 * Drafts API (specs/005 contracts/api.md).
 *
 * Every draft call sends `X-Client-Id`: one random UUID per page load, kept in memory only and
 * never persisted (research.md R3). It lets the server tell a save from this page apart from a
 * save made on another device or in another tab of the same session.
 *
 * Card data is never written to localStorage or any other device storage (Principle II).
 */
import { ApiError, apiFetch } from './api';
import type { MissingItem } from './draftValidation';

export const clientId: string = crypto.randomUUID();

const draftHeaders = (): Record<string, string> => ({ 'X-Client-Id': clientId });

export type Side = 'front' | 'back';
export type LocationSource = 'gps' | 'map';

export interface DraftLocation {
  lat: number;
  lng: number;
  source: LocationSource;
  accuracy_m: number | null;
}

export interface DraftImage {
  id: string;
  size_bytes: number;
  width: number;
  height: number;
  created_at: string;
}

export interface DraftNotice {
  field: 'area_id' | 'tower_id' | 'plan_id';
  code: 'choice_unavailable' | 'price_changed';
  old?: { trial_price: number; second_price: number } | null;
  new?: { trial_price: number; second_price: number } | null;
}

export interface Draft {
  id: string;
  status: 'draft';
  version: number;
  created_at: string;
  updated_at: string;
  subscriber_name: string | null;
  national_id: string | null;
  family_number: string | null;
  location: DraftLocation | null;
  address: string | null;
  landmark: string | null;
  area_id: number | null;
  tower_id: number | null;
  plan_id: number | null;
  area_name: string | null;
  tower_code: string | null;
  plan_name: string | null;
  trial_price: number | null;
  second_price: number | null;
  phone_input: string | null;
  phone_normalized: string | null;
  images: { front: DraftImage | null; back: DraftImage | null };
  missing: MissingItem[];
  notices: DraftNotice[];
}

/** Partial update: an omitted key is unchanged, `null` clears. Prices are never sent. */
export interface DraftChanges {
  subscriber_name?: string | null;
  national_id?: string | null;
  family_number?: string | null;
  location?: DraftLocation | null;
  address?: string | null;
  landmark?: string | null;
  area_id?: number | null;
  tower_id?: number | null;
  plan_id?: number | null;
  phone_input?: string | null;
}

export interface DraftListItem {
  id: string;
  subscriber_name: string | null;
  tower_code: string | null;
  phone_normalized: string | null;
  updated_at: string;
  missing_count: number;
  has_images: boolean;
}

export interface DraftVersion {
  version: number;
  updated_at: string;
  same_client: boolean;
}

/** The 409 `draft_conflict` body carries the current version (contracts/api.md). */
export function conflictInfo(err: unknown): DraftVersion | null {
  if (!(err instanceof ApiError) || err.code !== 'draft_conflict') return null;
  const { version, updated_at, same_client } = err.extra as Partial<DraftVersion>;
  if (typeof version !== 'number') return null;
  return { version, updated_at: String(updated_at ?? ''), same_client: Boolean(same_client) };
}

const path = (id: string) => `/api/drafts/${encodeURIComponent(id)}`;

export const listDrafts = (q = '') =>
  apiFetch<{ items: DraftListItem[] }>(
    q.trim() ? `/api/drafts?q=${encodeURIComponent(q.trim())}` : '/api/drafts',
    { headers: draftHeaders() },
  );

/** Create-if-absent with a client UUID; a retried create never makes two drafts (R1). */
export const createDraft = (id: string, changes: DraftChanges) =>
  apiFetch<Draft>(path(id), { method: 'PUT', body: { changes }, headers: draftHeaders() });

export const getDraft = (id: string) => apiFetch<Draft>(path(id), { headers: draftHeaders() });

export const getDraftVersion = (id: string) =>
  apiFetch<DraftVersion>(`${path(id)}/version`, { headers: draftHeaders() });

export const patchDraft = (id: string, version: number, changes: DraftChanges) =>
  apiFetch<Draft>(path(id), {
    method: 'PATCH',
    body: { version, changes },
    headers: draftHeaders(),
  });

export const deleteDraft = (id: string) =>
  apiFetch<void>(path(id), { method: 'DELETE', headers: draftHeaders() });

/**
 * Upload one compressed card image with progress (research.md R6). Stub until T032: the real
 * version uses XMLHttpRequest because fetch has no upload progress events.
 */
export type UploadDraftImage = (
  id: string,
  side: Side,
  blob: Blob,
  onProgress: (fraction: number) => void,
) => Promise<Draft>;

export const uploadDraftImage: UploadDraftImage = () =>
  Promise.reject(new ApiError('not_implemented', 'رفع الصور غير متاح بعد', 0));
