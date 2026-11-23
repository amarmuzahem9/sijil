/**
 * The review file (specs/010 US1: FR-003, FR-004): every section, the linked records with their
 * basis, an unavailable record, and an image that fails. Synthetic values only.
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

function section(title: string): HTMLElement {
  return screen.getByRole('region', { name: title });
}

describe('RequestReviewView', () => {
  it('shows the header with number, type and status', () => {
    show();
    expect(screen.getByRole('heading', { name: /T3C-1011/ })).toBeTruthy();
    expect(screen.getByText('النوع: اشتراك إضافي')).toBeTruthy();
    expect(screen.getByText('بانتظار المراجعة')).toBeTruthy();
  });

  it('shows the card section with names, numbers, dates and both images', async () => {
    show();
    const card = within(section('البطاقة'));
    expect(card.getByText('تجربة اختبار نموذج مثال التجريبي')).toBeTruthy();
    expect(card.getByText('199000000001')).toBeTruthy();
    expect(card.getByText('1234A5678901234567')).toBeTruthy();
    expect(card.getByText('بغداد')).toBeTruthy();
    expect(await card.findByRole('img', { name: 'وجه البطاقة' })).toBeTruthy();
    expect(card.getByRole('img', { name: 'ظهر البطاقة' })).toBeTruthy();
    expect(requestImageUrl).toHaveBeenCalledWith('img-front');
  });

  it('marks a name the marketer changed from the reading', () => {
    show();
    const card = within(section('البطاقة'));
    // great_grandfather_name was not read from the card.
    expect(card.getByText(/لم تقرأه البطاقة/)).toBeTruthy();
  });

  it('shows «الصورة غير متوفرة» when an image cannot be fetched', async () => {
    requestImageUrl.mockRejectedValue(new Error('404'));
    show();
    expect((await screen.findAllByText('الصورة غير متوفرة')).length).toBeGreaterThan(0);
  });

  it('shows location, subscription and phone', () => {
    show();
    const location = within(section('الموقع'));
    expect(location.getByText('حي تجريبي')).toBeTruthy();
    expect(location.getByText('قرب نقطة تجريبية')).toBeTruthy();
    const link = location.getByRole('link', { name: 'فتح على الخريطة' });
    expect(link.getAttribute('href')).toBe('https://maps.google.com/?q=34.7,43.68');

    const plan = within(section('الاشتراك'));
    expect(plan.getByText(/برج العلم 3/)).toBeTruthy();
    expect(plan.getByText(/20,000/)).toBeTruthy();
    expect(plan.getByText(/35,000/)).toBeTruthy();
    expect(plan.getByText('ALM03-07801234567')).toBeTruthy();

    const phone = within(section('الهاتف'));
    expect(phone.getByText('07801234567')).toBeTruthy();
  });

  it('lists the reasons with each linked record and its basis', () => {
    show();
    const reasons = within(section('الأسباب'));
    expect(reasons.getByText('عائلة موجودة')).toBeTruthy();
    expect(reasons.getByText('مشترك سابق تجريبي')).toBeTruthy();
    expect(reasons.getByText('ALM01-07709990001')).toBeTruthy();
    expect(reasons.getByText('سِجلّ')).toBeTruthy();
    expect(reasons.getByText('تم الربط')).toBeTruthy();
    expect(reasons.getByText('تعديل الأرقام')).toBeTruthy();
  });

  it('shows an unavailable record and the state of a reason that no longer applies', () => {
    show();
    const reasons = within(section('الأسباب'));
    expect(reasons.getByText('سجل غير متوفر')).toBeTruthy();
    expect(reasons.getByText('قديم')).toBeTruthy();
    expect(reasons.getByText('لم يعد ينطبق')).toBeTruthy();
  });
});
