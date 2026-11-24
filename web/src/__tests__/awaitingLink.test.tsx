/**
 * «بانتظار الربط» (specs/013 US1, FR-002, FR-003, FR-005, FR-006): the rows, the search, the
 * confirmation and the «already linked» answer. Synthetic values only.
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
const linkRequest = vi.fn();
vi.mock('../lib/links', async (original) => ({
  ...(await original<typeof import('../lib/links')>()),
  listAwaiting: (...args: unknown[]) => listAwaiting(...args),
  listRecent: (...args: unknown[]) => listRecent(...args),
  linkRequest: (...args: unknown[]) => linkRequest(...args),
}));

import AwaitingLink from '../pages/admin/links/AwaitingLink';

const ONE: LinkList = {
  total: 1,
  items: [
    {
      id: 21,
      number_label: 'T3C-1021',
      full_name: 'تجربة اختبار نموذج',
      username: 'ALM03-07801234567',
      phone: '07801234567',
      tower_name: 'برج العلم 3',
      tower_code: 'ALM03',
      plan_name: 'PLUS',
      marketer_name: 'مسوّق تجريبي',
      approved_at: '2026-11-23T20:30:00Z',
      linked_at: null,
      linked_by_name: null,
      link_id: null,
    },
  ],
};
const EMPTY: LinkList = { total: 0, items: [] };

beforeEach(() => {
  listAwaiting.mockReset();
  listRecent.mockReset();
  linkRequest.mockReset();
  listRecent.mockResolvedValue(EMPTY);
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AwaitingLink />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function row() {
  return (await screen.findByText('T3C-1021')).closest('[data-testid="link-row"]') as HTMLElement;
}

describe('AwaitingLink', () => {
  it('shows what SAS checking needs, in Baghdad time', async () => {
    listAwaiting.mockResolvedValue(ONE);
    show();

    const inRow = within(await row());
    expect(inRow.getByText('تجربة اختبار نموذج')).toBeTruthy();
    expect(inRow.getByText('ALM03-07801234567')).toBeTruthy();
    expect(inRow.getByText('07801234567')).toBeTruthy();
    expect(inRow.getByText(/برج العلم 3 \(ALM03\)/)).toBeTruthy();
    expect(inRow.getByText(/PLUS/)).toBeTruthy();
    expect(inRow.getByText(/مسوّق تجريبي/)).toBeTruthy();
    expect(inRow.getByText(new RegExp(formatBaghdad('2026-11-23T20:30:00Z')))).toBeTruthy();
    expect(screen.getByText('العدد: 1')).toBeTruthy();
    expect(listAwaiting).toHaveBeenLastCalledWith(undefined, 0);
  });

  it('searches through the server once 2 characters are typed', async () => {
    listAwaiting.mockResolvedValue(ONE);
    show();
    await row();

    const box = screen.getByLabelText('بحث برقم الطلب أو الهاتف أو اليوزر');
    fireEvent.change(box, { target: { value: '1' } });
    fireEvent.change(box, { target: { value: ' T3C-1021 ' } });
    await vi.waitFor(() => expect(listAwaiting).toHaveBeenLastCalledWith('T3C-1021', 0));
  });

  it('links after the confirmation and refreshes the list', async () => {
    listAwaiting.mockResolvedValueOnce(ONE).mockResolvedValue(EMPTY);
    linkRequest.mockResolvedValue({ ...ONE.items[0], linked_at: '2026-11-24T09:00:00Z' });
    show();

    fireEvent.click(within(await row()).getByRole('button', { name: 'تم الربط' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/T3C-1021/)).toBeTruthy();
    expect(within(dialog).getByText(/ALM03-07801234567/)).toBeTruthy();
    expect(linkRequest).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'تأكيد الربط' }));
    await vi.waitFor(() => expect(linkRequest).toHaveBeenCalledWith(21));
    expect(await screen.findByText('لا توجد طلبات بانتظار الربط')).toBeTruthy();
  });

  it('cancel does not link', async () => {
    listAwaiting.mockResolvedValue(ONE);
    show();
    fireEvent.click(within(await row()).getByRole('button', { name: 'تم الربط' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'إلغاء' }),
    );
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(linkRequest).not.toHaveBeenCalled();
  });

  it('shows the server message when another admin linked first, and refreshes', async () => {
    listAwaiting.mockResolvedValueOnce(ONE).mockResolvedValue(EMPTY);
    linkRequest.mockRejectedValue(new ApiError('already_linked', 'تم ربط هذا الطلب مسبقاً', 409));
    show();

    fireEvent.click(within(await row()).getByRole('button', { name: 'تم الربط' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'تأكيد الربط' }),
    );
    expect(await screen.findByText('تم ربط هذا الطلب مسبقاً')).toBeTruthy();
    await vi.waitFor(() => expect(listAwaiting.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('says so when nothing waits', async () => {
    listAwaiting.mockResolvedValue(EMPTY);
    show();
    expect(await screen.findByText('لا توجد طلبات بانتظار الربط')).toBeTruthy();
  });
});
