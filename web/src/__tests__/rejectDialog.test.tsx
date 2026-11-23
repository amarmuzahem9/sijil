/**
 * «رفض» (specs/010 US2: FR-008, FR-019; system.md v1.14 §6.4): the five fixed reasons, «سبب آخر»
 * with a required note and its hint, and no note with a fixed reason.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RejectDialog } from '../pages/admin/pending/RejectDialog';

const onSubmit = vi.fn();
const onClose = vi.fn();

beforeEach(() => {
  onSubmit.mockReset();
  onClose.mockReset();
});
afterEach(cleanup);

function show() {
  render(<RejectDialog open numberLabel="T3C-1011" onSubmit={onSubmit} onClose={onClose} />);
}

const confirm = () => screen.getByRole('button', { name: 'تأكيد الرفض' }) as HTMLButtonElement;

describe('RejectDialog', () => {
  it('lists the five reasons and needs one before sending', () => {
    show();
    for (const label of [
      'صورة البطاقة غير واضحة',
      'الأرقام غير مطابقة للبطاقة',
      'المتبقي من الاشتراك الأول أقل من 15 يوماً',
      'المشترك لديه اشتراك فعّال',
      'سبب آخر',
    ])
      expect(screen.getByRole('radio', { name: label })).toBeTruthy();
    expect(confirm().disabled).toBe(true);
  });

  it('sends a fixed reason with no note', () => {
    show();
    fireEvent.click(screen.getByRole('radio', { name: 'الأرقام غير مطابقة للبطاقة' }));
    expect(screen.queryByRole('textbox', { name: /^سبب الرفض/ })).toBeNull();
    fireEvent.click(confirm());
    expect(onSubmit).toHaveBeenCalledWith({ reason: 'numbers_mismatch' });
  });

  it('«سبب آخر» needs a note of 3 characters or more, with the privacy hint', () => {
    show();
    fireEvent.click(screen.getByRole('radio', { name: 'سبب آخر' }));
    // A required field's label carries MUI's « *».
    const note = screen.getByRole('textbox', { name: /^سبب الرفض/ }) as HTMLTextAreaElement;
    expect(note.required).toBe(true);
    expect(screen.getByText('لا تكتب أي معلومة عن مشترك آخر')).toBeTruthy();

    fireEvent.change(note, { target: { value: '  اب  ' } });
    expect(confirm().disabled).toBe(true);
    fireEvent.change(note, { target: { value: '  طلب مكرر  ' } });
    expect(confirm().disabled).toBe(false);
    fireEvent.click(confirm());
    expect(onSubmit).toHaveBeenCalledWith({ reason: 'other', note: 'طلب مكرر' });
  });

  it('closes without sending on «إلغاء»', () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(onClose).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
