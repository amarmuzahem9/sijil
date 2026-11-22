import { describe, expect, it } from 'vitest';

import {
  computeMissing,
  isTooLong,
  MISSING_ORDER,
  TEXT_LIMITS,
  type DraftFields,
} from '../lib/draftValidation';
import { cleanArabicName } from '../lib/arabicName';
import { sendable } from '../lib/draftFormController';
import { NAME_FIELDS, REQUIRED_NAME_FIELDS } from '../lib/nameFields';
import { normalizeNationalId } from '../lib/nationalId';
import fixture from './fixtures/draft_validation_cases.json';

// The fixture is a copy of api/tests/fixtures/draft_validation_cases.json — keep them identical.
interface DraftCase {
  note: string;
  draft: DraftFields;
  images: ('front' | 'back')[];
  missing: { field: string; code: string }[];
}

describe('normalizeNationalId', () => {
  it.each(fixture.national_id as { note: string; input: string; expected: string | null }[])(
    '$note',
    ({ input, expected }) => {
      expect(normalizeNationalId(input)).toBe(expected);
    },
  );

  it('treats null/undefined as invalid', () => {
    expect(normalizeNationalId(null)).toBeNull();
    expect(normalizeNationalId(undefined)).toBeNull();
  });
});

describe('computeMissing', () => {
  it.each(fixture.drafts as DraftCase[])('$note', ({ draft, images, missing }) => {
    expect(computeMissing(draft, images, fixture.today)).toEqual(missing);
  });

  it('uses the same page order and limits as the server', () => {
    expect([...MISSING_ORDER]).toEqual(fixture.missing_order);
    expect(TEXT_LIMITS).toEqual(fixture.limits);
  });
});

describe('isTooLong', () => {
  it('counts characters after trimming', () => {
    expect(isTooLong('landmark', 'أ'.repeat(200))).toBe(false);
    expect(isTooLong('landmark', 'أ'.repeat(201))).toBe(true);
    expect(isTooLong('landmark', `  ${'أ'.repeat(200)}  `)).toBe(false);
    expect(isTooLong('address', null)).toBe(false);
  });
});

describe('cleanArabicName (specs/005 research.md R12)', () => {
  it.each(
    fixture.names as { note: string; input: string; expected: string | null; valid: boolean }[],
  )('$note', ({ input, expected, valid }) => {
    const result = cleanArabicName(input);
    expect(result.ok).toBe(valid);
    if (result.ok) expect(result.value).toBe(expected);
  });

  it('lists every required name in page order, and never the optional ones', () => {
    const names = MISSING_ORDER.filter((f) => (NAME_FIELDS as readonly string[]).includes(f));
    expect(names).toEqual(REQUIRED_NAME_FIELDS);
    expect(names).not.toContain('mother_third_name');
    expect(names).not.toContain('mother_surname');
  });
});

describe('sendable: refused values are never sent', () => {
  it('blocks a name with a digit or a Latin letter, and over-length text', () => {
    expect(sendable('first_name', 'علي')).toBe(true);
    expect(sendable('first_name', '')).toBe(true);
    expect(sendable('first_name', 'علي2')).toBe(false);
    expect(sendable('surname', 'Ali')).toBe(false);
    expect(sendable('surname', 'ا'.repeat(51))).toBe(false);
    expect(sendable('address', 'حي 12')).toBe(true); // digits are fine outside names
  });
});
