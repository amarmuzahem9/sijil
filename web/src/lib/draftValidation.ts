/**
 * Client mirror of api/app/services/draft_validation.py (specs/005 data-model.md › "Validation
 * rules"). Gives instant feedback; the server's `missing` list is authoritative.
 * Both sides are tested against __tests__/fixtures/draft_validation_cases.json.
 */
import { NAME_LABELS, NAME_MAX, REQUIRED_NAME_FIELDS, type NameField } from './nameFields';
import { normalizeNationalId } from './nationalId';
import { normalizePhone } from './phone';

/** Page order (FR-003): card images, card data, location, subscription, phone. */
export const MISSING_ORDER = [
  'image_front',
  'image_back',
  'first_name',
  'father_name',
  'grandfather_name',
  'great_grandfather_name',
  'surname',
  'mother_first_name',
  'mother_second_name',
  'national_id',
  'family_number',
  // Back of the card (specs/006 owner change, system.md v1.8).
  'birth_date',
  'birth_place',
  'issue_date',
  'expiry_date',
  'card_expired',
  'issuing_authority',
  'location',
  'address',
  'landmark',
  'area_id',
  'tower_id',
  'plan_id',
  'phone',
] as const;

export type MissingField = (typeof MISSING_ORDER)[number];
export type MissingCode = 'required' | 'invalid_national_id' | 'invalid_phone' | 'card_expired';

// The required names in MISSING_ORDER must match REQUIRED_NAME_FIELDS (checked by the tests).

export interface MissingItem {
  field: MissingField;
  code: MissingCode;
}

/** Same limits as data-model.md › drafts and api/app/models/draft.py TEXT_LIMITS. */
export const TEXT_LIMITS = {
  first_name: NAME_MAX,
  father_name: NAME_MAX,
  grandfather_name: NAME_MAX,
  great_grandfather_name: NAME_MAX,
  surname: NAME_MAX,
  mother_first_name: NAME_MAX,
  mother_second_name: NAME_MAX,
  mother_third_name: NAME_MAX,
  mother_surname: NAME_MAX,
  national_id: 30,
  family_number: 30,
  address: 300,
  landmark: 200,
  phone_input: 30,
  birth_place: 100,
  issuing_authority: 100,
} as const;

export type LimitedField = keyof typeof TEXT_LIMITS;

export interface DraftFields extends Partial<Record<NameField, string | null>> {
  national_id?: string | null;
  family_number?: string | null;
  location_lat?: number | null;
  location_lng?: number | null;
  address?: string | null;
  landmark?: string | null;
  area_id?: number | null;
  tower_id?: number | null;
  plan_id?: number | null;
  phone_input?: string | null;
  /** «لا يوجد لقب على البطاقة» satisfies the required surname (specs/006 FR-017). */
  no_surname?: boolean | null;
  /** ISO dates (YYYY-MM-DD) and text of the back of the card. */
  birth_date?: string | null;
  birth_place?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  issuing_authority?: string | null;
}

export const FIELD_LABELS: Record<MissingField, string> = {
  image_front: 'وجه البطاقة',
  image_back: 'ظهر البطاقة',
  first_name: NAME_LABELS.first_name,
  father_name: NAME_LABELS.father_name,
  grandfather_name: NAME_LABELS.grandfather_name,
  great_grandfather_name: NAME_LABELS.great_grandfather_name,
  surname: NAME_LABELS.surname,
  mother_first_name: NAME_LABELS.mother_first_name,
  mother_second_name: NAME_LABELS.mother_second_name,
  national_id: 'الرقم الوطني',
  family_number: 'الرقم العائلي',
  birth_date: 'تاريخ الميلاد',
  birth_place: 'محل الولادة',
  issue_date: 'تاريخ الإصدار',
  expiry_date: 'تاريخ النفاذ',
  card_expired: 'البطاقة منتهية الصلاحية',
  issuing_authority: 'جهة الإصدار',
  location: 'موقع البيت على الخريطة',
  address: 'العنوان',
  landmark: 'أقرب نقطة دالّة',
  area_id: 'المنطقة',
  tower_id: 'البرج',
  plan_id: 'الفئة',
  phone: 'هاتف المشترك',
};

export const CODE_MESSAGES: Record<MissingCode | 'too_long' | 'invalid_name_text', string> = {
  required: 'مطلوب',
  invalid_national_id: 'الرقم الوطني 12 رقماً',
  invalid_phone: 'رقم غير صالح',
  card_expired: 'البطاقة منتهية الصلاحية',
  too_long: 'النص أطول من المسموح',
  invalid_name_text: 'الاسم أحرف عربية فقط',
};

const blank = (value: string | null | undefined): boolean => value == null || value.trim() === '';

/** Every empty or invalid item, in MISSING_ORDER. An empty list means complete. */
/** Today's date in Baghdad as YYYY-MM-DD (card expiry, specs/006 FR-030). */
export function baghdadToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Baghdad' }).format(now);
}

export function computeMissing(
  draft: DraftFields,
  imageSides: Iterable<'front' | 'back'>,
  today: string = baghdadToday(),
): MissingItem[] {
  const sides = new Set(imageSides);
  const found = new Map<MissingField, MissingCode>();

  if (!sides.has('front')) found.set('image_front', 'required');
  if (!sides.has('back')) found.set('image_back', 'required');

  for (const name of [...REQUIRED_NAME_FIELDS, 'family_number', 'address', 'landmark'] as const) {
    if (blank(draft[name])) found.set(name, 'required');
  }
  if (draft.no_surname) found.delete('surname');
  for (const name of [
    'birth_date',
    'birth_place',
    'issue_date',
    'expiry_date',
    'issuing_authority',
  ] as const) {
    if (blank(draft[name])) found.set(name, 'required');
  }
  if (draft.expiry_date && draft.expiry_date < today) found.set('card_expired', 'card_expired');

  if (blank(draft.national_id)) found.set('national_id', 'required');
  else if (normalizeNationalId(draft.national_id) === null)
    found.set('national_id', 'invalid_national_id');

  if (draft.location_lat == null || draft.location_lng == null) found.set('location', 'required');

  for (const name of ['area_id', 'tower_id', 'plan_id'] as const) {
    if (draft[name] == null) found.set(name, 'required');
  }

  if (blank(draft.phone_input)) found.set('phone', 'required');
  else if (normalizePhone(draft.phone_input) === null) found.set('phone', 'invalid_phone');

  return MISSING_ORDER.filter((f) => found.has(f)).map((field) => ({
    field,
    code: found.get(field)!,
  }));
}

/** True when the trimmed text exceeds its limit (the server refuses it with `too_long`). */
export function isTooLong(field: LimitedField, value: string | null | undefined): boolean {
  return value != null && [...value.trim()].length > TEXT_LIMITS[field];
}
