/**
 * «رسالة الربط» on the marketer's request page (specs/012 US1, FR-001, FR-006 to FR-008;
 * research R3). The server composes the text; the page shows it, copies it and opens WhatsApp
 * with it. Synthetic values only.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { whatsappUrl } from '../lib/linkMessage';
import type { SubmittedRequest } from '../lib/requests';
import { RequestResultView } from '../pages/marketer/RequestResult';

afterEach(cleanup);

const TEXT = [
  'طلب ربط جديد | رقم الطلب: #T3C-1001',
  'الاسم: تجربة اختبار نموذج مثال التجريبي',
  'الهاتف: 07801234567',
  'اليوزر: ALM03-07801234567',
  'البرج: برج العلم 3 (ALM03)',
  'الفئة: PLUS | التجريبي 20,000 د.ع | الثاني 35,000 د.ع',
  'العنوان: حي تجريبي، قرب نقطة تجريبية',
  'الموقع: https://maps.google.com/?q=34.7,43.68',
  'المسوّق: مسوّق تجريبي',
].join('\n');

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
    deleted_at: null,
    deletion_label: null,
    link_message: TEXT,
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

describe('whatsappUrl', () => {
  it('opens WhatsApp with the text and no recipient', () => {
    expect(whatsappUrl('أ\nب & ج')).toBe(`https://wa.me/?text=${encodeURIComponent('أ\nب & ج')}`);
  });
});

describe('«رسالة الربط» (system.md v1.17 §8.4)', () => {
  it('shows the server text for an accepted request', () => {
    show(request());
    expect(screen.getByText('رسالة الربط')).toBeTruthy();
    expect(screen.getByTestId('link-message-text').textContent).toBe(TEXT);
  });

  it('«نسخ رسالة الربط» copies the exact text and says «تم النسخ»', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    show(request());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'نسخ رسالة الربط' }));
    });
    expect(writeText).toHaveBeenCalledWith(TEXT);
    expect(screen.getByTestId('link-message-status').textContent).toBe('تم النسخ');
  });

  it('a failed copy leaves the text and asks to copy it by hand', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    Object.assign(navigator, { clipboard: { writeText } });
    show(request());
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'نسخ رسالة الربط' }));
    });
    expect(screen.getByTestId('link-message-status').textContent).toBe(
      'تعذّر النسخ، انسخ النص يدوياً',
    );
    expect(screen.getByTestId('link-message-text').textContent).toBe(TEXT);
  });

  it('«مشاركة بالواتساب» links to wa.me with the text, in a new tab', () => {
    show(request());
    const share = screen.getByRole('link', { name: 'مشاركة بالواتساب' });
    expect(share.getAttribute('href')).toBe(whatsappUrl(TEXT));
    expect(share.getAttribute('target')).toBe('_blank');
  });

  it('a linked request shows it too', () => {
    show(request({ status: 'linked', result: 'linked' }));
    expect(screen.getByTestId('link-message-text')).toBeTruthy();
  });

  it('«نسخ التفاصيل» stays next to it', () => {
    show(request());
    expect(screen.getByRole('button', { name: 'نسخ التفاصيل' })).toBeTruthy();
  });

  it.each([
    ['pending', { status: 'pending_review', result: 'pending_review', username: null }],
    [
      'rejected',
      { status: 'rejected', result: 'rejected', rejection_label: 'صورة البطاقة غير واضحة' },
    ],
    [
      'deleted',
      {
        status: 'pending_review',
        result: 'deleted',
        deleted_at: '2026-11-24T10:00:00Z',
        deletion_label: 'طلب مكرر',
      },
    ],
  ] as const)('no link message when %s', (_name, partial) => {
    show(request({ ...partial, link_message: null } as Partial<SubmittedRequest>));
    expect(screen.queryByText('رسالة الربط')).toBeNull();
    expect(screen.queryByRole('button', { name: 'نسخ رسالة الربط' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'مشاركة بالواتساب' })).toBeNull();
  });
});
