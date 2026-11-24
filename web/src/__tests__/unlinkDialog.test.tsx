/**
 * «التراجع عن الربط» (specs/013 US3: FR-004, FR-008, FR-009, FR-016): the recent links tab, the
 * required reason from the fixed list (no text), the body sent and the «already undone» answer.
 * Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { LinkList } from '../lib/links';
import { formatBaghdad } from '../lib/time';

const listAwaiting = vi.fn();
const listRecent = vi.fn();
const unlinkRequest = vi.fn();
vi.mock('../lib/links', async (original) => ({
  ...(await original<typeof import('../lib/links')>()),
  listAwaiting: (...args: unknown[]) => listAwaiting(...args),
  listRecent: (...args: unknown[]) => listRecent(...args),
  unlinkRequest: (...args: unknown[]) => unlinkRequest(...args),
}));

import AwaitingLink from '../pages/admin/links/AwaitingLink';

const LINKED: LinkList = {
  total: 1,
  items: [
    {
      id: 41,
      number_label: 'T3C-1041',
      full_name: 'عينة مربوطة',
      username: 'SMR01-07801234567',
      phone: '07801234567',
      tower_name: 'برج سمرة',
      tower_code: 'SMR01',
      plan_name: 'PLUS',
      marketer_name: 'مسوّق تجريبي',
      approved_at: '2026-11-22T10:00:00Z',
      linked_at: '2026-11-24T08:00:00Z',
      linked_by_name: 'أدمن الربط',
      link_id: 88,
    },
  ],
};
const EMPTY: LinkList = { total: 0, items: [] };

beforeEach(() => {
  listAwaiting.mockReset().mockResolvedValue(EMPTY);
  listRecent.mockReset();
  unlinkRequest.mockReset();
});
afterEach(cleanup);

async function openRecent() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AwaitingLink />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'المربوطة مؤخراً' }));
  return (await screen.findByText('T3C-1041')).closest('[data-testid="link-row"]') as HTMLElement;
}

async function openDialog() {
  fireEvent.click(within(await openRecent()).getByRole('button', { name: 'التراجع عن الربط' }));
  return screen.findByRole('dialog');
}

describe('«المربوطة مؤخراً»', () => {
  it('shows the link date and who linked', async () => {
    listRecent.mockResolvedValue(LINKED);
    const row = within(await openRecent());
    expect(row.getByText(new RegExp(formatBaghdad('2026-11-24T08:00:00Z')))).toBeTruthy();
    expect(row.getByText(/ربطه: أدمن الربط/)).toBeTruthy();
    expect(listRecent).toHaveBeenLastCalledWith(undefined, 0);
  });
});

describe('UnlinkDialog', () => {
  it('needs one of the four fixed reasons and has no text field', async () => {
    listRecent.mockResolvedValue(LINKED);
    const dialog = within(await openDialog());

    for (const label of ['لم يُربط فعلياً في SAS', 'ضُغط بالخطأ', 'ربط طلب آخر بدله', 'سبب آخر'])
      expect(dialog.getByRole('radio', { name: label })).toBeTruthy();
    expect(dialog.queryByRole('textbox')).toBeNull();
    const confirm = dialog.getByRole('button', { name: 'تأكيد التراجع' }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.click(confirm);
    expect(unlinkRequest).not.toHaveBeenCalled();
  });

  it('sends the reason and the current link id, then refreshes', async () => {
    listRecent.mockResolvedValueOnce(LINKED).mockResolvedValue(EMPTY);
    unlinkRequest.mockResolvedValue({ ...LINKED.items[0], linked_at: null, link_id: null });
    const dialog = within(await openDialog());

    fireEvent.click(dialog.getByRole('radio', { name: 'سبب آخر' }));
    fireEvent.click(dialog.getByRole('button', { name: 'تأكيد التراجع' }));

    await vi.waitFor(() =>
      expect(unlinkRequest).toHaveBeenCalledWith(41, { reason: 'other', link_id: 88 }),
    );
    expect(await screen.findByText('تم التراجع عن ربط T3C-1041')).toBeTruthy();
    expect(await screen.findByText('لا توجد طلبات مربوطة')).toBeTruthy();
  });

  it('shows the server message when the link was already undone, and refreshes', async () => {
    listRecent.mockResolvedValueOnce(LINKED).mockResolvedValue(EMPTY);
    unlinkRequest.mockRejectedValue(
      new ApiError('already_unlinked', 'تم التراجع عن هذا الربط مسبقاً', 409),
    );
    const dialog = within(await openDialog());

    fireEvent.click(dialog.getByRole('radio', { name: 'ضُغط بالخطأ' }));
    fireEvent.click(dialog.getByRole('button', { name: 'تأكيد التراجع' }));

    expect(await screen.findByText('تم التراجع عن هذا الربط مسبقاً')).toBeTruthy();
    await vi.waitFor(() => expect(listRecent.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('cancel does not undo', async () => {
    listRecent.mockResolvedValue(LINKED);
    const dialog = within(await openDialog());
    fireEvent.click(dialog.getByRole('button', { name: 'إلغاء' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(unlinkRequest).not.toHaveBeenCalled();
  });
});
