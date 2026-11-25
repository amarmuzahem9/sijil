/**
 * «النسخ الاحتياطي» (docs/system.md §10 item 10, §15; specs/016 contracts/api.md). Main admin
 * only. The page shows what the `backup` service recorded; a restore is a server operation and is
 * never offered here.
 */
import { apiFetch } from './api';

export type BackupKind = 'nightly' | 'manual' | 'pre_deploy' | 'pre_restore';
export type BackupWarning =
  | 'service_down'
  | 'no_key'
  | 'last_failed'
  | 'no_recent_backup'
  | 'disk_low'
  | 'drill_failed_or_overdue'
  | 'external_overdue';

export interface BackupRun {
  id: string;
  snapshot_id: string | null;
  kind: BackupKind;
  status: 'succeeded' | 'failed';
  error_code: string | null;
  started_at: string | null;
  finished_at: string | null;
  total_size: number | null;
  image_count: number | null;
  counts: Record<string, number> | null;
}

export interface BackupPage {
  status: {
    service_ok: boolean;
    heartbeat_at: string | null;
    nightly_at: string | null;
    free_bytes: number | null;
    total_bytes: number | null;
    min_free_bytes: number | null;
    backup_dir_bytes: number | null;
    external_dir: string;
    key_configured: boolean;
  };
  running: { id: string; kind: BackupKind; status: string; started_at: string | null } | null;
  runs: BackupRun[];
  last_external: { at: string; result: string; snapshot_id: string | null } | null;
  last_drill: {
    at: string;
    result: string;
    snapshot_id: string | null;
    source: string | null;
    reason: string | null;
  } | null;
  deploys: { at: string; result: string; mode: string | null; commit: string | null }[];
  warnings: BackupWarning[];
}

export const getBackupPage = () => apiFetch<BackupPage>('/api/admin/backup');
export const requestBackup = () =>
  apiFetch<{ id: string }>('/api/admin/backup/run', { method: 'POST' });

export const WARNING_TEXTS: Record<BackupWarning, string> = {
  service_down: 'خدمة النسخ متوقفة',
  no_key: 'لم يُضبط مفتاح النسخ',
  last_failed: 'فشل آخر نسخ احتياطي',
  no_recent_backup: 'لا توجد نسخة ناجحة منذ أكثر من 36 ساعة',
  disk_low: 'مساحة السيرفر قليلة',
  drill_failed_or_overdue: 'تجربة الاسترجاع فشلت أو متأخرة',
  external_overdue: 'النسخة الأسبوعية على الهارد الخارجي متأخرة',
};

export const KIND_LABELS: Record<BackupKind, string> = {
  nightly: 'ليلية',
  manual: 'يدوية',
  pre_deploy: 'قبل النشر',
  pre_restore: 'قبل الاسترجاع',
};

export const ERROR_TEXTS: Record<string, string> = {
  disk_low: 'المساحة غير كافية',
  missing_images: 'صور ناقصة',
  dump_failed: 'تعذّر نسخ قاعدة البيانات',
  encrypt_failed: 'تعذّر التشفير',
  verify_failed: 'فشل التحقق من النسخة',
  busy: 'كان يوجد نسخ آخر جارٍ',
  no_key: 'لم يُضبط مفتاح النسخ',
  internal: 'خطأ داخلي',
};

/** Bytes as «250 MB» / «1.5 GB», in the same Latin digits as `formatNumber`. */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = value >= 10 || unit === 0 ? 0 : 1;
  return `${value.toLocaleString('en-US', { maximumFractionDigits: digits })} ${units[unit]}`;
}
