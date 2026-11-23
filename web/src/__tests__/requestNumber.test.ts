import { describe, expect, it } from 'vitest';
import { parseRequestNumber } from '../lib/requestNumber';
import fixture from './fixtures/request_number_cases.json';

// specs/011 research R6; the same cases as api/tests/unit/test_request_number.py.
describe('parseRequestNumber', () => {
  it.each(fixture.cases)('$text', ({ text, number }) => {
    expect(parseRequestNumber(text)).toBe(number);
  });
});
