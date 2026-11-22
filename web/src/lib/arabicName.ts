/**
 * Client mirror of api/app/core/arabic_name.py (docs/system.md §5.1 v1.5, specs/005 research.md
 * R12): Arabic letters and single spaces only; diacritics, tatweel and direction marks removed;
 * spaces trimmed and collapsed. Tested against the shared fixture's `names` cases.
 *
 * The character classes are built from code points so that no invisible or combining character
 * is written literally in this file.
 */
const ch = (code: number) => String.fromCharCode(code);
const range = (lo: number, hi: number) => `${ch(lo)}-${ch(hi)}`;

// Arabic letters, including the Persian/Iraqi additions (پ چ ژ ڤ ک گ ی) in U+0671–U+06D3.
const LETTERS = range(0x0621, 0x063a) + range(0x0641, 0x064a) + range(0x0671, 0x06d3);
// Diacritics (harakat, shadda, sukun, superscript alef), tatweel and direction marks.
const REMOVED =
  range(0x064b, 0x065f) +
  range(0x200e, 0x200f) +
  range(0x202a, 0x202e) +
  range(0x2066, 0x2069) +
  ch(0x0670) +
  ch(0x0640) +
  ch(0x061c) +
  ch(0xfeff);

const REMOVE = new RegExp(`[${REMOVED}]`, 'g');
const VALID = new RegExp(`^[${LETTERS}]+(?: [${LETTERS}]+)*$`);

export const INVALID_NAME_MESSAGE = 'الاسم أحرف عربية فقط';

export type NameResult = { ok: true; value: string | null } | { ok: false };

/** Clean a name the way the server does; `ok: false` when it would be refused. */
export function cleanArabicName(raw: string | null | undefined): NameResult {
  if (raw == null) return { ok: true, value: null };
  const text = raw.normalize('NFC').replace(REMOVE, '').replace(/\s+/g, ' ').trim();
  if (!text) return { ok: true, value: null };
  return VALID.test(text) ? { ok: true, value: text } : { ok: false };
}
