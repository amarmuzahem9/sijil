/**
 * Request statuses and their fixed colors (docs/system.md §7.2, constitution Principle V: the
 * same color everywhere). `draft` since 005; `pending_review` and `approved` since 008; `rejected`
 * since 010; `linked` since 013 («تم الربط» and its undo).
 */
export type RequestStatus = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'linked';

export const STATUS_LABELS: Record<RequestStatus, string> = {
  draft: 'مسودة',
  pending_review: 'بانتظار المراجعة',
  // «مقبول (بانتظار الربط)» (§7.2, specs/012 FR-010).
  approved: 'مقبول (بانتظار الربط)',
  rejected: 'مرفوض',
  linked: 'تم الربط',
};

/** grey, orange, blue, red, green (§7.2). */
export const STATUS_COLORS: Record<RequestStatus, { bg: string; fg: string }> = {
  draft: { bg: '#eceff1', fg: '#455a64' },
  pending_review: { bg: '#fff3e0', fg: '#e65100' },
  approved: { bg: '#e3f2fd', fg: '#0d47a1' },
  rejected: { bg: '#ffebee', fg: '#b71c1c' },
  linked: { bg: '#e8f5e9', fg: '#1b5e20' },
};

/** Tabs of «الطلبات» in the order of §4.3. */
export const REQUEST_TABS = [
  { key: 'pending', label: 'بالانتظار' },
  { key: 'approved', label: 'مقبولة' },
  { key: 'linked', label: 'تم الربط' },
  { key: 'rejected', label: 'مرفوضة' },
  { key: 'drafts', label: 'مسودات' },
] as const;

export type RequestTab = (typeof REQUEST_TABS)[number]['key'];
