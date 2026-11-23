/**
 * Early warnings under the fields (specs/008 T034, T038, T043; FR-008 to FR-010): the national ID
 * and the phone show their message with no button (009 adds «إعادة مشترك للخدمة»); the family
 * shows «طلب اشتراك إضافي», then the confirmed state with «تراجع». Nothing shows without
 * `checks` (an older server) or without a match. The warnings never name the other subscriber.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DraftChecks } from '../lib/drafts';
import {
  FamilyMatchNotice,
  MATCH_TEXT,
  NationalIdExistsNotice,
  PhoneUsedNotice,
} from '../pages/marketer/subscriber/FamilyMatchNotice';

afterEach(cleanup);

const NONE: DraftChecks = {
  phone_used: false,
  national_id_exists: false,
  id_conflict: false,
  family_exists: false,
  additional_confirmed: false,
  return_available: false,
  return_basis: null,
  return_chosen: false,
  return_pending: false,
};

describe('NationalIdExistsNotice and PhoneUsedNotice', () => {
  it('show the message with no button when matched', () => {
    render(
      <>
        <NationalIdExistsNotice checks={{ ...NONE, national_id_exists: true }} />
        <PhoneUsedNotice checks={{ ...NONE, phone_used: true }} />
      </>,
    );
    expect(screen.getByTestId('national-id-exists').textContent).toBe('المشترك لديه اشتراك سابق');
    expect(screen.getByTestId('phone-used').textContent).toBe(
      'المشترك موجود سابقاً، هل يود العودة للخدمة؟',
    );
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('show nothing without a match or without checks', () => {
    render(
      <>
        <NationalIdExistsNotice checks={NONE} />
        <PhoneUsedNotice checks={undefined} />
      </>,
    );
    expect(screen.queryByTestId('national-id-exists')).toBeNull();
    expect(screen.queryByTestId('phone-used')).toBeNull();
  });
});

describe('FamilyMatchNotice', () => {
  it('offers «طلب اشتراك إضافي» while unconfirmed', () => {
    const onConfirm = vi.fn();
    render(
      <FamilyMatchNotice
        checks={{ ...NONE, family_exists: true }}
        onConfirm={onConfirm}
        onWithdraw={vi.fn()}
      />,
    );
    expect(screen.getByText(MATCH_TEXT.family)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'طلب اشتراك إضافي' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('shows the confirmed state with «تراجع»', () => {
    const onWithdraw = vi.fn();
    render(
      <FamilyMatchNotice
        checks={{ ...NONE, family_exists: true, additional_confirmed: true }}
        onConfirm={vi.fn()}
        onWithdraw={onWithdraw}
      />,
    );
    expect(screen.getByTestId('family-confirmed').textContent).toContain(MATCH_TEXT.confirmed);
    expect(screen.queryByRole('button', { name: 'طلب اشتراك إضافي' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'تراجع' }));
    expect(onWithdraw).toHaveBeenCalledTimes(1);
  });

  it('shows nothing without a family match or without checks', () => {
    const { container } = render(
      <>
        <FamilyMatchNotice checks={NONE} onConfirm={vi.fn()} onWithdraw={vi.fn()} />
        <FamilyMatchNotice checks={undefined} onConfirm={vi.fn()} onWithdraw={vi.fn()} />
      </>,
    );
    expect(container.textContent).toBe('');
  });
});
