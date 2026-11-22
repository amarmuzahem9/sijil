import { describe, expect, it } from 'vitest';

import { tierRanges } from '../lib/settings';

describe('tierRanges (specs/004 US3)', () => {
  it('labels the default tiers', () => {
    expect(tierRanges([0, 30, 50])).toEqual(['0 إلى 29', '30 إلى 49', '50 فأكثر']);
  });

  it('works while rows are out of order', () => {
    expect(tierRanges([50, 0, 30])).toEqual(['50 فأكثر', '0 إلى 29', '30 إلى 49']);
  });

  it('marks empty and duplicated counts', () => {
    expect(tierRanges([0, null, 30, 30])).toEqual(['0 إلى 29', '—', '—', '—']);
  });

  it('groups thousands and handles a single tier', () => {
    expect(tierRanges([0, 1000])).toEqual(['0 إلى 999', '1,000 فأكثر']);
    expect(tierRanges([0])).toEqual(['0 فأكثر']);
  });
});
