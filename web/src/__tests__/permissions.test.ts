import { describe, expect, it } from 'vitest';
import { PERMISSION_LABELS, PERMISSIONS } from '../lib/labels';

// Mirrors api/app/core/access.py ADMIN_PERMISSIONS (specs/011 research R7).
describe('admin permissions', () => {
  it('lists «حذف مشترك» last, after the commissions', () => {
    expect(PERMISSIONS).toEqual([
      'review',
      'link',
      'settings',
      'marketers',
      'reports',
      'commissions',
      'delete',
    ]);
    expect(PERMISSION_LABELS.delete).toBe('حذف مشترك (طلب بالانتظار أو مرفوض)');
  });
});

describe('deletion reasons', () => {
  it('lists the four fixed reasons in order (api/app/core/deletion_reasons.py)', async () => {
    const { DELETION_REASON_LABELS } = await import('../lib/labels');
    expect(Object.entries(DELETION_REASON_LABELS)).toEqual([
      ['duplicate', 'طلب مكرر'],
      ['test', 'طلب تجريبي'],
      ['entry_error', 'خطأ إدخال'],
      ['other', 'سبب آخر'],
    ]);
  });
});
