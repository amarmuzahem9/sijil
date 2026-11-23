/**
 * The result screen after «إرسال» (specs/008 T026, T028; FR-018): the three texts, the number,
 * and the username only when approved, with «نسخ اليوزر». Synthetic values only.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { SubmittedRequest } from '../lib/requests';
import { RequestResultView } from '../pages/marketer/RequestResult';

afterEach(cleanup);

function request(partial: Partial<SubmittedRequest> = {}): SubmittedRequest {
  return {
    id: 1,
    number: 1001,
    number_label: 'T3C-1001',
    type: 'new',
    status: 'approved',
    reasons: [],
    full_name: 'تجربة اختبار نموذج مثال التجريبي',
    tower_code: 'ALM03',
    tower_name: 'برج العلم 3',
    area_name: 'العلم',
    plan_name: 'PLUS',
    trial_price: 20000,
    second_price: 35000,
    phone: '07801234567',
    address: 'حي تجريبي',
    landmark: 'قرب نقطة تجريبية',
    marketer_name: 'مسوّق تجريبي',
    username: 'ALM03-07801234567',
    submitted_at: '2026-11-23T10:00:00Z',
    approved_at: '2026-11-23T10:00:00Z',
    result: 'approved',
    rejection_reason: null,
    rejection_label: null,
    rejected_at: null,
    ...partial,
  };
}

function show(r: SubmittedRequest) {
  return render(
    <MemoryRouter>
      <RequestResultView request={r} />
    </MemoryRouter>,
  );
}

const DETAILS = [
  'رقم الطلب: #T3C-1001',
  'اسم المشترك: تجربة اختبار نموذج مثال التجريبي',
  'البرج: برج العلم 3 (ALM03)',
  'العنوان: حي تجريبي، قرب نقطة تجريبية',
  'اسم المستخدم: ALM03-07801234567',
  'الباقة: PLUS | التجريبي 20,000 د.ع | الثاني 35,000 د.ع',
  'المسوّق: مسوّق تجريبي',
].join('\n');

describe('«نسخ التفاصيل» (system.md v1.11 §5.5)', () => {
  it('copies the ordered Arabic text, one line each', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    show(request());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'نسخ التفاصيل' }));
    });
    expect(writeText).toHaveBeenCalledWith(DETAILS);
    expect(screen.getByText('تم النسخ')).toBeTruthy();
  });

  it('pending without a username: «بانتظار الموافقة», and no «نسخ اليوزر»', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    show(
      request({
        status: 'pending_review',
        result: 'pending_approval',
        type: 'return',
        reasons: ['return'],
        username: null,
        approved_at: null,
      }),
    );
    expect(screen.queryByRole('button', { name: 'نسخ اليوزر' })).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'نسخ التفاصيل' }));
    });
    expect(writeText).toHaveBeenCalledWith(
      DETAILS.replace('اسم المستخدم: ALM03-07801234567', 'اسم المستخدم: بانتظار الموافقة'),
    );
  });

  it('never copies the phone, a national ID or a family number', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    show(request({ username: null, status: 'pending_review', result: 'pending_review' }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'نسخ التفاصيل' }));
    });
    expect(writeText.mock.calls[0][0]).not.toContain('07801234567');
  });
});

describe('RequestResultView', () => {
  it('approved: «تمت الموافقة», the number and the username with a copy button', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    show(request());
    expect(screen.getByText('تمت الموافقة')).toBeTruthy();
    expect(screen.getByText('#T3C-1001')).toBeTruthy();
    expect(screen.getByTestId('request-username').textContent).toBe('ALM03-07801234567');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'نسخ اليوزر' }));
    });
    expect(writeText).toHaveBeenCalledWith('ALM03-07801234567');
    expect(screen.getByText('تم النسخ')).toBeTruthy();
  });

  it('family reason: «بانتظار موافقة المسؤول», no username', () => {
    show(
      request({
        type: 'additional',
        status: 'pending_review',
        reasons: ['family_exists'],
        result: 'pending_family',
        username: null,
        approved_at: null,
      }),
    );
    expect(screen.getByText('بانتظار موافقة المسؤول')).toBeTruthy();
    expect(screen.queryByTestId('request-username')).toBeNull();
    expect(screen.queryByRole('button', { name: 'نسخ اليوزر' })).toBeNull();
    expect(screen.getByText('#T3C-1001')).toBeTruthy();
  });

  it('return or numbers conflict: «بانتظار موافقة المسؤول», no username', () => {
    show(
      request({
        type: 'return',
        status: 'pending_review',
        reasons: ['return'],
        result: 'pending_approval',
        username: null,
        approved_at: null,
      }),
    );
    expect(screen.getByText('بانتظار موافقة المسؤول')).toBeTruthy();
    expect(screen.queryByTestId('request-username')).toBeNull();
  });

  it('edited numbers: «طلبك بانتظار التدقيق»', () => {
    show(
      request({
        status: 'pending_review',
        reasons: ['numbers_edited'],
        result: 'pending_review',
        username: null,
        approved_at: null,
      }),
    );
    expect(screen.getByText('طلبك بانتظار التدقيق')).toBeTruthy();
    expect(screen.queryByTestId('request-username')).toBeNull();
  });

  it('shows the status with its fixed label', () => {
    show(request({ status: 'pending_review', result: 'pending_review', username: null }));
    expect(screen.getByTestId('request-status').textContent).toBe('بانتظار المراجعة');
  });

  it('rejected: «تم رفض الطلب» with the reason, no username (specs/010 FR-011)', () => {
    show(
      request({
        status: 'rejected',
        result: 'rejected',
        username: null,
        approved_at: null,
        rejection_reason: 'other',
        rejection_label: 'طلب مكرر',
        rejected_at: '2026-11-23T11:00:00Z',
      }),
    );
    expect(screen.getByText('تم رفض الطلب')).toBeTruthy();
    expect(screen.getByTestId('rejection-label').textContent).toBe('طلب مكرر');
    expect(screen.getByTestId('request-status').textContent).toBe('مرفوض');
    expect(screen.queryByRole('button', { name: 'نسخ اليوزر' })).toBeNull();
  });
});
