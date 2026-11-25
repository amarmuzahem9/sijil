/**
 * Import of the SAS subscribers (docs/system.md 1.20 §12.2; specs/015 contracts/api.md). Main
 * admin or `reports` only. A preview is unsaved until «تأكيد الاستيراد». No body here ever carries
 * a password: the server drops `ct_password` when it reads the file.
 */
import { apiFetch } from './api';

export type SasFlagCode = 'username_missing' | 'username_dup_file' | 'phone_in_sijil';
export type SasChoice = 'import' | 'skip';
export type SasKind = 'new' | 'update' | 'unchanged';

export interface SasFlag {
  code: SasFlagCode;
  rows?: number[];
  requests?: string[];
}

export interface SasFlaggedRow {
  index: number;
  sas_id: string | null;
  username: string | null;
  full_name: string;
  phone: string | null;
  username_phone: string | null;
  kind: SasKind;
  flags: SasFlag[];
  allowed: SasChoice[];
  choice: SasChoice | null;
}

export interface SasPrefix {
  prefix: string;
  rows: number;
  tower_id: number | null;
  from_previous: boolean;
  chosen: boolean;
}

export interface SasTower {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

export interface SasCounts {
  rows: number;
  new: number;
  update: number;
  unchanged: number;
  missing_from_file: number;
  flagged: number;
  waiting_choice: number;
  same_username_in_sijil: number;
  no_valid_phone: number;
  username_no_phone: number;
  date_unreadable: number;
  phone_dup_file: number;
  phone_in_legacy: number;
}

export interface SasPreview {
  id: string;
  file_name: string;
  expires_at: string;
  counts: SasCounts;
  prefixes: SasPrefix[];
  waiting_prefixes: number;
  towers: SasTower[];
  flagged: SasFlaggedRow[];
}

export interface SasImportSummary {
  import_id: number;
  rows: number;
  added: number;
  updated: number;
  unchanged: number;
  skipped: number;
  missing_marked: number;
  missing_cleared: number;
  without_phone: number;
  prefixes_mapped: number;
  skipped_rows: { index: number; sas_id: string | null }[];
}

export interface SasChoiceItem {
  index: number;
  choice: SasChoice;
}

/** `tower_id: null` is «بلا برج». */
export interface SasPrefixItem {
  prefix: string;
  tower_id: number | null;
}

const BASE = '/api/admin/imports/sas/previews';

export function uploadSasFile(file: File): Promise<SasPreview> {
  const form = new FormData();
  form.append('file', file, file.name);
  return apiFetch<SasPreview>(BASE, { method: 'POST', body: form });
}

export const getSasPreview = (id: string) =>
  apiFetch<SasPreview>(`${BASE}/${encodeURIComponent(id)}`);

/** «تخطي للكل» is this call with skip for every row of a group (system.md 1.20 §12.2). */
export const setSasChoices = (id: string, choices: SasChoiceItem[], prefixes: SasPrefixItem[]) =>
  apiFetch<SasPreview>(`${BASE}/${encodeURIComponent(id)}/choices`, {
    method: 'PUT',
    body: { choices, prefixes },
  });

/** 409 `preview_changed` carries the updated preview in `extra.preview`. */
export const confirmSasImport = (id: string) =>
  apiFetch<SasImportSummary>(`${BASE}/${encodeURIComponent(id)}/confirm`, { method: 'POST' });

export const cancelSasPreview = (id: string) =>
  apiFetch<void>(`${BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' });

// --- labels ---

export const SAS_FLAG_LABELS: Record<SasFlagCode, string> = {
  username_missing: 'بلا يوزر',
  username_dup_file: 'يوزر مكرر في الملف',
  phone_in_sijil: 'الهاتف في طلب سِجلّ',
};

/** Group order on the page: what can only be skipped first. */
export const SAS_FLAG_ORDER: SasFlagCode[] = [
  'username_missing',
  'username_dup_file',
  'phone_in_sijil',
];

export const SAS_KIND_LABELS: Record<SasKind, string> = {
  new: 'جديد',
  update: 'سيُحدَّث',
  unchanged: 'بلا تغيير',
};

/** The informational counts (no choice needed), in display order. */
export const SAS_INFO_LABELS: Partial<Record<keyof SasCounts, string>> = {
  missing_from_file: 'غير موجود في آخر ملف',
  same_username_in_sijil: 'نفس اليوزر في سِجلّ',
  no_valid_phone: 'بلا هاتف صالح',
  username_no_phone: 'يوزر بلا هاتف',
  date_unreadable: 'تاريخ غير مقروء',
  phone_dup_file: 'هاتف مكرر في الملف',
  phone_in_legacy: 'الهاتف عند مشترك قديم',
};

export const SAS_CHOICE_LABELS: Record<SasChoice, string> = {
  import: 'استيراد',
  skip: 'تخطي',
};

/** One flag in Arabic, with its detail in brackets. */
export function sasFlagText(flag: SasFlag): string {
  const label = SAS_FLAG_LABELS[flag.code] ?? flag.code;
  let detail: string | null = null;
  if (flag.rows?.length) detail = `مع الصف ${flag.rows.join('، ')}`;
  else if (flag.requests?.length) detail = flag.requests.join('، ');
  return detail ? `${label} (${detail})` : label;
}

export interface SasFlagGroup {
  code: SasFlagCode;
  rows: SasFlaggedRow[];
}

/** Each row once, under the first of its flags in SAS_FLAG_ORDER; its other flags show on it. */
export function groupSasFlagged(rows: SasFlaggedRow[]): SasFlagGroup[] {
  const rank = (code: SasFlagCode) => {
    const i = SAS_FLAG_ORDER.indexOf(code);
    return i === -1 ? SAS_FLAG_ORDER.length : i;
  };
  const groups = new Map<SasFlagCode, SasFlaggedRow[]>();
  for (const row of rows) {
    if (row.flags.length === 0) continue;
    const first = [...row.flags].sort((a, b) => rank(a.code) - rank(b.code))[0].code;
    groups.set(first, [...(groups.get(first) ?? []), row]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([code, grouped]) => ({ code, rows: grouped }));
}

export function towerLabel(tower: SasTower): string {
  return `${tower.name} (${tower.code})${tower.is_active ? '' : ' — موقوف'}`;
}
