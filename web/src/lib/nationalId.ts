/**
 * Client-side mirror of api/app/core/national_id.py (specs/005 research.md R9).
 * Instant feedback only — the server result is authoritative (Principle I).
 */
import { toLatinDigits } from './phone';

// Spaces of any kind and the invisible direction marks phones paste around numbers.
const STRIP = /[\s\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\ufeff]/g;

/** The 12 Latin digits, or null when the input is not a valid national ID. */
export function normalizeNationalId(raw: string | null | undefined): string | null {
  if (raw == null) return null;
  const cleaned = toLatinDigits(raw).replace(STRIP, '');
  return /^[0-9]{12}$/.test(cleaned) ? cleaned : null;
}
