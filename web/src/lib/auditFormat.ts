/**
 * Pure display helpers for «سجل العمليات» (specs/004 T022, research.md R6). Kept out of the page
 * so they can be unit-tested (analysis fix C2).
 */
import { ROLE_LABELS } from '../auth/roles';
import type { AuditEntry } from './audit';
import {
  DELETION_REASON_LABELS,
  AUDIT_ACTION_LABELS,
  PERMISSION_LABELS,
  PIN_FIELD_LABELS,
  PIN_SOURCE_LABELS,
  REASON_LABELS,
  REJECTION_REASON_LABELS,
  UNLINK_REASON_LABELS,
  REQUEST_TYPE_LABELS,
  WARNING_LABELS,
} from './labels';
import type { Permission } from './labels';
import { formatMoney, formatNumber } from './money';
import { STATUS_LABELS } from './requestStatus';
import { formatBaghdad } from './time';

// specs/017: the rate and amount of «تم الدفع» are money too.
const MONEY_FIELDS = new Set(['trial_price', 'second_price', 'rate', 'amount']);

function formatTiers(value: unknown[]): string {
  return value
    .map((tier) => {
      const t = tier as { min_count?: number; rate?: number };
      if (typeof t.min_count !== 'number' || typeof t.rate !== 'number') return String(tier);
      return `${formatNumber(t.min_count)} → ${formatMoney(t.rate)}`;
    })
    .join('، ');
}

/** One before/after value in Arabic. */
export function formatAuditValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (MONEY_FIELDS.has(field) && typeof value === 'number') return formatMoney(value);
  if (field === 'tiers' && Array.isArray(value)) return formatTiers(value);
  if (field === 'permissions' && Array.isArray(value)) {
    return value.length === 0
      ? 'بلا صلاحيات'
      : value.map((p) => PERMISSION_LABELS[p as Permission] ?? String(p)).join('، ');
  }
  if (field === 'is_active' && typeof value === 'boolean') return value ? 'فعّال' : 'موقوف';
  // specs/010: the rejection reason code and the warnings confirmed at accept.
  if (field === 'reason' && typeof value === 'string' && value in REJECTION_REASON_LABELS)
    return REJECTION_REASON_LABELS[value as keyof typeof REJECTION_REASON_LABELS];
  // specs/011: the deletion reason ('other' reads «سبب آخر» in both lists) and the status.
  if (field === 'reason' && typeof value === 'string' && value in DELETION_REASON_LABELS)
    return DELETION_REASON_LABELS[value as keyof typeof DELETION_REASON_LABELS];
  // specs/013: the reason of «التراجع عن الربط».
  if (field === 'reason' && typeof value === 'string' && value in UNLINK_REASON_LABELS)
    return UNLINK_REASON_LABELS[value as keyof typeof UNLINK_REASON_LABELS];
  if (field === 'status' && typeof value === 'string' && value in STATUS_LABELS)
    return STATUS_LABELS[value as keyof typeof STATUS_LABELS];
  if (field === 'despite_warnings' && Array.isArray(value)) {
    if (value.length === 0) return '—';
    return value
      .map((w) => WARNING_LABELS[w as keyof typeof WARNING_LABELS] ?? String(w))
      .join('، ');
  }
  // specs/010: a pin names the field, its source and the reasons it marked; never a value.
  if (field === 'field' && typeof value === 'string' && value in PIN_FIELD_LABELS)
    return PIN_FIELD_LABELS[value as keyof typeof PIN_FIELD_LABELS];
  if (field === 'source' && typeof value === 'string' && value in PIN_SOURCE_LABELS)
    return PIN_SOURCE_LABELS[value as keyof typeof PIN_SOURCE_LABELS];
  if (field === 'type' && typeof value === 'string' && value in REQUEST_TYPE_LABELS)
    return REQUEST_TYPE_LABELS[value as keyof typeof REQUEST_TYPE_LABELS];
  if ((field === 'reasons_added' || field === 'reasons_not_applicable') && Array.isArray(value)) {
    if (value.length === 0) return '—';
    return value.map((r) => REASON_LABELS[r as keyof typeof REASON_LABELS] ?? String(r)).join('، ');
  }
  if (field === 'role' && typeof value === 'string' && value in ROLE_LABELS) {
    return ROLE_LABELS[value as keyof typeof ROLE_LABELS];
  }
  if (
    (field === 'locked_until' || field === 'created_at' || field === 'updated_at') &&
    typeof value === 'string'
  )
    return formatBaghdad(value);
  if (typeof value === 'boolean') return value ? 'نعم' : 'لا';
  if (typeof value === 'number') return formatNumber(value);
  return String(value);
}

/** A value in its entry: the pin link of a deleted request reads «سجل محذوف» (specs/011 R12). */
export function formatEntryValue(entry: AuditEntry, field: string, value: unknown): string {
  if (field === 'pin_id' && entry.entity_deleted) return 'سجل محذوف';
  return formatAuditValue(field, value);
}

/** Arabic action label; account creation also names the role (002 analysis fix I3). */
export function actionLabel(entry: AuditEntry): string {
  const label = AUDIT_ACTION_LABELS[entry.action] ?? entry.action;
  const despite = entry.after?.despite_warnings;
  if (entry.action === 'request.approved' && Array.isArray(despite) && despite.length > 0)
    return `${label} رغم التحذير`;
  const role = entry.after?.role;
  if (entry.action === 'user.created' && typeof role === 'string' && role in ROLE_LABELS) {
    return `${label} (${ROLE_LABELS[role as keyof typeof ROLE_LABELS]})`;
  }
  return label;
}

/**
 * Who or what the entry is about: the user's name for account entries; for settings items the
 * server's `target_label`, else the label stored in `after` / `before` (tower → code, area/plan →
 * name). Settings entries store only changed fields, hence the server label first.
 */
export function entryTargetLabel(entry: AuditEntry): string | null {
  if (entry.entity_type === 'user') return entry.target?.name ?? null;
  if (entry.entity_type === 'reward_tiers') return 'شرائح المكافآت';
  if (entry.entity_type === 'commission_payment') {
    // The server names the marketer; the month is in the entry either way (specs/017 R10).
    if (entry.target_label) return entry.target_label;
    const month = entry.after?.month;
    return typeof month === 'string' ? `عمولة ${month}` : 'عمولة';
  }
  if (entry.entity_type === 'app_setting') return 'الإعدادات العامة';
  if (entry.entity_type === 'draft') {
    const tower = entry.before?.tower_code;
    return typeof tower === 'string' && tower ? `مسودة (${tower})` : 'مسودة';
  }
  if (entry.entity_type === 'legacy_import') {
    const file = entry.after?.file_name;
    return typeof file === 'string' ? file : 'استيراد المشتركين القدامى';
  }
  if (entry.target_label) return entry.target_label; // resolved by the server
  const values = { ...(entry.before ?? {}), ...(entry.after ?? {}) };
  const key = entry.entity_type === 'tower' ? 'code' : 'name';
  const label = values[key];
  return typeof label === 'string' ? label : null;
}
