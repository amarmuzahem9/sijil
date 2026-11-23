/**
 * «الاتصال بالإدارة» (specs/009 research R8): WhatsApp to the administration's number from the
 * settings, with a ready text that names only the marketer. It never carries subscriber data,
 * not even the phone that was typed (FR-005a).
 */
import { apiFetch } from './api';
import { clientId } from './drafts';

export const CONTACT_ADMIN_TEXT = {
  action: 'الاتصال بالإدارة',
  unset: 'رقم الإدارة غير مضبوط في الإعدادات',
} as const;

export const contactAdminMessage = (marketerName: string) =>
  `مرحباً، أنا المسوّق ${marketerName}. عندي مشترك رقم هاتفه مسجّل سابقاً وأحتاج مساعدة الإدارة.`;

/** `07XXXXXXXXX` (§8.1) → `https://wa.me/9647XXXXXXXXX?text=…`. */
export function adminWhatsAppLink(number: string, marketerName: string): string {
  const international = `964${number.replace(/^0/, '')}`;
  return `https://wa.me/${international}?text=${encodeURIComponent(contactAdminMessage(marketerName))}`;
}

/** Audit that the button was opened (draft id only). The page does not wait for it. */
export const reportContactAdmin = (draftId: string) =>
  apiFetch<void>(`/api/drafts/${encodeURIComponent(draftId)}/contact-admin`, {
    method: 'POST',
    headers: { 'X-Client-Id': clientId },
  });
