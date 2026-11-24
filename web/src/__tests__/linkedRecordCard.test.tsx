/**
 * A linked record that is a deleted request (specs/011 US4: FR-015, research R10): «سجل محذوف»
 * with its request number only; an unavailable one keeps «سجل غير متوفر». Synthetic values only.
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LinkedRecord, ReviewReason } from '../lib/adminRequests';
import { formatBaghdad } from '../lib/time';

const requestImageUrl = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  requestImageUrl: (...args: unknown[]) => requestImageUrl(...args),
}));

import { LinkedRecordCard } from '../pages/admin/pending/LinkedRecordCard';

afterEach(cleanup);

function record(partial: Partial<LinkedRecord>): LinkedRecord {
  return {
    source: 'sijil',
    ref: '5',
    available: false,
    full_name: null,
    username: null,
    phone: null,
    tower_code: null,
    tower_name: null,
    registered_at: null,
    status: null,
    image_ids: [],
    expiry: null,
    deleted: false,
    number_label: null,
    ...partial,
  };
}

function show(r: LinkedRecord) {
  const reason: ReviewReason = {
    reason: 'family_exists',
    state: 'open',
    added_at_review: false,
    basis: null,
    fields: [],
    record: r,
  };
  render(<LinkedRecordCard reason={reason} />);
}

describe('LinkedRecordCard', () => {
  it('shows «سجل محذوف» with the number and no fields or images', () => {
    show(record({ deleted: true, number_label: 'T3C-1005' }));
    expect(screen.getByText('سجل محذوف (#T3C-1005)')).toBeTruthy();
    expect(screen.queryByText('سجل غير متوفر')).toBeNull();
    expect(screen.queryByLabelText('الاسم')).toBeNull();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('keeps «سجل غير متوفر» for a record that is only unavailable', () => {
    show(record({ source: 'legacy' }));
    expect(screen.getByText('سجل غير متوفر')).toBeTruthy();
    expect(screen.queryByText(/سجل محذوف/)).toBeNull();
  });
});

describe('LinkedRecordCard for a legacy subscriber (specs/014 US3, T043)', () => {
  const legacy = () =>
    record({
      source: 'legacy',
      ref: '42',
      available: true,
      legacy_number: 'T3C-042',
      full_name: 'مشترك قديم للمراجعة',
      phone: '07811114242',
      registered_at: '2024-05-03T07:00:00Z',
      status: 'تم',
      incomplete: true,
      extra: { mother_name: 'عينة', mother_father_name: 'مثال', birth_date: '1990/01/10' },
      image_ids: ['img-front'],
    });

  beforeEach(() => {
    requestImageUrl.mockReset().mockResolvedValue('blob:legacy');
  });

  const field = (label: string) => (screen.getByLabelText(label) as HTMLTextAreaElement).value;

  it('shows «مشترك قديم», its number, form date, status text and «غير مكتمل»', () => {
    show(legacy());
    expect(screen.getByText('مشترك قديم')).toBeTruthy();
    expect(field('الرقم القديم')).toBe('T3C-042');
    expect(field('الاسم')).toBe('مشترك قديم للمراجعة');
    expect(field('الهاتف')).toBe('07811114242');
    expect(field('تاريخ الاستمارة')).toBe(formatBaghdad('2024-05-03T07:00:00Z'));
    expect(field('الحالة في الملف القديم')).toBe('تم');
    expect(screen.getByText('غير مكتمل')).toBeTruthy();
    // A legacy record has no username or tower, and «الحالة» is not a request status chip.
    expect(screen.queryByLabelText('اليوزر')).toBeNull();
    expect(screen.queryByLabelText('البرج')).toBeNull();
    // «تم» is only the field's value, never a status chip.
    expect(screen.queryAllByText('تم').filter((el) => el.tagName !== 'TEXTAREA')).toEqual([]);
  });

  it('shows «بيانات إضافية»', () => {
    show(legacy());
    expect(screen.getByText('بيانات إضافية')).toBeTruthy();
    expect(field('اسم الأم')).toBe('عينة');
    expect(field('اسم أب الأم')).toBe('مثال');
    expect(field('تاريخ الميلاد')).toBe('1990/01/10');
  });

  it('loads its images from the legacy image route', async () => {
    show(legacy());
    await waitFor(() => expect(requestImageUrl).toHaveBeenCalledWith('img-front', 'legacy'));
  });

  it('leaves Sijil records as they were', async () => {
    show(
      record({
        available: true,
        full_name: 'طلب سِجلّ',
        username: 'ALM03-07801110001',
        tower_code: 'ALM03',
        tower_name: 'العلم 3',
        image_ids: ['img-sijil'],
      }),
    );
    expect(field('اليوزر')).toBe('ALM03-07801110001');
    expect(screen.queryByText('مشترك قديم')).toBeNull();
    expect(screen.queryByText('بيانات إضافية')).toBeNull();
    await waitFor(() => expect(requestImageUrl).toHaveBeenCalledWith('img-sijil', 'request'));
  });
});
