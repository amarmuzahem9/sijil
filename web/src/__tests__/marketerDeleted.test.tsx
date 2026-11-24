/**
 * «محذوف» for the marketer (specs/011 US5: FR-021, research R11): the list row keeps the number,
 * the tower and the date with a grey tag and the reason; the result page shows the same, with no
 * copy or share buttons. Synthetic values only.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RequestListItem, SubmittedRequest } from '../lib/requests';

const listRequests = vi.fn();
vi.mock('../lib/requests', async (original) => ({
  ...(await original<typeof import('../lib/requests')>()),
  listRequests: (...args: unknown[]) => listRequests(...args),
}));

import { RequestResultView } from '../pages/marketer/RequestResult';
import { SubmittedTab } from '../pages/marketer/SubmittedTab';

afterEach(cleanup);

const deletedItem: RequestListItem = {
  id: 7,
  number_label: 'T3C-1007',
  full_name: null,
  status: 'pending_review',
  type: 'new',
  submitted_at: '2026-11-23T10:00:00Z',
  tower_code: 'ALM03',
  tower_name: 'برج العلم 3',
  rejection_label: null,
  deleted_at: '2026-11-24T09:30:00Z',
  deletion_label: 'طلب مكرر',
};

const liveItem: RequestListItem = {
  ...deletedItem,
  id: 8,
  number_label: 'T3C-1008',
  full_name: 'تجربة اختبار نموذج مثال التجريبي',
  deleted_at: null,
  deletion_label: null,
};

const deletedRequest: SubmittedRequest = {
  id: 7,
  number: 1007,
  number_label: 'T3C-1007',
  type: 'new',
  status: 'pending_review',
  reasons: [],
  full_name: null,
  tower_code: 'ALM03',
  tower_name: 'برج العلم 3',
  area_name: null,
  plan_name: null,
  trial_price: null,
  second_price: null,
  phone: null,
  address: null,
  landmark: null,
  marketer_name: null,
  username: null,
  submitted_at: '2026-11-23T10:00:00Z',
  approved_at: null,
  result: 'deleted',
  rejection_reason: null,
  rejection_label: null,
  rejected_at: null,
  deleted_at: '2026-11-24T09:30:00Z',
  deletion_label: 'طلب مكرر',
};

describe('the marketer list', () => {
  it('shows a deleted request with the grey tag, the reason, the number and the tower', async () => {
    listRequests.mockResolvedValue({ items: [deletedItem, liveItem] });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <SubmittedTab statuses={['pending_review']} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const rows = within(await screen.findByTestId('submitted-list')).getAllByRole('link');
    const row = within(rows[0]);
    expect(row.getByText('محذوف')).toBeTruthy();
    expect(row.getByText('سبب الحذف: طلب مكرر')).toBeTruthy();
    expect(row.getByText('#T3C-1007', { exact: false })).toBeTruthy();
    expect(row.getByText('برج العلم 3 (ALM03)')).toBeTruthy();
    // The live request keeps its name and has no tag.
    expect(within(rows[1]).getByText('تجربة اختبار نموذج مثال التجريبي')).toBeTruthy();
    expect(within(rows[1]).queryByText('محذوف')).toBeNull();
  });
});

describe('the result page of a deleted request', () => {
  it('shows «تم حذف الطلب» with the reason and the kept fields only, and no copy buttons', () => {
    render(
      <MemoryRouter>
        <RequestResultView request={deletedRequest} />
      </MemoryRouter>,
    );
    const result = screen.getByTestId('request-result');
    expect(within(result).getByText('تم حذف الطلب')).toBeTruthy();
    expect(within(result).getByText('سبب الحذف: طلب مكرر')).toBeTruthy();
    expect(within(result).getByText('#T3C-1007')).toBeTruthy();
    expect(within(result).getByText('برج العلم 3 (ALM03)')).toBeTruthy();
    expect(within(result).getByTestId('request-status').textContent).toBe('محذوف');
    for (const label of ['الاسم', 'الفئة', 'الهاتف', 'اسم المستخدم'])
      expect(within(result).queryByText(label)).toBeNull();
    expect(screen.queryByRole('button', { name: /نسخ/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /مشاركة/ })).toBeNull();
  });
});
