/**
 * «إرسال» (specs/008 T025, T028; FR-011): enabled only when nothing is missing and the phone is
 * verified; pressing it calls the submit, and a refusal shows the server's Arabic message.
 * The three server-side items (phone used, national ID exists, family unconfirmed) are named.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { MissingItem } from '../lib/draftValidation';
import { MissingSummary } from '../pages/marketer/subscriber/MissingSummary';

afterEach(cleanup);

const sendButton = () => screen.getByRole('button', { name: 'إرسال' }) as HTMLButtonElement;

describe('MissingSummary «إرسال»', () => {
  it('is disabled while something is missing', () => {
    const onSubmit = vi.fn();
    render(
      <MissingSummary
        missing={[{ field: 'landmark', code: 'required' }]}
        phoneVerified
        onSubmit={onSubmit}
      />,
    );
    expect(sendButton().disabled).toBe(true);
  });

  it('is disabled until the phone is verified', () => {
    render(<MissingSummary missing={[]} phoneVerified={false} onSubmit={vi.fn()} />);
    expect(sendButton().disabled).toBe(true);
    expect(screen.getByTestId('missing-phone_verification')).toBeTruthy();
  });

  it('is enabled when complete and verified, and submits once per press', async () => {
    const onSubmit = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
    render(<MissingSummary missing={[]} phoneVerified onSubmit={onSubmit} />);
    expect(sendButton().disabled).toBe(false);
    expect(screen.queryByText('الإرسال يتفعّل بعد إضافة فحص الطلب')).toBeNull();
    await act(async () => {
      fireEvent.click(sendButton());
    });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('is busy while sending, so a double tap sends once', async () => {
    let finish: () => void = () => undefined;
    const onSubmit = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)));
    render(<MissingSummary missing={[]} phoneVerified onSubmit={onSubmit} />);
    await act(async () => {
      fireEvent.click(sendButton());
    });
    expect(screen.getByRole('button', { name: /جارٍ الإرسال/ })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /جارٍ الإرسال/ }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    await act(async () => finish());
  });

  it('shows the refusal message from the server', async () => {
    const onSubmit = vi
      .fn<() => Promise<void>>()
      .mockRejectedValue(
        new ApiError('phone_used', 'المشترك موجود سابقاً، هل يود العودة للخدمة؟', 409),
      );
    render(<MissingSummary missing={[]} phoneVerified onSubmit={onSubmit} />);
    await act(async () => {
      fireEvent.click(sendButton());
    });
    expect(screen.getByText('المشترك موجود سابقاً، هل يود العودة للخدمة؟')).toBeTruthy();
    expect(sendButton().disabled).toBe(false);
  });

  it('names the three server-side items', () => {
    const missing = [
      { field: 'national_id_exists', code: 'national_id_exists' },
      { field: 'family_exists_unconfirmed', code: 'family_exists_unconfirmed' },
      { field: 'phone_used', code: 'phone_used' },
    ] as unknown as MissingItem[];
    render(<MissingSummary missing={missing} phoneVerified onSubmit={vi.fn()} />);
    expect(screen.getByTestId('missing-national_id_exists').textContent).toContain(
      'المشترك لديه اشتراك سابق',
    );
    expect(screen.getByTestId('missing-family_exists_unconfirmed').textContent).toContain(
      'لهذه العائلة اشتراك سابق',
    );
    expect(screen.getByTestId('missing-phone_used').textContent).toContain(
      'المشترك موجود سابقاً، هل يود العودة للخدمة؟',
    );
    expect(sendButton().disabled).toBe(true);
  });
  it('lists the server items in page order, between the form fields (T044)', () => {
    // The server sorts: national ID items after the national ID, family after the family number,
    // phone after the phone (specs/008 research R5).
    const missing = [
      { field: 'national_id_exists', code: 'national_id_exists' },
      { field: 'family_exists_unconfirmed', code: 'family_exists_unconfirmed' },
      { field: 'landmark', code: 'required' },
      { field: 'phone_used', code: 'phone_used' },
    ] as unknown as MissingItem[];
    render(<MissingSummary missing={missing} phoneVerified onSubmit={vi.fn()} />);
    const order = screen.getAllByRole('listitem').map((li) => li.getAttribute('data-testid'));
    expect(order).toEqual([
      'missing-national_id_exists',
      'missing-family_exists_unconfirmed',
      'missing-landmark',
      'missing-phone_used',
    ]);
  });

  it('links each server item to its field', () => {
    const field = document.createElement('input');
    field.id = 'field-family_number';
    field.scrollIntoView = vi.fn();
    document.body.appendChild(field);
    const missing = [
      { field: 'family_exists_unconfirmed', code: 'family_exists_unconfirmed' },
    ] as unknown as MissingItem[];
    render(<MissingSummary missing={missing} phoneVerified onSubmit={vi.fn()} />);
    fireEvent.click(
      screen.getByTestId('missing-family_exists_unconfirmed').querySelector('button')!,
    );
    expect(document.activeElement).toBe(field);
    field.remove();
  });
});
