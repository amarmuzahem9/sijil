/**
 * Money and counts (specs/004 FR-012): integers end to end, shown with thousands separators.
 * Input accepts Arabic-Indic / Persian digits, Latin or Arabic thousands separators and spaces.
 */
const DIGIT_OFFSETS = [0x0660, 0x06f0]; // Arabic-Indic, Extended Arabic-Indic (Persian)
// space, ",", Arabic thousands sep U+066C, Arabic comma U+060C, nbsp U+00A0, narrow nbsp U+202F
const SEPARATORS = new RegExp('[\\s,\\u066c\\u060c\\u00a0\\u202f]', 'g');
const grouping = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

function toLatinDigits(input: string): string {
  let out = '';
  for (const ch of input) {
    const code = ch.codePointAt(0)!;
    const base = DIGIT_OFFSETS.find((b) => code >= b && code <= b + 9);
    out += base === undefined ? ch : String(code - base);
  }
  return out;
}

/** "٢٠٬٠٠٠" / "20,000" / " 20000 " → 20000; anything that is not a whole number → null. */
export function parseMoney(text: string | null | undefined): number | null {
  if (text == null) return null;
  const cleaned = toLatinDigits(text).replace(SEPARATORS, '');
  if (!/^\d{1,9}$/.test(cleaned)) return null;
  return Number(cleaned);
}

/** 20000 → "20,000". */
export function formatNumber(value: number): string {
  return grouping.format(value);
}

/** 20000 → "20,000 د.ع". */
export function formatMoney(value: number): string {
  return `${formatNumber(value)} د.ع`;
}

/** The text a MoneyField starts with for an existing value ("" when there is none). */
export function moneyText(value: number | null | undefined): string {
  return value === null || value === undefined ? '' : formatNumber(value);
}
