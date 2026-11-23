/**
 * The review file (specs/010 US1: FR-003, FR-004): every section, the linked records with their
 * basis, an unavailable record, and an image that fails. Every value sits in a read-only box like
 * the form's inputs, with notes under the box (owner's request). Synthetic values only.
 */
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const requestImageUrl = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  requestImageUrl: (...args: unknown[]) => requestImageUrl(...args),
}));

import { RequestReviewView } from '../pages/admin/pending/RequestReview';
import { requestFile } from './fixtures/requestFile';

beforeEach(() => {
  requestImageUrl.mockReset();
  requestImageUrl.mockResolvedValue('blob:fake');
});
afterEach(cleanup);

function show(file = requestFile()) {
  render(
    <MemoryRouter>
      <RequestReviewView file={file} />
    </MemoryRouter>,
  );
}

function section(title: string) {
  return within(screen.getByRole('region', { name: title }));
}

/** The read-only box labelled `label` inside `scope`, with its value. */
function box(scope: ReturnType<typeof within>, label: string) {
  const el = scope.getByLabelText(label) as HTMLInputElement | HTMLTextAreaElement;
  expect(el.readOnly).toBe(true);
  return el;
}

describe('RequestReviewView', () => {
  it('shows the header with number, type and status', () => {
    show();
    expect(screen.getByRole('heading', { name: /T3C-1011/ })).toBeTruthy();
    expect(screen.getByText('النوع: اشتراك إضافي')).toBeTruthy();
    expect(screen.getByText('بانتظار المراجعة')).toBeTruthy();
  });

  it('shows the card values in read-only boxes, in the grid, and both images', async () => {
    show();
    const card = section('البطاقة');
    expect(box(card, 'الاسم الكامل').value).toBe('تجربة اختبار نموذج مثال التجريبي');
    expect(box(card, 'الرقم الوطني').value).toBe('199000000001');
    expect(box(card, 'الرقم العائلي').value).toBe('1234A5678901234567');
    expect(box(card, 'محل الولادة').value).toBe('بغداد');
    expect(box(card, 'تاريخ الولادة').value).toBe('1990-01-01');
    expect(card.getAllByTestId('readonly-fields').length).toBeGreaterThan(0);
    expect(await card.findByRole('img', { name: 'وجه البطاقة' })).toBeTruthy();
    expect(card.getByRole('img', { name: 'ظهر البطاقة' })).toBeTruthy();
    expect(requestImageUrl).toHaveBeenCalledWith('img-front');
  });

  it('puts «لم تقرأه البطاقة» under the box of a name the card did not read', () => {
    show();
    const card = section('البطاقة');
    const field = box(card, 'اسم أب الجد');
    const note = card.getByText('لم تقرأه البطاقة');
    expect(field.getAttribute('aria-describedby')).toBe(note.id);
  });

  it('shows «الصورة غير متوفرة» when an image cannot be fetched', async () => {
    requestImageUrl.mockRejectedValue(new Error('404'));
    show();
    expect((await screen.findAllByText('الصورة غير متوفرة')).length).toBeGreaterThan(0);
  });

  it('shows location, subscription and phone in read-only boxes', () => {
    show();
    const location = section('الموقع');
    expect(box(location, 'العنوان').value).toBe('حي تجريبي');
    expect(box(location, 'أقرب نقطة دالّة').value).toBe('قرب نقطة تجريبية');
    expect(box(location, 'الإحداثيات').value).toBe('34.7, 43.68');
    const link = location.getByRole('link', { name: 'فتح على الخريطة' });
    expect(link.getAttribute('href')).toBe('https://maps.google.com/?q=34.7,43.68');

    const plan = section('الاشتراك');
    expect(box(plan, 'البرج').value).toBe('برج العلم 3 (ALM03)');
    expect(box(plan, 'الفئة').value).toMatch(/20,000.*35,000/);
    expect(box(plan, 'اليوزر').value).toBe('ALM03-07801234567');

    const phone = section('الهاتف');
    expect(box(phone, 'هاتف الاشتراك').value).toBe('07801234567');
  });

  it('lists the reasons with each linked record in read-only boxes and its basis', () => {
    show();
    const reasons = section('الأسباب');
    expect(reasons.getByText('عائلة موجودة')).toBeTruthy();
    expect(box(reasons, 'الاسم').value).toBe('مشترك سابق تجريبي');
    expect(box(reasons, 'اليوزر').value).toBe('ALM01-07709990001');
    expect(reasons.getByText('سِجلّ')).toBeTruthy();
    expect(reasons.getByText('تم الربط')).toBeTruthy();
    expect(reasons.getByText('تعديل الأرقام')).toBeTruthy();
  });

  it('shows an unavailable record and the state of a reason that no longer applies', () => {
    show();
    const reasons = section('الأسباب');
    expect(reasons.getByText('سجل غير متوفر')).toBeTruthy();
    expect(reasons.getByText('قديم')).toBeTruthy();
    expect(reasons.getByText('لم يعد ينطبق')).toBeTruthy();
  });
});
