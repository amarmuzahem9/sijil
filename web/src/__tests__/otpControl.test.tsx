/**
 * «تحقّق» control (specs/007 US1, US2): states, the 60 s countdown, Arabic digits and paste.
 * The component never sees a code from the server; these tests type synthetic ones.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { OtpStatus } from '../lib/drafts';
import { normalizeCodeEntry, OTP_TEXT } from '../lib/otp';
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
  const onSend = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
  const onVerify = vi.fn<(code: string) => Promise<void>>().mockResolvedValue(undefined);
  const view = render(
    <OtpControl otp={status()} phoneValid enabled onSend={onSend} onVerify={onVerify} {...props} />,
  );
  return { ...view, onSend, onVerify };
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

describe('OtpControl', () => {
  it('disables «تحقّق» for an invalid or empty phone', () => {
    renderControl({ phoneValid: false });
    expect((screen.getByTestId('otp-send') as HTMLButtonElement).disabled).toBe(true);
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

  it('shows the code box with the numeric keypad and one-time-code', () => {
    vi.useFakeTimers({ now: NOW });
    renderControl({ otp: SENT });
    expect(screen.getByTestId('otp-sent-to').textContent).toContain(
      'أُرسل رمز التحقق عبر الواتساب إلى 07801234567',
    );
    const input = screen.getByTestId('otp-code');
    expect(input.getAttribute('inputmode')).toBe('numeric');
    expect(input.getAttribute('autocomplete')).toBe('one-time-code');
  });

  it('counts down «إعادة الإرسال بعد N ثانية» then offers «إعادة الإرسال»', () => {
    vi.useFakeTimers({ now: NOW });
    renderControl({ otp: SENT });
    const resend = screen.getByTestId('otp-send');
    expect(resend.textContent).toContain('إعادة الإرسال بعد 60 ثانية');
    expect((resend as HTMLButtonElement).disabled).toBe(true);
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(resend.textContent).toContain('إعادة الإرسال بعد 45 ثانية');
    act(() => {
      vi.advanceTimersByTime(45_000);
    });
    expect(resend.textContent).toContain(OTP_TEXT.resend);
    expect((resend as HTMLButtonElement).disabled).toBe(false);
  });

  it('accepts a pasted Arabic-digit code and sends Latin digits', async () => {
    vi.useFakeTimers({ now: NOW });
    const { onVerify } = renderControl({ otp: SENT });
    const confirm = screen.getByTestId('otp-confirm');
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByTestId('otp-code'), { target: { value: '٤٨٢ ٩١٥' } });
    expect((screen.getByTestId('otp-code') as HTMLInputElement).value).toBe('482915');
    await act(async () => {
      fireEvent.click(confirm);
    });
    expect(onVerify).toHaveBeenCalledWith('482915');
  });

  it('shows the server message for a wrong code', async () => {
    vi.useFakeTimers({ now: NOW });
    const onVerify = vi
      .fn<(code: string) => Promise<void>>()
      .mockRejectedValue(
        new ApiError('otp_wrong', 'الرمز غير صحيح، بقيت محاولتان', 422, { attempts_left: 2 }),
      );
    renderControl({ otp: SENT, onVerify });
    fireEvent.change(screen.getByTestId('otp-code'), { target: { value: '000000' } });
    await act(async () => {
      fireEvent.click(screen.getByTestId('otp-confirm'));
    });
    expect(screen.getByTestId('otp-error').textContent).toContain('الرمز غير صحيح، بقيت محاولتان');
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

describe('OtpControl after a change (US2)', () => {
  it('shows «يحتاج تحقق جديد» with «تحقّق» enabled', () => {
    renderControl({ otp: status({ status: 'needs_reverify' }) });
    expect(screen.getByTestId('otp-needs-reverify').textContent).toContain(OTP_TEXT.needsReverify);
    expect((screen.getByTestId('otp-send') as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByTestId('otp-send').textContent).toContain(OTP_TEXT.verify);
  });

  it('closes the code box when the pending code is cancelled', () => {
    vi.useFakeTimers({ now: NOW });
    const { rerender, onSend, onVerify } = renderControl({ otp: SENT });
    expect(screen.getByTestId('otp-code')).toBeTruthy();
    rerender(<OtpControl otp={status()} phoneValid enabled onSend={onSend} onVerify={onVerify} />);
    expect(screen.queryByTestId('otp-code')).toBeNull();
  });
});
