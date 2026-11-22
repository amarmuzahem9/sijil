/**
 * Drafts API (specs/005 contracts/api.md).
 *
 * Every draft call sends `X-Client-Id`: one random UUID per page load, kept in memory only and
 * never persisted (research.md R3). It lets the server tell a save from this page apart from a
 * save made on another device or in another tab of the same session.
 *
 * Card data is never written to localStorage or any other device storage (Principle II).
 */
import {
  ApiError,
  apiErrorFrom,
  apiFetch,
  apiFetchBlob,
  getAccessToken,
  refreshSession,
  reportAuthError,
} from './api';
import type { MissingItem } from './draftValidation';
import type { NullableNames } from './nameFields';

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

export interface Draft extends NullableNames {
  id: string;
  status: 'draft';
  version: number;
  created_at: string;
  updated_at: string;
  /** Computed by the server from the first five names (R12). */
  full_name: string | null;
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

/** Partial update: an omitted key is unchanged, `null` clears. Prices and `full_name` are
 * never sent. */
export interface DraftChanges extends Partial<NullableNames> {
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
  full_name: string | null;
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

const UPLOAD_TIMEOUT_MS = 120_000; // a slow 3G-class connection (SC-003)

interface XhrResult {
  status: number;
  body: unknown;
}

function xhrUpload(
  url: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<XhrResult> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.timeout = UPLOAD_TIMEOUT_MS;
    xhr.responseType = 'json';
    const token = getAccessToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.setRequestHeader('X-Client-Id', clientId);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) onProgress(Math.min(1, e.loaded / e.total));
    };
    xhr.onload = () => resolve({ status: xhr.status, body: xhr.response });
    xhr.onerror = () => resolve({ status: 0, body: null });
    xhr.ontimeout = () => resolve({ status: 0, body: null });
    xhr.onabort = () => resolve({ status: 0, body: null });
    xhr.send(form);
  });
}

/**
 * Upload one compressed card image with progress (research.md R6). XMLHttpRequest because fetch
 * has no upload progress events. One automatic token refresh on 401 `token_expired`.
 */
export async function uploadDraftImage(
  id: string,
  side: Side,
  blob: Blob,
  onProgress: (fraction: number) => void,
): Promise<Draft> {
  const form = new FormData();
  form.append('file', blob, `${side}.jpg`);
  const url = `${path(id)}/images/${side}`;
  let result = await xhrUpload(url, form, onProgress);
  let err =
    result.status >= 200 && result.status < 300 ? null : apiErrorFrom(result.status, result.body);
  if (err?.code === 'token_expired') {
    await refreshSession();
    onProgress(0);
    result = await xhrUpload(url, form, onProgress);
    err =
      result.status >= 200 && result.status < 300 ? null : apiErrorFrom(result.status, result.body);
  }
  if (err) {
    reportAuthError(err);
    throw err;
  }
  return result.body as Draft;
}

/** A card image as an object URL for <img> (the bearer token cannot go in an img src).
 * The caller revokes it with URL.revokeObjectURL when done. */
export async function fetchImageObjectUrl(imageId: string): Promise<string> {
  const blob = await apiFetchBlob(`/api/draft-images/${encodeURIComponent(imageId)}`);
  return URL.createObjectURL(blob);
}
