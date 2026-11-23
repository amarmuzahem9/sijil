/**
 * The request file and «حذف مشترك» (specs/011 US1: FR-002, FR-017; research R9): the «حذف» button
 * follows `can_delete`, and a deleted file shows the banner and the kept fields only.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RequestReviewView } from '../pages/admin/pending/RequestReview';
import { deletedRequestFile, requestFile } from './fixtures/requestFile';

afterEach(cleanup);

function show(file = requestFile(), onDelete = vi.fn()) {
  render(
    <MemoryRouter>
      <RequestReviewView file={file} onDelete={onDelete} decision={<div>منطقة القرار</div>} />
    </MemoryRouter>,
  );
  return onDelete;
}

describe('«حذف» on the request file', () => {
  it('is shown when the file allows it, and asks for the dialog', () => {
    const onDelete = show(requestFile({ can_delete: true }));
    fireEvent.click(screen.getByRole('button', { name: 'حذف' }));
    expect(onDelete).toHaveBeenCalled();
  });

  it('is hidden without `can_delete` (no `delete`, or an accepted request)', () => {
    show(requestFile({ can_delete: false }));
    expect(screen.queryByRole('button', { name: 'حذف' })).toBeNull();
  });
});

describe('a deleted request file', () => {
  it('shows the banner with who, when and the reason', () => {
    show(deletedRequestFile());
    const banner = screen.getByRole('status');
    expect(banner.textContent).toContain('تم حذف بيانات هذا الطلب');
    expect(banner.textContent).toContain('أدمن الحذف');
    expect(banner.textContent).toContain('طلب مكرر');
    // 2026-11-24T09:30:00Z is ١٢:٣٠ in Baghdad (UTC+3).
    expect(banner.textContent).toContain('١٢:٣٠');
  });

  it('keeps the number, the tower, the plan and the reasons, and hides everything else', () => {
    show(deletedRequestFile());
    expect(screen.getByRole('heading', { name: /T3C-1011/ })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'الاشتراك' })).toBeTruthy();
    expect(screen.getByRole('region', { name: 'الأسباب' })).toBeTruthy();
    for (const title of ['البطاقة', 'الموقع', 'الهاتف', 'تثبيت الأرقام'])
      expect(screen.queryByRole('region', { name: title })).toBeNull();
    expect(screen.queryByText('منطقة القرار')).toBeNull();
    expect(screen.queryByRole('button', { name: 'حذف' })).toBeNull();
  });

  it('shows the rejection reason name of a deleted rejected request', () => {
    show(
      deletedRequestFile({
        status: 'rejected',
        decision: {
          status: 'rejected',
          by: 'أدمن المراجعة',
          at: '2026-11-23T11:00:00Z',
          counts_commission: null,
          despite_warnings: [],
          reason: 'other',
          label: 'سبب آخر',
        },
      }),
    );
    expect(screen.getByRole('status').textContent).toContain('سبب الرفض: سبب آخر');
  });
});
