/**
 * «المشتركون» search page (docs/system.md v1.24 §10 item 4; specs/018 US1, FR-003 to FR-006, FR-009).
 * Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { ResultRow, SearchResult } from '../lib/subscribers';

const searchSubscribers = vi.fn();
vi.mock('../lib/subscribers', async (original) => ({
  ...(await original<typeof import('../lib/subscribers')>()),
  searchSubscribers: (...args: unknown[]) => searchSubscribers(...args),
}));

import SubscriberSearch from '../pages/admin/subscribers/SubscriberSearch';

const BASE: ResultRow = {
  source: 'sijil',
  ref: '42',
  number_label: 'T3C-1042',
  legacy_number: null,
  full_name: 'تجربة اختبار نموذج',
  tower_name: 'العلم 3',
  tower_code: 'ALM03',
  phone: '07801234567',
  status: 'linked',
  registered_at: '2026-11-20T09:00:00Z',
  deleted: false,
};
const ROWS: ResultRow[] = [
  BASE,
  {
    ...BASE,
    source: 'legacy',
    ref: '7',
    number_label: null,
    legacy_number: 'T3C-077',
    full_name: 'مشترك قديم تجريبي',
    tower_name: null,
    tower_code: null,
    status: 'ملغي',
  },
  {
    ...BASE,
    source: 'sas',
    ref: '918',
    number_label: null,
    full_name: 'مشترك SAS تجريبي',
    tower_name: null,
    tower_code: 'ZZT01',
    status: '2026-12-01',
  },
  {
    ...BASE,
    ref: '43',
    number_label: 'T3C-1043',
    full_name: null,
    tower_name: null,
    tower_code: null,
    phone: null,
    status: null,
    registered_at: null,
    deleted: true,
  },
];

function result(items: ResultRow[], total = items.length): SearchResult {
  return { kind: 'phone', items, total };
}

beforeEach(() => {
  searchSubscribers.mockReset();
  searchSubscribers.mockResolvedValue(result(ROWS));
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SubscriberSearch />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function search(text: string) {
  fireEvent.change(screen.getByLabelText('بحث في المشتركين'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: 'بحث' }));
}

describe('SubscriberSearch (specs/018 US1)', () => {
  it('does not search before the admin asks', () => {
    show();
    expect(searchSubscribers).not.toHaveBeenCalled();
    expect(screen.getByText(/اسم أو هاتف أو يوزر أو رقم طلب/)).toBeTruthy();
  });

  it('shows one list across the three sources', async () => {
    show();
    search('0780 123 4567');
    expect(searchSubscribers).toHaveBeenCalledWith('0780 123 4567', 0);
    const rows = await screen.findAllByTestId('subscriber-row');
    expect(rows).toHaveLength(4);
    expect(screen.getByTestId('search-total').textContent).toBe('النتائج: 4');

    const request = within(rows[0]);
    expect(request.getByText('طلب سِجلّ')).toBeTruthy();
    expect(request.getByText('تجربة اختبار نموذج')).toBeTruthy();
    expect(request.getByText('تم الربط')).toBeTruthy(); // the §7.2 status label
    expect(request.getByText('العلم 3 (ALM03)')).toBeTruthy();

    const legacy = within(rows[1]);
    expect(legacy.getByText('مشترك قديم')).toBeTruthy();
    expect(legacy.getByText('ملغي')).toBeTruthy();
    expect(legacy.getByText('T3C-077')).toBeTruthy();

    const sas = within(rows[2]);
    expect(sas.getByText('مشترك SAS')).toBeTruthy();
    expect(sas.getByText('ينتهي 2026-12-01 حسب آخر استيراد')).toBeTruthy();

    const deleted = within(rows[3]);
    expect(deleted.getByText('سجل محذوف')).toBeTruthy();
    expect(deleted.getByText('T3C-1043')).toBeTruthy();
  });

  it('pages with «التالي» and «السابق»', async () => {
    searchSubscribers.mockResolvedValue(result([BASE], 120));
    show();
    search('تجربة');
    await screen.findAllByTestId('subscriber-row');
    fireEvent.click(screen.getByRole('button', { name: 'التالي' }));
    expect(searchSubscribers).toHaveBeenLastCalledWith('تجربة', 50);
    await screen.findAllByTestId('subscriber-row');
    fireEvent.click(screen.getByRole('button', { name: 'السابق' }));
    expect(searchSubscribers).toHaveBeenLastCalledWith('تجربة', 0);
  });

  it.each([
    ['search_unclear', 'اكتب اسماً (3 أحرف على الأقل) أو هاتفاً أو رقماً', 422],
    ['identity_search_forbidden', 'البحث بالرقم الوطني أو العائلي يحتاج صلاحية المراجعة', 403],
  ])('shows the Arabic answer of %s', async (code, message, status) => {
    searchSubscribers.mockRejectedValue(new ApiError(code, message, status));
    show();
    search('199012345678');
    expect(await screen.findByText(message)).toBeTruthy();
  });

  it('says when nothing is found', async () => {
    searchSubscribers.mockResolvedValue(result([]));
    show();
    search('زينب');
    expect(await screen.findByText('لا توجد نتائج')).toBeTruthy();
  });
});
