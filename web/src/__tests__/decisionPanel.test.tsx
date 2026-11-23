/**
 * The decision area of the review file (specs/010 US2: FR-006 to FR-009): «قبول» with its
 * confirmation, the commission question on a return, «تم البت في هذا الطلب مسبقاً», and a decided
 * request shown read-only. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';

const accept = vi.fn();
const reject = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  accept: (...args: unknown[]) => accept(...args),
  reject: (...args: unknown[]) => reject(...args),
}));

import { DecisionPanel } from '../pages/admin/pending/DecisionPanel';
import { requestFile } from './fixtures/requestFile';

const onDecided = vi.fn();
const onRefresh = vi.fn();

beforeEach(() => {
  accept.mockReset();
  reject.mockReset();
  onDecided.mockReset();
  onRefresh.mockReset();
});
afterEach(cleanup);

function show(file = requestFile()) {
  render(<DecisionPanel file={file} onDecided={onDecided} onRefresh={onRefresh} />);
}

describe('DecisionPanel', () => {
  it('accepts a second subscription after the confirmation', async () => {
    const decided = requestFile({ status: 'approved' });
    accept.mockResolvedValue(decided);
    show();

    fireEvent.click(screen.getByRole('button', { name: 'قبول' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('T3C-1011');
    expect(screen.queryByText('هل تُحتسب عمولة للمسوّق؟')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد القبول' }));

    await vi.waitFor(() => expect(accept).toHaveBeenCalledWith(11, {}));
    await vi.waitFor(() => expect(onDecided).toHaveBeenCalledWith(decided));
  });

  it('asks «هل تُحتسب عمولة للمسوّق؟» on a return before accepting', async () => {
    accept.mockResolvedValue(requestFile({ type: 'return', status: 'approved' }));
    show(requestFile({ type: 'return' }));

    fireEvent.click(screen.getByRole('button', { name: 'قبول' }));
    await screen.findByText('هل تُحتسب عمولة للمسوّق؟');
    const confirm = screen.getByRole('button', { name: 'تأكيد القبول' }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);

    fireEvent.click(screen.getByRole('radio', { name: 'لا' }));
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);

    await vi.waitFor(() => expect(accept).toHaveBeenCalledWith(11, { counts_commission: false }));
  });

  it('says «تم البت في هذا الطلب مسبقاً» and reloads when another admin decided first', async () => {
    accept.mockRejectedValue(
      new ApiError('already_decided', 'تم البت في هذا الطلب مسبقاً', 409, { status: 'rejected' }),
    );
    show();

    fireEvent.click(screen.getByRole('button', { name: 'قبول' }));
    fireEvent.click(await screen.findByRole('button', { name: 'تأكيد القبول' }));

    expect(await screen.findByText('تم البت في هذا الطلب مسبقاً')).toBeTruthy();
    expect(onRefresh).toHaveBeenCalled();
    expect(onDecided).not.toHaveBeenCalled();
  });

  it('rejects through the reject dialog', async () => {
    reject.mockResolvedValue(requestFile({ status: 'rejected' }));
    show();

    fireEvent.click(screen.getByRole('button', { name: 'رفض' }));
    fireEvent.click(await screen.findByRole('radio', { name: 'صورة البطاقة غير واضحة' }));
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد الرفض' }));

    await vi.waitFor(() => expect(reject).toHaveBeenCalledWith(11, { reason: 'card_unclear' }));
    await vi.waitFor(() => expect(onDecided).toHaveBeenCalled());
  });

  it('shows a decided request read-only, with no buttons', () => {
    show(
      requestFile({
        status: 'rejected',
        decision: {
          status: 'rejected',
          by: 'أدمن تجريبي',
          at: '2026-11-23T11:00:00Z',
          counts_commission: null,
          despite_warnings: [],
          reason: 'other',
          label: 'طلب مكرر',
        },
      }),
    );
    expect(screen.queryByRole('button', { name: 'قبول' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'رفض' })).toBeNull();
    expect(screen.getByText('تم رفض الطلب')).toBeTruthy();
    expect((screen.getByLabelText('سبب الرفض') as HTMLInputElement).value).toBe('طلب مكرر');
    expect((screen.getByLabelText('بواسطة') as HTMLInputElement).value).toBe('أدمن تجريبي');
  });

  it('shows an accepted return with its commission answer', () => {
    show(
      requestFile({
        type: 'return',
        status: 'approved',
        decision: {
          status: 'approved',
          by: 'أدمن تجريبي',
          at: '2026-11-23T11:00:00Z',
          counts_commission: false,
          despite_warnings: [],
          reason: null,
          label: null,
        },
      }),
    );
    expect(screen.getByText('تم القبول')).toBeTruthy();
    expect((screen.getByLabelText('احتساب العمولة') as HTMLInputElement).value).toBe('لا');
  });
});
