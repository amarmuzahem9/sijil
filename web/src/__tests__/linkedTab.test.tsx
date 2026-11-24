/**
 * A linked request for the marketer (specs/013 US2: FR-017, FR-018): the «تم الربط» row shows its
 * link date; the request page shows «تاريخ الربط» and keeps the link message. Synthetic values only.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RequestListItem, SubmittedRequest } from '../lib/requests';
import { formatBaghdad } from '../lib/time';

const listRequests = vi.fn();
vi.mock('../lib/requests', async (original) => ({
  ...(await original<typeof import('../lib/requests')>()),
  listRequests: (...args: unknown[]) => listRequests(...args),
}));

import { RequestResultView } from '../pages/marketer/RequestResult';
import { SubmittedTab } from '../pages/marketer/SubmittedTab';

afterEach(cleanup);

const LINKED_AT = '2026-11-24T20:30:00Z';

const item: RequestListItem = {
  id: 9,
  number_label: 'T3C-1009',
  full_name: 'تجربة اختبار نموذج مثال التجريبي',
  status: 'linked',
  type: 'new',
  submitted_at: '2026-11-20T10:00:00Z',
  tower_code: 'ALM03',
  tower_name: 'برج العلم 3',
  rejection_label: null,
  deleted_at: null,
  deletion_label: null,
  linked_at: LINKED_AT,
};

const request: SubmittedRequest = {
  id: 9,
  number: 1009,
  number_label: 'T3C-1009',
  type: 'new',
  status: 'linked',
  reasons: [],
  full_name: 'تجربة اختبار نموذج مثال التجريبي',
  tower_code: 'ALM03',
  tower_name: 'برج العلم 3',
  area_name: 'العلم',
  plan_name: 'PLUS',
  trial_price: 20000,
  second_price: 35000,
  phone: '07801234567',
  address: 'حي تجريبي',
  landmark: 'قرب نقطة تجريبية',
  marketer_name: 'مسوّق تجريبي',
  username: 'ALM03-07801234567',
  submitted_at: '2026-11-20T10:00:00Z',
  approved_at: '2026-11-20T10:00:00Z',
  result: 'linked',
  rejection_reason: null,
  rejection_label: null,
  rejected_at: null,
  link_message: 'طلب ربط جديد | رقم الطلب: #T3C-1009',
  linked_at: LINKED_AT,
};

describe('the «تم الربط» tab', () => {
  it('shows the link date on a linked row', async () => {
    listRequests.mockResolvedValue({ items: [item] });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <SubmittedTab statuses={['linked']} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const row = within(within(await screen.findByTestId('submitted-list')).getByRole('link'));
    expect(row.getByText(`تاريخ الربط: ${formatBaghdad(LINKED_AT)}`)).toBeTruthy();
    expect(row.getByText('تم الربط')).toBeTruthy();
  });

  it('shows no link date on a row that is not linked', async () => {
    listRequests.mockResolvedValue({
      items: [{ ...item, status: 'approved', linked_at: null }],
    });
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <SubmittedTab statuses={['approved']} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByTestId('submitted-list');
    expect(screen.queryByText(/تاريخ الربط/)).toBeNull();
  });
});

describe('the request page of a linked request', () => {
  it('shows «تاريخ الربط» and keeps the link message', () => {
    render(
      <MemoryRouter>
        <RequestResultView request={request} />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('request-status').textContent).toBe('تم الربط');
    expect(screen.getByText('تاريخ الربط')).toBeTruthy();
    expect(screen.getByText(formatBaghdad(LINKED_AT))).toBeTruthy();
    expect(screen.getByText(/طلب ربط جديد/)).toBeTruthy();
  });

  it('an accepted request has no «تاريخ الربط»', () => {
    render(
      <MemoryRouter>
        <RequestResultView
          request={{ ...request, status: 'approved', result: 'approved', linked_at: null }}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByText('تاريخ الربط')).toBeNull();
  });
});
