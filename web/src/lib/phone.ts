/**
 * Client-side mirror of api/app/core/phone.py (docs/system.md §8.1).
 * Used only for instant feedback — the server result is authoritative (Principle I).
 */
const DIGIT_OFFSETS = [0x0660, 0x06f0]; // Arabic-Indic, Extended Arabic-Indic (Persian)

/** Arabic-Indic and Persian digits → ASCII digits; every other character is kept. */
export function toLatinDigits(input: string): string {
  let out = '';
  for (const ch of input) {
    const code = ch.codePointAt(0)!;
    const base = DIGIT_OFFSETS.find((b) => code >= b && code <= b + 9);
    out += base === undefined ? ch : String(code - base);
  }
  return out;
}

export function normalizePhone(raw: string | null | undefined): string | null {
  if (raw == null) return null;
  let digits = toLatinDigits(raw).replace(/[^0-9]/g, '');
  if (digits.startsWith('00964')) digits = '0' + digits.slice(5);
  else if (digits.startsWith('964')) digits = '0' + digits.slice(3);
  if (digits.length === 10 && digits.startsWith('7')) digits = '0' + digits;
  return /^07\d{9}$/.test(digits) ? digits : null;
}
