/**
 * The request number as an admin types it (specs/011 research R6). Mirrors
 * api/app/core/request_number.py; both are tested against request_number_cases.json.
 */

const ARABIC_INDIC = '٠١٢٣٤٥٦٧٨٩';
const EASTERN_ARABIC = '۰۱۲۳۴۵۶۷۸۹';
const PATTERN = /^#?\s*(?:T3C-)?\s*([0-9]{1,9})$/i;

function westernDigits(text: string): string {
  return text.replace(/[٠-٩۰-۹]/g, (d) => {
    const i = ARABIC_INDIC.indexOf(d);
    return String(i >= 0 ? i : EASTERN_ARABIC.indexOf(d));
  });
}

/** The number, or null when the text is not a request number. */
export function parseRequestNumber(text: string): number | null {
  const match = PATTERN.exec(westernDigits(text).trim());
  if (!match) return null;
  const number = Number(match[1]);
  return number > 0 ? number : null;
}
