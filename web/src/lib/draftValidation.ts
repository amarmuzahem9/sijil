/**
 * Client mirror of api/app/services/draft_validation.py (specs/005 data-model.md › "Validation
 * rules"). Gives instant feedback; the server's `missing` list is authoritative.
 * Both sides are tested against __tests__/fixtures/draft_validation_cases.json.
 */
import { normalizeNationalId } from './nationalId';
import { normalizePhone } from './phone';

/** Page order (FR-003): card images, card data, location, subscription, phone. */
export const MISSING_ORDER = [
  'image_front',
  'image_back',
  'subscriber_name',
  'national_id',
  'family_number',
  'location',
  'address',
  'landmark',
  'area_id',
  'tower_id',
  'plan_id',
  'phone',
] as const;

export type MissingField = (typeof MISSING_ORDER)[number];
export type MissingCode = 'required' | 'invalid_national_id' | 'invalid_phone';

export interface MissingItem {
  field: MissingField;
  code: MissingCode;
}

/** Same limits as data-model.md › drafts and api/app/models/draft.py TEXT_LIMITS. */
export const TEXT_LIMITS = {
  subscriber_name: 100,
  national_id: 30,
  family_number: 30,
  address: 300,
  landmark: 200,
  phone_input: 30,
} as const;

export type LimitedField = keyof typeof TEXT_LIMITS;

export interface DraftFields {
  subscriber_name?: string | null;
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
}

export const FIELD_LABELS: Record<MissingField, string> = {
  image_front: 'وجه البطاقة',
  image_back: 'ظهر البطاقة',
  subscriber_name: 'الاسم',
  national_id: 'الرقم الوطني',
  family_number: 'الرقم العائلي',
  location: 'موقع البيت على الخريطة',
  address: 'العنوان',
  landmark: 'أقرب نقطة دالّة',
  area_id: 'المنطقة',
  tower_id: 'البرج',
  plan_id: 'الفئة',
  phone: 'هاتف المشترك',
};

export const CODE_MESSAGES: Record<MissingCode | 'too_long', string> = {
  required: 'مطلوب',
  invalid_national_id: 'الرقم الوطني 12 رقماً',
  invalid_phone: 'رقم غير صالح',
  too_long: 'النص أطول من المسموح',
};

const blank = (value: string | null | undefined): boolean => value == null || value.trim() === '';

/** Every empty or invalid item, in MISSING_ORDER. An empty list means complete. */
export function computeMissing(
  draft: DraftFields,
  imageSides: Iterable<'front' | 'back'>,
): MissingItem[] {
  const sides = new Set(imageSides);
  const found = new Map<MissingField, MissingCode>();

  if (!sides.has('front')) found.set('image_front', 'required');
  if (!sides.has('back')) found.set('image_back', 'required');

  for (const name of ['subscriber_name', 'family_number', 'address', 'landmark'] as const) {
    if (blank(draft[name])) found.set(name, 'required');
  }

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
