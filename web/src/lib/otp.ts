/**
 * Phone OTP texts and code-entry rules for the page (specs/007 contracts/api.md). The page never
 * receives a code; it only cleans what the marketer typed or pasted.
 */
import { toLatinDigits } from './phone';

export const OTP_TEXT = {
  verify: 'تحقّق',
  confirm: 'تأكيد',
  resend: 'إعادة الإرسال',
  verified: 'تم التحقق',
  needsReverify: 'يحتاج تحقق جديد',
  notConfigured: 'خدمة التحقق غير مهيّأة',
  codeLabel: 'رمز التحقق',
  digitLabel: 'الرقم',
  sentTo: (phone: string) => `أُرسل رمز التحقق عبر الواتساب إلى ${phone}`,
  resendIn: (seconds: number) => `إعادة الإرسال بعد ${seconds} ثانية`,
} as const;

export const CODE_LENGTH = 6;

/** How long the green boxes show before ✓ «تم التحقق», and the red shake before clearing. */
export const SUCCESS_HOLD_MS = 700;
export const ERROR_HOLD_MS = 500;

/** Arabic-Indic digits → ASCII, anything else dropped, at most 6 digits (pasting works). */
export function normalizeCodeEntry(raw: string): string {
  return toLatinDigits(raw)
    .replace(/[^0-9]/g, '')
    .slice(0, CODE_LENGTH);
}
