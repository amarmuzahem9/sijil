/**
 * A linked record that is a deleted request (specs/011 US4: FR-015, research R10): «سجل محذوف»
 * with its request number only; an unavailable one keeps «سجل غير متوفر». Synthetic values only.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import type { LinkedRecord, ReviewReason } from '../lib/adminRequests';
import { LinkedRecordCard } from '../pages/admin/pending/LinkedRecordCard';

afterEach(cleanup);

function record(partial: Partial<LinkedRecord>): LinkedRecord {
  return {
    source: 'sijil',
    ref: '5',
    available: false,
    full_name: null,
    username: null,
    phone: null,
    tower_code: null,
    tower_name: null,
    registered_at: null,
    status: null,
    image_ids: [],
    expiry: null,
    deleted: false,
    number_label: null,
    ...partial,
  };
}

function show(r: LinkedRecord) {
  const reason: ReviewReason = {
    reason: 'family_exists',
    state: 'open',
    added_at_review: false,
    basis: null,
    fields: [],
    record: r,
  };
  render(<LinkedRecordCard reason={reason} />);
}

describe('LinkedRecordCard', () => {
  it('shows «سجل محذوف» with the number and no fields or images', () => {
    show(record({ deleted: true, number_label: 'T3C-1005' }));
    expect(screen.getByText('سجل محذوف (#T3C-1005)')).toBeTruthy();
    expect(screen.queryByText('سجل غير متوفر')).toBeNull();
    expect(screen.queryByLabelText('الاسم')).toBeNull();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('keeps «سجل غير متوفر» for a record that is only unavailable', () => {
    show(record({ source: 'legacy' }));
    expect(screen.getByText('سجل غير متوفر')).toBeTruthy();
    expect(screen.queryByText(/سجل محذوف/)).toBeNull();
  });
});
