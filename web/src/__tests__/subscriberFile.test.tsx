/**
 * The subscriber's file (docs/system.md v1.24 §10 item 4; specs/018 US2, FR-007 to FR-010): the
 * record by source, identity data and images only when the server sent them, linked records with
 * their reasons, the history, and no edit control. Synthetic values only.
 */
import { cleanup, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ResultRow, SubscriberFile as FileData } from '../lib/subscribers';

const getSubscriberFile = vi.fn();
vi.mock('../lib/subscribers', async (original) => ({
  ...(await original<typeof import('../lib/subscribers')>()),
  getSubscriberFile: (...args: unknown[]) => getSubscriberFile(...args),
}));
const requestImageUrl = vi.fn();
vi.mock('../lib/adminRequests', async (original) => ({
  ...(await original<typeof import('../lib/adminRequests')>()),
  requestImageUrl: (...args: unknown[]) => requestImageUrl(...args),
}));

import SubscriberFile from '../pages/admin/subscribers/SubscriberFile';

const ROW: Omit<ResultRow, 'source' | 'ref' | 'full_name'> = {
  number_label: null,
  legacy_number: null,
  tower_name: null,
  tower_code: null,
  phone: '07801234567',
  status: null,
  registered_at: '2026-01-01T09:00:00Z',
  deleted: false,
};

const REVIEW_FILE: FileData = {
  record: {
    ...ROW,
    source: 'sijil',
    ref: '42',
    number_label: 'T3C-1042',
    full_name: 'تجربة اختبار نموذج',
    tower_name: 'العلم 3',
    tower_code: 'ALM03',
    status: 'linked',
    username: 'ALM03-07801234567',
    type: 'new',
    marketer_name: 'مسوّق تجريبي',
    national_id: '199012345678',
    family_number: '1990A1234567890123',
    card_fields: { birth_date: '1990-01-10', expiry_date: '2030-01-01' },
    images: [
      { id: 'img-front', side: 'front' },
      { id: 'img-back', side: 'back' },
    ],
  },
  history: [
    { kind: 'submitted', at: '2026-11-01T09:00:00Z', by_name: 'مسوّق تجريبي' },
    { kind: 'approved', at: '2026-11-01T09:00:00Z', by_name: null },
    { kind: 'pinned', at: '2026-11-01T10:00:00Z', by_name: 'مراجع تجريبي', field: 'national_id' },
    { kind: 'unlinked', at: '2026-11-02T10:00:00Z', by_name: 'رابط تجريبي', reason: 'by_mistake' },
  ],
  linked: [
    {
      reason: 'same_phone',
      row: {
        ...ROW,
        source: 'sas',
        ref: '918',
        full_name: 'مشترك SAS تجريبي',
        status: '2026-12-01',
      },
    },
    {
      reason: 'same_family',
      row: {
        ...ROW,
        source: 'legacy',
        ref: '7',
        full_name: 'مشترك قديم تجريبي',
        legacy_number: 'T3C-077',
      },
    },
  ],
  more_linked: 3,
};

beforeEach(() => {
  getSubscriberFile.mockReset();
  requestImageUrl.mockReset();
  requestImageUrl.mockResolvedValue('blob:fake');
});
afterEach(cleanup);

function show(path = '/admin/subscribers/sijil/42') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/subscribers/:source/:ref" element={<SubscriberFile />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SubscriberFile (specs/018 US2)', () => {
  it('shows a request with its identity block and images for a review admin', async () => {
    getSubscriberFile.mockResolvedValue(REVIEW_FILE);
    show();
    expect(await screen.findByText('تجربة اختبار نموذج')).toBeTruthy();
    expect(getSubscriberFile).toHaveBeenCalledWith('sijil', '42');
    expect(screen.getByText('طلب سِجلّ')).toBeTruthy();
    const identity = screen.getByTestId('identity-block');
    expect(within(identity).getByText('199012345678')).toBeTruthy();
    expect(within(identity).getByText('1990A1234567890123')).toBeTruthy();
    expect(await screen.findAllByRole('img')).toHaveLength(2);
    expect(requestImageUrl).toHaveBeenCalledWith('img-front', 'request');
  });

  it('lists linked records with their reasons, each opening its own file', async () => {
    getSubscriberFile.mockResolvedValue(REVIEW_FILE);
    show();
    const linked = await screen.findAllByTestId('linked-record');
    expect(linked).toHaveLength(2);
    expect(within(linked[0]).getByText('نفس الهاتف')).toBeTruthy();
    expect(within(linked[0]).getByRole('link').getAttribute('href')).toBe(
      '/admin/subscribers/sas/918',
    );
    expect(within(linked[1]).getByText('نفس العائلة')).toBeTruthy();
    expect(screen.getByText('و 3 سجلات أخرى')).toBeTruthy();
  });

  it('shows the history in Arabic, without any number value', async () => {
    getSubscriberFile.mockResolvedValue(REVIEW_FILE);
    show();
    const lines = await screen.findAllByTestId('history-line');
    expect(lines).toHaveLength(4);
    expect(lines[0].textContent).toContain('أُرسل');
    expect(lines[1].textContent).toContain('قُبل تلقائياً');
    expect(lines[2].textContent).toContain('تثبيت رقم');
    expect(lines[2].textContent).toContain('الرقم الوطني');
    expect(lines[3].textContent).toContain('ضُغط بالخطأ');
    expect(lines.map((l) => l.textContent).join(' ')).not.toContain('199012345678');
  });

  it('has no identity block or images when the server sent none (link, reports)', async () => {
    const record = { ...REVIEW_FILE.record };
    delete record.national_id;
    delete record.family_number;
    delete record.card_fields;
    delete record.images;
    getSubscriberFile.mockResolvedValue({ ...REVIEW_FILE, record });
    show();
    await screen.findByText('تجربة اختبار نموذج');
    expect(screen.queryByTestId('identity-block')).toBeNull();
    expect(screen.queryAllByRole('img')).toHaveLength(0);
    expect(requestImageUrl).not.toHaveBeenCalled();
  });

  it('shows the legacy marks', async () => {
    getSubscriberFile.mockResolvedValue({
      record: {
        ...ROW,
        source: 'legacy',
        ref: '7',
        full_name: 'مشترك قديم تجريبي',
        legacy_number: 'T3C-077',
        status_text: 'ملغي',
        incomplete: true,
        extra: { mother_name: 'عينة', mother_father_name: null, birth_date: null },
      },
      history: [],
      linked: [],
      more_linked: 0,
    });
    show('/admin/subscribers/legacy/7');
    expect(await screen.findByText('غير مكتمل')).toBeTruthy();
    expect(screen.getByText('ملغي')).toBeTruthy();
    expect(screen.getByText('عينة')).toBeTruthy();
    expect(screen.getByText('T3C-077')).toBeTruthy();
  });

  it('shows the SAS marks', async () => {
    getSubscriberFile.mockResolvedValue({
      record: {
        ...ROW,
        source: 'sas',
        ref: '918',
        full_name: 'مشترك SAS تجريبي',
        username: 'ZZT01-07801234567',
        expires_at: '2026-12-01T00:00:00Z',
        missing_since: '2026-11-20T00:00:00Z',
        no_documents: true,
      },
      history: [],
      linked: [],
      more_linked: 0,
    });
    show('/admin/subscribers/sas/918');
    expect(await screen.findByText('بلا مستمسكات في سِجلّ')).toBeTruthy();
    expect(screen.getByText(/غير موجود في آخر ملف/)).toBeTruthy();
    expect(screen.getByText(/حسب آخر استيراد/)).toBeTruthy();
  });

  it('shows a deleted request as «سجل محذوف»', async () => {
    getSubscriberFile.mockResolvedValue({
      record: {
        ...ROW,
        source: 'sijil',
        ref: '43',
        number_label: 'T3C-1043',
        full_name: null,
        phone: null,
        deleted: true,
      },
      history: [
        { kind: 'deleted', at: '2026-11-03T09:00:00Z', by_name: 'أدمن', reason: 'duplicate' },
      ],
      linked: [],
      more_linked: 0,
    });
    show('/admin/subscribers/sijil/43');
    expect(await screen.findByText('سجل محذوف')).toBeTruthy();
    expect(screen.getByText('T3C-1043')).toBeTruthy();
  });

  it('offers no edit control (read-only)', async () => {
    getSubscriberFile.mockResolvedValue(REVIEW_FILE);
    show();
    await screen.findByText('تجربة اختبار نموذج');
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
    for (const name of [/تعديل/, /حفظ/, /حذف/]) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
  });
});
