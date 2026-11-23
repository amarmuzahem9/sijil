/**
 * Pure display helpers for «سجل العمليات» (specs/004 T022, research.md R6). Kept out of the page
 * so they can be unit-tested (analysis fix C2).
 */
import { ROLE_LABELS } from '../auth/roles';
import type { AuditEntry } from './audit';
import {
  AUDIT_ACTION_LABELS,
  PERMISSION_LABELS,
  REJECTION_REASON_LABELS,
  WARNING_LABELS,
} from './labels';
import type { Permission } from './labels';
import { formatMoney, formatNumber } from './money';
import { formatBaghdad } from './time';

const MONEY_FIELDS = new Set(['trial_price', 'second_price']);

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
  if (field === 'despite_warnings' && Array.isArray(value)) {
    if (value.length === 0) return '—';
    return value
      .map((w) => WARNING_LABELS[w as keyof typeof WARNING_LABELS] ?? String(w))
      .join('، ');
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
  if (entry.entity_type === 'app_setting') return 'الإعدادات العامة';
  if (entry.entity_type === 'draft') {
    const tower = entry.before?.tower_code;
    return typeof tower === 'string' && tower ? `مسودة (${tower})` : 'مسودة';
  }
  if (entry.target_label) return entry.target_label; // resolved by the server
  const values = { ...(entry.before ?? {}), ...(entry.after ?? {}) };
  const key = entry.entity_type === 'tower' ? 'code' : 'name';
  const label = values[key];
  return typeof label === 'string' ? label : null;
}
