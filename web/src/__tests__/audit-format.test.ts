import { describe, expect, it } from 'vitest';

import type { AuditEntry } from '../lib/audit';
import { actionLabel, entryTargetLabel, formatAuditValue } from '../lib/auditFormat';
import { formatBaghdad } from '../lib/time';

function entry(partial: Partial<AuditEntry>): AuditEntry {
  return {
    id: 1,
    created_at: '2026-11-22T09:00:00Z',
    action: 'user.updated',
    actor: null,
    entity_type: 'user',
    entity_id: '1',
    target: null,
    target_label: null,
    before: null,
    after: null,
    ...partial,
  };
}

describe('entryTargetLabel (specs/004 T022)', () => {
  it('names the user for account entries', () => {
    const e = entry({ target: { id: 7, name: 'مسوّق تجريبي', role: 'marketer' } });
    expect(entryTargetLabel(e)).toBe('مسوّق تجريبي');
  });

  it('prefers the server label for settings items (entries store only changed fields)', () => {
    const e = entry({
      action: 'tower.deactivated',
      entity_type: 'tower',
      target_label: 'ALM01',
      before: { is_active: true },
      after: { is_active: false },
    });
    expect(entryTargetLabel(e)).toBe('ALM01');
  });

  it('falls back to the code of a tower and the name of an area or plan', () => {
    expect(
      entryTargetLabel(entry({ entity_type: 'tower', after: { code: 'ALM01', name: 'العلم 1' } })),
    ).toBe('ALM01');
    expect(entryTargetLabel(entry({ entity_type: 'area', after: { name: 'العلم' } }))).toBe(
      'العلم',
    );
    expect(entryTargetLabel(entry({ entity_type: 'plan', after: { name: 'PLUS' } }))).toBe('PLUS');
  });

  it('reads `before` for a delete', () => {
    const e = entry({ action: 'plan.deleted', entity_type: 'plan', before: { name: 'OLD' } });
    expect(entryTargetLabel(e)).toBe('OLD');
  });

  it('names the tier list and the general settings', () => {
    expect(entryTargetLabel(entry({ entity_type: 'reward_tiers' }))).toBe('شرائح المكافآت');
    expect(entryTargetLabel(entry({ entity_type: 'app_setting' }))).toBe('الإعدادات العامة');
  });
});

describe('formatAuditValue', () => {
  it('formats prices as money', () => {
    expect(formatAuditValue('second_price', 35000)).toBe('35,000 د.ع');
    expect(formatAuditValue('trial_price', 0)).toBe('0 د.ع');
  });

  it('formats a tier list', () => {
    const tiers = [
      { min_count: 0, rate: 5000 },
      { min_count: 30, rate: 7000 },
    ];
    expect(formatAuditValue('tiers', tiers)).toBe('0 → 5,000 د.ع، 30 → 7,000 د.ع');
  });

  it('keeps the account formatting', () => {
    expect(formatAuditValue('is_active', false)).toBe('موقوف');
    expect(formatAuditValue('archived', true)).toBe('نعم');
    expect(formatAuditValue('permissions', [])).toBe('بلا صلاحيات');
    expect(formatAuditValue('role', 'marketer')).toBe('مسوّق');
    expect(formatAuditValue('name', null)).toBe('—');
  });

  it('groups other numbers', () => {
    expect(formatAuditValue('otp_validity_minutes', 1440)).toBe('1,440');
  });
});

describe('actionLabel', () => {
  it('labels settings actions in Arabic', () => {
    expect(actionLabel(entry({ action: 'plan.updated' }))).toBe('تعديل فئة');
    expect(actionLabel(entry({ action: 'tower.deleted' }))).toBe('حذف برج');
  });

  it('names the role on account creation', () => {
    expect(actionLabel(entry({ action: 'user.created', after: { role: 'admin' } }))).toBe(
      'إنشاء حساب (أدمن)',
    );
  });
});

describe('draft deletion (specs/005 T044)', () => {
  const deleted = entry({
    action: 'draft.deleted',
    entity_type: 'draft',
    entity_id: '3f0c0000-0000-4000-8000-000000000000',
    before: {
      created_at: '2026-11-22T09:00:00Z',
      updated_at: '2026-11-22T09:30:00Z',
      tower_code: 'ALM01',
      image_count: 2,
      missing_count: 4,
    },
  });

  it('labels the action and the target', () => {
    expect(actionLabel(deleted)).toBe('حذف مسودة');
    expect(entryTargetLabel(deleted)).toBe('مسودة (ALM01)');
    expect(entryTargetLabel(entry({ entity_type: 'draft', before: { tower_code: null } }))).toBe(
      'مسودة',
    );
  });

  it('formats the stored times in Baghdad time', () => {
    expect(formatAuditValue('created_at', '2026-11-22T09:00:00Z')).toBe(
      formatBaghdad('2026-11-22T09:00:00Z'),
    );
  });
});

describe('submission (specs/008 T046)', () => {
  it('labels the two actions in Arabic', () => {
    expect(
      actionLabel(
        entry({
          action: 'request.submitted',
          entity_type: 'request',
          entity_id: '1001',
          after: { number: 1001, type: 'new', status: 'approved', reasons: [] },
        }),
      ),
    ).toBe('إرسال طلب');
    expect(
      actionLabel(
        entry({
          action: 'request.submit_refused',
          entity_type: 'draft',
          after: { reason: 'phone_used' },
        }),
      ),
    ).toBe('رفض إرسال طلب');
  });
});

describe('admin review (specs/010 T038)', () => {
  it('labels accept and reject, and an accept despite a warning', () => {
    expect(
      actionLabel(entry({ action: 'request.approved', after: { despite_warnings: [] } })),
    ).toBe('قبول طلب');
    expect(
      actionLabel(
        entry({ action: 'request.approved', after: { despite_warnings: ['same_person'] } }),
      ),
    ).toBe('قبول طلب رغم التحذير');
    expect(actionLabel(entry({ action: 'request.rejected' }))).toBe('رفض طلب');
  });

  it('shows the rejection reason and the warnings in Arabic', () => {
    expect(formatAuditValue('reason', 'under_15_days')).toBe(
      'المتبقي من الاشتراك الأول أقل من 15 يوماً',
    );
    expect(formatAuditValue('despite_warnings', ['same_person'])).toBe('نفس الشخص');
    expect(formatAuditValue('despite_warnings', [])).toBe('—');
    expect(formatAuditValue('counts_commission', false)).toBe('لا');
  });
});
