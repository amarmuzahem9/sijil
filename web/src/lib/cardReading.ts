/**
 * Card reading on the form (specs/006 contracts/api.md › UI strings, research R5, R8).
 *
 * Pure helpers: the Arabic texts of each state and reason, when to poll, and which fields a
 * finished reading may update on this page. Card data is never stored on the device.
 */
import type { CardField, CardReading, CardReadingSide, ReshootReason, Side } from './drafts';
import { normalizeNationalId } from './nationalId';

export const READING_POLL_MS = 2000;

export const READING_RUNNING = 'جارٍ قراءة البطاقة';
export const READING_NEEDS_OTHER_SIDE = 'ارفع الوجه الآخر لتبدأ قراءة البطاقة';
export const READING_FAILED = 'تعذّرت القراءة الآلية، أكمل يدوياً';
export const READING_RETRY = 'أعد المحاولة';
export const RESHOOT = 'أعد التصوير';
export const RESHOOT_TIPS = 'بلا لمعة، البطاقة مسطّحة وتملأ الإطار، والوجه في خانته';
export const MARK_FROM_CARD = 'من البطاقة';
export const MARK_EDITED = 'عُدِّل يدوياً';
export const NO_SURNAME = 'لا يوجد لقب على البطاقة';
export const NO_SURNAME_HINT = 'لا يوجد لقب على البطاقة؟ اختر الخيار أدناه أو اسأل المشترك';
export const NATIONAL_ID_CHECK = 'تأكد من الرقم الوطني';
export const NATIONAL_ID_CURRENT = 'الرقم الحالي';
export const NATIONAL_ID_MRZ = 'في الشريط الآلي';
export const NATIONAL_ID_ADOPT = 'اعتماد هذا الرقم';
export const CARD_EXPIRED = 'البطاقة منتهية الصلاحية';
export const BIRTH_YEAR_MISMATCH = 'سنة الميلاد لا تطابق الرقم الوطني، تأكد منهما';

const SIDE_NAME: Record<Side, string> = { front: 'وجه', back: 'ظهر' };
const OTHER_SIDE_NAME: Record<Side, string> = { front: 'الظهر', back: 'الوجه' };

/** The Arabic message of a side that needs a re-shoot. */
export function reshootText(side: Side, reason: ReshootReason): string {
  switch (reason) {
    case 'no_card':
      return `لم نتمكن من قراءة ${SIDE_NAME[side]} البطاقة`;
    case 'wrong_side':
      return `هذه صورة ${OTHER_SIDE_NAME[side]}، ضعها في خانتها`;
    case 'not_unified':
      return 'البطاقة الوطنية الموحدة فقط';
    case 'multiple':
      return 'يظهر أكثر من مستمسك في الصورة';
  }
}

const ACTIVE: ReadonlySet<CardReadingSide['state']> = new Set(['pending', 'running']);

export const isActive = (side: CardReadingSide | null | undefined): boolean =>
  side != null && ACTIVE.has(side.state);

/** Poll while either side waits or runs (research R5). */
export const shouldPoll = (reading: CardReading | null | undefined): boolean =>
  reading != null && (isActive(reading.front) || isActive(reading.back));

export const anyFailed = (reading: CardReading | null | undefined): boolean =>
  reading?.front?.state === 'failed' || reading?.back?.state === 'failed';

/** Only one side has an image: the reading waits for the other one (FR-001). */
export const waitsForOtherSide = (reading: CardReading | null | undefined): boolean => {
  const sides = [reading?.front, reading?.back].filter(Boolean);
  return sides.length === 1 && sides[0]?.state === 'pending';
};

/**
 * Which server values a finished reading may write into this page's form: every card field,
 * except those with a change still waiting to be saved here (research R8; the typed value wins
 * and is resent by the autosave queue).
 */
export function fieldsToMerge(
  fields: readonly CardField[],
  hasPendingKey: (field: CardField) => boolean,
): CardField[] {
  return fields.filter((field) => !hasPendingKey(field));
}

/**
 * FR-032: the national ID's first four digits are the birth year. A different year (typed or
 * read) shows a warning only; it never blocks saving or sending.
 */
export function birthYearMismatch(birthDate: string, nationalId: string): boolean {
  const id = normalizeNationalId(nationalId);
  if (!id || !/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) return false;
  return birthDate.slice(0, 4) !== id.slice(0, 4);
}

/** FR-030: an expiry date before today in Baghdad. */
export const isExpired = (expiryDate: string, today: string): boolean =>
  /^\d{4}-\d{2}-\d{2}$/.test(expiryDate) && expiryDate < today;
