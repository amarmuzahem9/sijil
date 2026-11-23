/**
 * «طلب العودة للخدمة» and the numbers-conflict notice (specs/009 US1, FR-003, FR-004, FR-012).
 * Booleans and a basis only: nothing here can name the other subscriber.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DraftChecks } from '../lib/drafts';
import {
  IdConflictNotice,
  RETURN_TEXT,
  ReturnNotice,
} from '../pages/marketer/subscriber/ReturnNotice';

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

const SAME_PERSON: DraftChecks = {
  ...NONE,
  national_id_exists: true,
  return_available: true,
  return_basis: 'identity',
};

describe('ReturnNotice (identity)', () => {
  it('offers «طلب العودة للخدمة» for the same person', () => {
    const onChoose = vi.fn();
    render(
      <ReturnNotice
        basis="identity"
        checks={SAME_PERSON}
        onChoose={onChoose}
        onWithdraw={vi.fn()}
      />,
    );
    expect(screen.getByTestId('return-offer').textContent).toContain('المشترك لديه اشتراك سابق');
    fireEvent.click(screen.getByRole('button', { name: 'طلب العودة للخدمة' }));
    expect(onChoose).toHaveBeenCalledOnce();
  });

  it('shows the chosen state with «إلغاء»', () => {
    const onWithdraw = vi.fn();
    render(
      <ReturnNotice
        basis="identity"
        checks={{ ...SAME_PERSON, return_chosen: true }}
        onChoose={vi.fn()}
        onWithdraw={onWithdraw}
      />,
    );
    expect(screen.getByTestId('return-chosen').textContent).toContain(RETURN_TEXT.chosen);
    expect(screen.queryByRole('button', { name: 'طلب العودة للخدمة' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(onWithdraw).toHaveBeenCalledOnce();
  });

  it('shows the pending block', () => {
    render(
      <ReturnNotice
        basis="identity"
        checks={{ ...SAME_PERSON, return_chosen: true, return_pending: true }}
        onChoose={vi.fn()}
        onWithdraw={vi.fn()}
      />,
    );
    expect(screen.getByTestId('return-pending').textContent).toContain(
      'يوجد طلب سابق بالانتظار لهذا المشترك',
    );
  });

  it('stays hidden for another basis, no match or no checks', () => {
    render(
      <>
        <ReturnNotice basis="phone" checks={SAME_PERSON} onChoose={vi.fn()} onWithdraw={vi.fn()} />
        <ReturnNotice basis="identity" checks={NONE} onChoose={vi.fn()} onWithdraw={vi.fn()} />
        <ReturnNotice basis="identity" checks={undefined} onChoose={vi.fn()} onWithdraw={vi.fn()} />
      </>,
    );
    expect(screen.queryByTestId('return-offer')).toBeNull();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });
});

describe('IdConflictNotice', () => {
  it('tells the marketer the request will be reviewed, with no button', () => {
    render(<IdConflictNotice checks={{ ...NONE, id_conflict: true }} />);
    expect(screen.getByTestId('id-conflict').textContent).toBe(
      'الرقم الوطني مسجّل سابقاً ببيانات مختلفة، سيُراجع الطلب من الإدارة',
    );
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('shows nothing without a conflict', () => {
    render(<IdConflictNotice checks={NONE} />);
    expect(screen.queryByTestId('id-conflict')).toBeNull();
  });
});
