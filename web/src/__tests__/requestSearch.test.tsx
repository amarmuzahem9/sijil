/**
 * «الطلبات»: the search box, the «تم الربط» tab and the §7.2 label (specs/012 US3, FR-010,
 * FR-012, FR-013). The server classifies the text; the page only skips texts under 2 characters.
 * Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetch = vi.hoisted(() => vi.fn());

vi.mock('../lib/api', async (original) => ({
  ...(await original<typeof import('../lib/api')>()),
  apiFetch,
}));

import { isSearchable } from '../lib/requestSearch';
import { STATUS_LABELS } from '../lib/requestStatus';
import Requests from '../pages/marketer/Requests';

const ROW = {
  type: 'new',
  submitted_at: '2026-11-24T09:00:00Z',
  tower_code: 'ALM03',
  tower_name: 'برج 3',
  rejection_label: null,
  deleted_at: null,
  deletion_label: null,
};

beforeEach(() => {
  apiFetch.mockImplementation(async (path: string) => {
    if (path.includes('q=')) {
      return {
        items: [
          {
            ...ROW,
            id: 1,
            number_label: 'T3C-1001',
            full_name: 'أحمد علي حسين',
            status: 'pending_review',
          },
          {
            ...ROW,
            id: 2,
            number_label: 'T3C-1002',
            full_name: 'سارة أحمد كريم',
            status: 'approved',
          },
        ],
      };
    }
    if (path.includes('status=pending_review')) {
      return {
        items: [
          {
            ...ROW,
            id: 5,
            number_label: 'T3C-1005',
            full_name: 'طلب بالانتظار',
            status: 'pending_review',
          },
        ],
      };
    }
    return { items: [] };
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function show(entry = '/requests?tab=pending') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Requests />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const box = () => screen.getByRole('searchbox', { name: 'بحث بالاسم أو الهاتف أو رقم الطلب' });
const searched = () => apiFetch.mock.calls.map(([p]) => String(p)).filter((p) => p.includes('q='));

describe('isSearchable', () => {
  it.each([
    ['', false],
    [' ', false],
    ['ت', false],
    [' ت ', false],
    ['تج', true],
    ['10', true],
  ])('%j → %s', (text, expected) => {
    expect(isSearchable(text)).toBe(expected);
  });
});

describe('the search box', () => {
  it('2 characters or more search all statuses and replace the tab list', async () => {
    show();
    await screen.findByText('طلب بالانتظار');
    fireEvent.change(box(), { target: { value: 'أحمد' } });
    await screen.findByText('سارة أحمد كريم');
    expect(searched().at(-1)).toBe(`/api/requests?q=${encodeURIComponent('أحمد')}`);
    expect(screen.getByText('أحمد علي حسين')).toBeTruthy();
    expect(screen.getByText(STATUS_LABELS.approved)).toBeTruthy();
    expect(screen.queryByText('طلب بالانتظار')).toBeNull();
    expect(screen.queryByRole('tablist')).toBeNull();
  });

  it('one character does not search', async () => {
    show();
    await screen.findByText('طلب بالانتظار');
    fireEvent.change(box(), { target: { value: 'أ' } });
    await new Promise((r) => setTimeout(r, 400));
    expect(searched()).toEqual([]);
    expect(screen.getByText('طلب بالانتظار')).toBeTruthy();
  });

  it('clearing the box returns to the tab', async () => {
    show();
    fireEvent.change(box(), { target: { value: 'أحمد' } });
    await screen.findByText('سارة أحمد كريم');
    fireEvent.change(box(), { target: { value: '' } });
    await screen.findByText('طلب بالانتظار');
    expect(screen.getByRole('tablist')).toBeTruthy();
  });

  it('no match: «لا توجد نتائج»', async () => {
    apiFetch.mockImplementation(async () => ({ items: [] }));
    show();
    fireEvent.change(box(), { target: { value: 'غير موجود' } });
    expect(await screen.findByText('لا توجد نتائج')).toBeTruthy();
  });
});

describe('tabs and labels', () => {
  it('«تم الربط» asks for linked requests', async () => {
    show('/requests?tab=linked');
    await waitFor(() =>
      expect(apiFetch.mock.calls.map(([p]) => p)).toContain('/api/requests?status=linked'),
    );
  });

  it('approved reads «مقبول (بانتظار الربط)» (§7.2)', () => {
    expect(STATUS_LABELS.approved).toBe('مقبول (بانتظار الربط)');
  });
});
