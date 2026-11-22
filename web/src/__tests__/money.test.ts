import { describe, expect, it } from 'vitest';

import { formatMoney, formatNumber, parseMoney } from '../lib/money';

describe('parseMoney (specs/004 FR-012)', () => {
  it.each([
    ['20000', 20000],
    ['20,000', 20000],
    [' 20000 ', 20000],
    ['٢٠٠٠٠', 20000],
    ['٢٠٬٠٠٠', 20000],
    ['۳۵۰۰۰', 35000],
    ['35 000', 35000],
    ['0', 0],
    ['10,000,000', 10000000],
  ])('%s → %d', (text, value) => {
    expect(parseMoney(text)).toBe(value);
  });

  it.each(['', '   ', '-5', '1.5', '20,000.5', 'abc', '20k', '1234567890'])(
    'rejects %j',
    (text) => {
      expect(parseMoney(text)).toBeNull();
    },
  );

  it('handles null and undefined', () => {
    expect(parseMoney(null)).toBeNull();
    expect(parseMoney(undefined)).toBeNull();
  });
});

describe('formatting', () => {
  it('groups thousands with Latin digits', () => {
    expect(formatNumber(20000)).toBe('20,000');
    expect(formatNumber(10000000)).toBe('10,000,000');
    expect(formatNumber(0)).toBe('0');
  });

  it('adds the dinar unit', () => {
    expect(formatMoney(35000)).toBe('35,000 د.ع');
  });
});
