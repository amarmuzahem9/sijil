/**
 * «طلبات بالانتظار» (specs/010 US1, FR-002): the rows, the reason filter, the count and the empty
 * state. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PendingList } from '../lib/adminRequests';
import { formatBaghdad } from '../lib/time';

const listPending = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  listPending: (...args: unknown[]) => listPending(...args),
}));

import PendingListPage from '../pages/admin/pending/PendingList';

const TWO: PendingList = {
  total: 2,
  items: [
    {
      id: 11,
      number_label: 'T3C-1011',
      type: 'additional',
      reasons: ['family_exists', 'numbers_edited'],
      marketer_name: 'مسوّق تجريبي',
      full_name: 'تجربة اختبار نموذج',
      tower_code: 'ALM03',
      tower_name: 'برج العلم 3',
      submitted_at: '2026-11-23T20:30:00Z',
    },
    {
      id: 12,
      number_label: 'T3C-1012',
      type: 'return',
      reasons: ['return'],
      marketer_name: 'مسوّق ثاني',
      full_name: 'عينة نموذجية',
      tower_code: 'SMR01',
      tower_name: 'برج سمرة',
      submitted_at: '2026-11-23T21:00:00Z',
    },
  ],
};

beforeEach(() => {
  listPending.mockReset();
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PendingListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PendingList', () => {
  it('shows each row with its labels, Baghdad time and a link to the file', async () => {
    listPending.mockResolvedValue(TWO);
    show();

    const row = (await screen.findByText('T3C-1011')).closest('a') as HTMLElement;
    expect(row.getAttribute('href')).toBe('/admin/pending/11');
    const inRow = within(row);
    expect(inRow.getByText('النوع: اشتراك إضافي')).toBeTruthy();
    expect(inRow.getByText('اشتراك إضافي')).toBeTruthy(); // the reason chip
    expect(inRow.getByText('تعديل الأرقام')).toBeTruthy();
    expect(inRow.getByText('تجربة اختبار نموذج')).toBeTruthy();
    expect(inRow.getByText(/مسوّق تجريبي/)).toBeTruthy();
    expect(inRow.getByText(/برج العلم 3/)).toBeTruthy();
    // Shown in Baghdad time (20:30 UTC is 23:30 in Baghdad).
    expect(inRow.getByText(formatBaghdad('2026-11-23T20:30:00Z'))).toBeTruthy();
    expect(screen.getByText('العدد: 2')).toBeTruthy();
  });

  it('filters by reason through the server', async () => {
    listPending.mockResolvedValue(TWO);
    show();
    await screen.findByText('T3C-1011');
    expect(listPending).toHaveBeenLastCalledWith(undefined);

    fireEvent.click(screen.getByRole('button', { name: 'تعارض بالأرقام' }));
    await vi.waitFor(() => expect(listPending).toHaveBeenLastCalledWith('numbers_conflict'));

    fireEvent.click(screen.getByRole('button', { name: 'الكل' }));
    await vi.waitFor(() => expect(listPending).toHaveBeenLastCalledWith(undefined));
  });

  it('says so when nothing is pending', async () => {
    listPending.mockResolvedValue({ total: 0, items: [] });
    show();
    expect(await screen.findByText('لا توجد طلبات بالانتظار')).toBeTruthy();
  });
});
