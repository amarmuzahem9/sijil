/**
 * Import of the legacy Google Form subscribers (docs/system.md 1.19 §12.1; specs/014
 * contracts/api.md). Main admin or `reports` only. A preview is unsaved until «تأكيد الاستيراد».
 */
import { apiFetch } from './api';

export type FlagCode =
  | 'legacy_number_missing'
  | 'name_missing'
  | 'phone_invalid'
  | 'phone_missing'
  | 'family_missing'
  | 'family_length'
  | 'no_check_keys'
  | 'image_missing'
  | 'image_failed'
  | 'family_dup_file'
  | 'family_dup_legacy'
  | 'phone_dup_file'
  | 'phone_dup_legacy'
  | 'in_sijil'
  | 'legacy_number_dup_file'
  | 'already_imported';

export type FetchOutcome =
  'not_shared' | 'not_found' | 'too_large' | 'not_image' | 'timeout' | 'network';
export type Choice = 'import' | 'skip' | 'correct';

export interface LegacyFlag {
  code: FlagCode;
  rows?: number[];
  requests?: string[];
  side?: 'front' | 'back';
  outcome?: FetchOutcome;
}

export interface FlaggedRow {
  index: number;
  legacy_number: string | null;
  full_name: string;
  phone_file: string | null;
  phone: string | null;
  family_number_file: string | null;
  status_text: string | null;
  counts_in_check: boolean;
  flags: LegacyFlag[];
  allowed: Choice[];
  choice: Choice | null;
  corrected_family_number: string | null;
}

export interface LegacyPreview {
  id: string;
  status: 'fetching' | 'ready' | 'failed';
  file_name: string;
  expires_at: string;
  images_total: number;
  images_done: number;
  counts: {
    rows: number;
    ready: number;
    flagged: number;
    already_imported: number;
    not_counted: number;
    waiting_choice: number;
  };
  status_values: { value: string | null; rows: number; counts_in_check: boolean }[];
  flagged: FlaggedRow[];
}

export interface ImportSummary {
  import_id: number;
  rows: number;
  imported: number;
  skipped: number;
  already_imported: number;
  not_counted: number;
  incomplete: number;
  corrected: number;
  skipped_numbers: string[];
  incomplete_numbers: string[];
}

export interface ChoiceItem {
  index: number;
  choice: Choice;
  family_number?: string;
}

const BASE = '/api/admin/imports/legacy/previews';

export function uploadLegacyFile(file: File): Promise<LegacyPreview> {
  const form = new FormData();
  form.append('file', file, file.name);
  return apiFetch<LegacyPreview>(BASE, { method: 'POST', body: form });
}

export const getPreview = (id: string) =>
  apiFetch<LegacyPreview>(`${BASE}/${encodeURIComponent(id)}`);

/** «تخطي للكل» is this call with skip for every row of a group (system.md 1.19 §12.1). */
export const setChoices = (id: string, choices: ChoiceItem[]) =>
  apiFetch<LegacyPreview>(`${BASE}/${encodeURIComponent(id)}/choices`, {
    method: 'PUT',
    body: { choices },
  });

/** 409 `preview_changed` carries the updated preview in `extra.preview`. */
export const confirmImport = (id: string) =>
  apiFetch<ImportSummary>(`${BASE}/${encodeURIComponent(id)}/confirm`, { method: 'POST' });

export const cancelPreview = (id: string) =>
  apiFetch<void>(`${BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' });

// --- labels ---

export const FLAG_LABELS: Record<FlagCode, string> = {
  legacy_number_missing: 'رقم قديم مفقود أو غير صالح',
  name_missing: 'بلا اسم',
  phone_invalid: 'هاتف غير صالح',
  phone_missing: 'بلا هاتف',
  family_missing: 'بلا رقم عائلي',
  family_length: 'طول غير معتاد للرقم العائلي',
  no_check_keys: 'لا يشارك في الفحص',
  image_missing: 'صورة ناقصة',
  image_failed: 'تعذّر سحب الصورة',
  family_dup_file: 'رقم عائلي مكرر في الملف',
  family_dup_legacy: 'رقم عائلي عند مشترك قديم مستورد',
  phone_dup_file: 'هاتف مكرر في الملف',
  phone_dup_legacy: 'هاتف عند مشترك قديم مستورد',
  in_sijil: 'موجود في طلبات سِجلّ',
  legacy_number_dup_file: 'رقم قديم مكرر',
  already_imported: 'مستورد سابقاً',
};

/** Group order on the page: what blocks a row first, already imported last. */
export const FLAG_ORDER: FlagCode[] = [
  'legacy_number_missing',
  'name_missing',
  'legacy_number_dup_file',
  'in_sijil',
  'family_dup_file',
  'family_dup_legacy',
  'phone_dup_file',
  'phone_dup_legacy',
  'family_length',
  'family_missing',
  'phone_invalid',
  'phone_missing',
  'no_check_keys',
  'image_failed',
  'image_missing',
  'already_imported',
];

export const OUTCOME_LABELS: Record<FetchOutcome, string> = {
  not_shared: 'الملف غير مشترك',
  not_found: 'الملف غير موجود',
  too_large: 'الملف كبير جداً',
  not_image: 'ليس صورة صالحة',
  timeout: 'انتهت المهلة',
  network: 'خطأ في الاتصال',
};

const SIDE_LABELS = { front: 'الوجه', back: 'الظهر' } as const;

export const CHOICE_LABELS: Record<Choice, string> = {
  import: 'استيراد',
  skip: 'تخطي',
  correct: 'تصحيح',
};

/** One flag in Arabic, with its detail in brackets. */
export function flagText(flag: LegacyFlag): string {
  const label = FLAG_LABELS[flag.code] ?? flag.code;
  let detail: string | null = null;
  if (flag.rows?.length) detail = `مع الصف ${flag.rows.join('، ')}`;
  else if (flag.requests?.length) detail = flag.requests.join('، ');
  else if (flag.side && flag.outcome)
    detail = `${SIDE_LABELS[flag.side]}: ${OUTCOME_LABELS[flag.outcome] ?? flag.outcome}`;
  else if (flag.side) detail = SIDE_LABELS[flag.side];
  return detail ? `${label} (${detail})` : label;
}

export interface FlagGroup {
  code: FlagCode;
  rows: FlaggedRow[];
}

/** Each row once, under the first of its flags in FLAG_ORDER; its other flags show on the row. */
export function groupFlagged(rows: FlaggedRow[]): FlagGroup[] {
  const rank = (code: FlagCode) => {
    const i = FLAG_ORDER.indexOf(code);
    return i === -1 ? FLAG_ORDER.length : i;
  };
  const groups = new Map<FlagCode, FlaggedRow[]>();
  for (const row of rows) {
    if (row.flags.length === 0) continue;
    const first = [...row.flags].sort((a, b) => rank(a.code) - rank(b.code))[0].code;
    groups.set(first, [...(groups.get(first) ?? []), row]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([code, grouped]) => ({ code, rows: grouped }));
}
