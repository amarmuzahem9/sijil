/**
 * «رسالة الربط» helpers (specs/012 research R3). The text itself comes from the server.
 */

/** WhatsApp with the text ready and no recipient: the marketer picks the technicians' group. */
export function whatsappUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

/** True when the text reached the clipboard. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
