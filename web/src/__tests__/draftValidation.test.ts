import { describe, expect, it } from 'vitest';

import {
  computeMissing,
  isTooLong,
  MISSING_ORDER,
  TEXT_LIMITS,
  type DraftFields,
} from '../lib/draftValidation';
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
    expect(computeMissing(draft, images)).toEqual(missing);
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
