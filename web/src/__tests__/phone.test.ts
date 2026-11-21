import { describe, expect, it } from 'vitest';

import { normalizePhone } from '../lib/phone';
import cases from './fixtures/phone_cases.json';

// The fixture is a copy of api/tests/fixtures/phone_cases.json — keep them identical.
describe('normalizePhone', () => {
  it.each(cases as { note: string; input: string; expected: string | null }[])(
    '$note',
    ({ input, expected }) => {
      expect(normalizePhone(input)).toBe(expected);
    },
  );

  it('treats null/undefined as invalid', () => {
    expect(normalizePhone(null)).toBeNull();
    expect(normalizePhone(undefined)).toBeNull();
  });
});
