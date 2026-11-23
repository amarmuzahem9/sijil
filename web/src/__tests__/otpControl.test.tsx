/**
 * «تحقّق» control (specs/007 US1, US2) and the six code boxes (owner request): states, the 60 s
 * countdown, focus moving between boxes, Backspace, paste and keyboard suggestion, Arabic digits,
 * auto-submit on the sixth digit, red shake on a wrong code, green on success.
 * The component never sees a code from the server; these tests type synthetic ones.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { OtpStatus } from '../lib/drafts';
import { ERROR_HOLD_MS, normalizeCodeEntry, OTP_TEXT, SUCCESS_HOLD_MS } from '../lib/otp';
import { OtpControl, type OtpControlProps } from '../pages/marketer/subscriber/OtpControl';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const NOW = new Date('2026-11-23T10:00:00Z');

function status(partial: Partial<OtpStatus> = {}): OtpStatus {
  return {
    status: 'none',
    phone: null,
    resend_at: null,
    expires_at: null,
    attempts_left: null,
    verified_at: null,
    ...partial,
  };
}

const SENT = status({
  status: 'sent',
  phone: '07801234567',
  resend_at: '2026-11-23T10:01:00Z',
  expires_at: '2026-11-23T11:00:00Z',
  attempts_left: 3,
});

function renderControl(props: Partial<OtpControlProps> = {}) {
  const apply = vi.fn();
  const onSend = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
  const onVerify = vi.fn<(code: string) => Promise<() => void>>().mockResolvedValue(apply);
  const view = render(
    <OtpControl otp={status()} phoneValid enabled onSend={onSend} onVerify={onVerify} {...props} />,
  );
  return { ...view, onSend, onVerify, apply };
}

const box = (i: number) => screen.getByTestId(`otp-digit-${i}`) as HTMLInputElement;
const values = () => [0, 1, 2, 3, 4, 5].map((i) => box(i).value).join('');
const disabled = (el: HTMLElement) => (el as HTMLButtonElement).disabled;

async function type(i: number, value: string) {
  await act(async () => {
    fireEvent.change(box(i), { target: { value } });
  });
}

async function paste(i: number, text: string) {
  await act(async () => {
    fireEvent.paste(box(i), { clipboardData: { getData: () => text } });
  });
}

describe('normalizeCodeEntry', () => {
  it.each([
    ['123456', '123456'],
    ['١٢٣ ٤٥٦', '123456'],
    ['۱۲۳۴۵۶', '123456'],
    ['رمزك هو 482915', '482915'],
    ['1234567', '123456'],
  ])('%s → %s', (raw, expected) => {
    expect(normalizeCodeEntry(raw)).toBe(expected);
  });
});

describe('OtpControl states', () => {
  it('disables «تحقّق» for an invalid or empty phone', () => {
    renderControl({ phoneValid: false });
    expect(disabled(screen.getByTestId('otp-send'))).toBe(true);
    expect(screen.getByTestId('otp-send').textContent).toContain(OTP_TEXT.verify);
  });

  it('calls onSend when «تحقّق» is tapped', async () => {
    const { onSend } = renderControl();
    await act(async () => {
      fireEvent.click(screen.getByTestId('otp-send'));
    });
    expect(onSend).toHaveBeenCalledOnce();
  });

  it('shows ✓ «تم التحقق» and no button when verified', () => {
    renderControl({ otp: status({ status: 'verified', verified_at: NOW.toISOString() }) });
    expect(screen.getByTestId('otp-verified').textContent).toContain(OTP_TEXT.verified);
    expect(screen.queryByTestId('otp-send')).toBeNull();
  });

  it('counts down «إعادة الإرسال بعد N ثانية» then offers «إعادة الإرسال»', () => {
    vi.useFakeTimers({ now: NOW });
    renderControl({ otp: SENT });
    const resend = screen.getByTestId('otp-send');
    expect(resend.textContent).toContain('إعادة الإرسال بعد 60 ثانية');
    expect(disabled(resend)).toBe(true);
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(resend.textContent).toContain('إعادة الإرسال بعد 45 ثانية');
    act(() => {
      vi.advanceTimersByTime(45_000);
    });
    expect(resend.textContent).toContain(OTP_TEXT.resend);
    expect(disabled(resend)).toBe(false);
  });

  it('a 429 resend wait starts the countdown from the server seconds', async () => {
    vi.useFakeTimers({ now: NOW });
    const onSend = vi
      .fn<() => Promise<void>>()
      .mockRejectedValue(
        new ApiError('otp_resend_wait', 'إعادة الإرسال بعد 30 ثانية', 429, { retry_after_s: 30 }),
      );
    renderControl({ onSend });
    await act(async () => {
      fireEvent.click(screen.getByTestId('otp-send'));
    });
    expect(screen.getByTestId('otp-send').textContent).toContain('إعادة الإرسال بعد 30 ثانية');
  });

  it('says «خدمة التحقق غير مهيّأة» without a provider key', () => {
    renderControl({ enabled: false });
    expect(screen.getByTestId('otp-not-configured').textContent).toContain(OTP_TEXT.notConfigured);
    expect(screen.queryByTestId('otp-send')).toBeNull();
  });
});

describe('the six code boxes', () => {
  it('six numeric one-time-code boxes, left to right, the first focused', () => {
    vi.useFakeTimers({ now: NOW });
    renderControl({ otp: SENT });
    expect(screen.getByTestId('otp-sent-to').textContent).toContain(
      'أُرسل رمز التحقق عبر الواتساب إلى 07801234567',
    );
    expect(screen.getByTestId('otp-code').getAttribute('dir')).toBe('ltr');
    for (let i = 0; i < 6; i += 1) {
      expect(box(i).getAttribute('inputmode')).toBe('numeric');
      expect(box(i).getAttribute('autocomplete')).toBe('one-time-code');
    }
    expect(document.activeElement).toBe(box(0));
  });

  it('typing moves to the next box; Backspace on an empty box goes back', async () => {
    vi.useFakeTimers({ now: NOW });
    renderControl({ otp: SENT });
    await type(0, '4');
    expect(document.activeElement).toBe(box(1));
    await type(1, '٨'); // Arabic-Indic digit
    expect(values()).toBe('48');
    expect(document.activeElement).toBe(box(2));

    await act(async () => {
      fireEvent.keyDown(box(2), { key: 'Backspace' });
    });
    expect(values()).toBe('4');
    expect(document.activeElement).toBe(box(1));
  });

  it('ignores letters', async () => {
    vi.useFakeTimers({ now: NOW });
    renderControl({ otp: SENT });
    await type(0, 'a');
    expect(values()).toBe('');
    expect(document.activeElement).toBe(box(0));
  });

  it('pasting the whole code (Arabic digits) spreads it and submits by itself', async () => {
    vi.useFakeTimers({ now: NOW });
    const { onVerify } = renderControl({ otp: SENT });
    await paste(2, '٤٨٢ ٩١٥');
    expect(values()).toBe('482915');
    expect(onVerify).toHaveBeenCalledWith('482915');
  });

  it('a keyboard suggestion (six digits in one box) spreads from the first box', async () => {
    vi.useFakeTimers({ now: NOW });
    const { onVerify } = renderControl({ otp: SENT });
    await type(0, '482915');
    expect(values()).toBe('482915');
    expect(onVerify).toHaveBeenCalledOnce();
  });

  it('the sixth digit submits without «تأكيد»', async () => {
    vi.useFakeTimers({ now: NOW });
    const { onVerify } = renderControl({ otp: SENT });
    for (const [i, d] of [...'24681'].entries()) await type(i, d);
    expect(onVerify).not.toHaveBeenCalled();
    await type(5, '0');
    expect(onVerify).toHaveBeenCalledWith('246810');
    expect(screen.queryByRole('button', { name: 'تأكيد' })).toBeNull();
  });

  it('a wrong code turns red and shakes, then clears for a new try', async () => {
    vi.useFakeTimers({ now: NOW });
    const onVerify = vi
      .fn<(code: string) => Promise<() => void>>()
      .mockRejectedValue(
        new ApiError('otp_wrong', 'الرمز غير صحيح، بقيت محاولتان', 422, { attempts_left: 2 }),
      );
    renderControl({ otp: SENT, onVerify });
    await paste(0, '000000');

    expect(screen.getByTestId('otp-code').getAttribute('data-phase')).toBe('error');
    expect(box(0).getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByTestId('otp-error').textContent).toContain('الرمز غير صحيح، بقيت محاولتان');

    act(() => {
      vi.advanceTimersByTime(ERROR_HOLD_MS);
    });
    expect(screen.getByTestId('otp-code').getAttribute('data-phase')).toBe('idle');
    expect(values()).toBe('');
    expect(document.activeElement).toBe(box(0));
  });

  it('the right code turns green, then shows ✓ once applied', async () => {
    vi.useFakeTimers({ now: NOW });
    const { apply } = renderControl({ otp: SENT });
    await paste(0, '246810');

    expect(screen.getByTestId('otp-code').getAttribute('data-phase')).toBe('success');
    expect(box(0).disabled).toBe(true);
    expect(apply).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(SUCCESS_HOLD_MS);
    });
    expect(apply).toHaveBeenCalledOnce();
  });
});

describe('OtpControl after a change (US2)', () => {
  it('shows «يحتاج تحقق جديد» with «تحقّق» enabled', () => {
    renderControl({ otp: status({ status: 'needs_reverify' }) });
    expect(screen.getByTestId('otp-needs-reverify').textContent).toContain(OTP_TEXT.needsReverify);
    expect(disabled(screen.getByTestId('otp-send'))).toBe(false);
    expect(screen.getByTestId('otp-send').textContent).toContain(OTP_TEXT.verify);
  });

  it('closes the code boxes when the pending code is cancelled', () => {
    vi.useFakeTimers({ now: NOW });
    const { rerender, onSend, onVerify } = renderControl({ otp: SENT });
    expect(screen.getByTestId('otp-code')).toBeTruthy();
    rerender(<OtpControl otp={status()} phoneValid enabled onSend={onSend} onVerify={onVerify} />);
    expect(screen.queryByTestId('otp-code')).toBeNull();
  });
});
