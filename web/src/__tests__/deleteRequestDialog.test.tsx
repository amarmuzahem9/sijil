/**
 * «حذف» (specs/011 US1: FR-004 to FR-006): the warning, the four fixed reasons, and the final
 * button only after a reason and the request number typed back (Western or Arabic-Indic digits).
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DeleteRequestDialog } from '../pages/admin/pending/DeleteRequestDialog';

const onSubmit = vi.fn();
const onClose = vi.fn();

beforeEach(() => {
  onSubmit.mockReset();
  onClose.mockReset();
});
afterEach(cleanup);

function show(props: { error?: string | null; busy?: boolean } = {}) {
  render(
    <DeleteRequestDialog
      open
      numberLabel="T3C-1005"
      onSubmit={onSubmit}
      onClose={onClose}
      {...props}
    />,
  );
}

const confirm = () => screen.getByRole('button', { name: 'حذف نهائي' }) as HTMLButtonElement;
const numberBox = () =>
  screen.getByRole('textbox', { name: /اكتب رقم الطلب للتأكيد/ }) as HTMLInputElement;

describe('DeleteRequestDialog', () => {
  it('warns that the deletion is final and lists the four reasons', () => {
    show();
    expect(screen.getByRole('heading', { name: /حذف الطلب/ })).toBeTruthy();
    expect(
      screen.getByText('ستُمسح البيانات الشخصية وصور البطاقة نهائياً ولا يمكن التراجع'),
    ).toBeTruthy();
    for (const label of ['طلب مكرر', 'طلب تجريبي', 'خطأ إدخال', 'سبب آخر'])
      expect(screen.getByRole('radio', { name: label })).toBeTruthy();
    // «سبب آخر» takes no text.
    fireEvent.click(screen.getByRole('radio', { name: 'سبب آخر' }));
    expect(screen.getAllByRole('textbox')).toHaveLength(1);
    expect(confirm().disabled).toBe(true);
  });

  it('needs a reason and the matching number', () => {
    show();
    fireEvent.change(numberBox(), { target: { value: 'T3C-1005' } });
    expect(confirm().disabled).toBe(true);
    fireEvent.click(screen.getByRole('radio', { name: 'طلب تجريبي' }));
    expect(confirm().disabled).toBe(false);
    fireEvent.change(numberBox(), { target: { value: '1006' } });
    expect(confirm().disabled).toBe(true);
  });

  it('accepts the number in Arabic-Indic digits and sends it as typed', () => {
    show();
    fireEvent.click(screen.getByRole('radio', { name: 'طلب مكرر' }));
    fireEvent.change(numberBox(), { target: { value: '١٠٠٥' } });
    fireEvent.click(confirm());
    expect(onSubmit).toHaveBeenCalledWith({ reason: 'duplicate', confirm_number: '١٠٠٥' });
  });

  it('shows the server error', () => {
    show({ error: 'لا يمكن حذف طلب مقبول أو مربوط' });
    expect(screen.getByText('لا يمكن حذف طلب مقبول أو مربوط')).toBeTruthy();
  });

  it('disables both buttons while sending', () => {
    show({ busy: true });
    expect(confirm().disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'إلغاء' }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it('closes without sending on «إلغاء»', () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(onClose).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
