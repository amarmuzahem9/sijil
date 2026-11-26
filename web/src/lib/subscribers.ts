/**
 * «المشتركون» (docs/system.md v1.24 §10 item 4; specs/018 contracts/api.md): one search across
 * Sijil requests, legacy and SAS subscribers, and the read-only file of one record. Identity
 * numbers, card fields and images are absent (not null) for callers without `review`.
 */
import { apiFetch } from './api';
import type { HistoryKind, LinkReason, SubscriberSource } from './labels';

export type SearchKind =
  'number' | 'legacy_number' | 'national_id' | 'phone' | 'family' | 'username' | 'name';

export interface ResultRow {
  source: SubscriberSource;
  ref: string;
  number_label: string | null;
  legacy_number: string | null;
  full_name: string | null;
  tower_name: string | null;
  tower_code: string | null;
  phone: string | null;
  /** Request status, legacy status text, or the SAS expiry date «حسب آخر استيراد». */
  status: string | null;
  registered_at: string | null;
  /** A deleted request, found by its number only: every other field is null. */
  deleted: boolean;
}

export interface SearchResult {
  kind: SearchKind;
  items: ResultRow[];
  total: number;
}

export const SEARCH_PAGE_SIZE = 50;

export const searchSubscribers = (q: string, offset = 0) => {
  const params = new URLSearchParams({
    q,
    offset: String(offset),
    limit: String(SEARCH_PAGE_SIZE),
  });
  return apiFetch<SearchResult>(`/api/admin/subscribers?${params.toString()}`);
};

export interface HistoryEvent {
  kind: HistoryKind;
  at: string;
  by_name: string | null;
  reason?: string | null;
  /** Only for `review`: which number was pinned, never its value. */
  field?: string | null;
}

export interface SubscriberImage {
  id: string;
  side: 'front' | 'back';
}

/** One record of the file. Keys depend on the source and on the caller's permissions. */
export interface SubscriberRecord extends Omit<ResultRow, 'status' | 'number_label'> {
  number_label?: string | null;
  status: string | null;
  username?: string | null;
  type?: string | null;
  marketer_name?: string | null;
  // `review` and the main admin only.
  national_id?: string | null;
  family_number?: string | null;
  card_fields?: Record<string, string | null>;
  images?: SubscriberImage[];
  // legacy
  status_text?: string | null;
  counts_in_check?: boolean;
  extra?: Record<string, string | null>;
  incomplete?: boolean;
  // SAS
  expires_at?: string | null;
  group_name?: string | null;
  last_online_at?: string | null;
  missing_since?: string | null;
  username_phone?: string | null;
  no_documents?: boolean;
}

export interface LinkedRecord {
  reason: LinkReason;
  row: ResultRow;
}

export interface SubscriberFile {
  record: SubscriberRecord;
  history: HistoryEvent[];
  linked: LinkedRecord[];
  more_linked: number;
}

export const getSubscriberFile = (source: SubscriberSource, ref: string) =>
  apiFetch<SubscriberFile>(
    `/api/admin/subscribers/${encodeURIComponent(source)}/${encodeURIComponent(ref)}`,
  );
