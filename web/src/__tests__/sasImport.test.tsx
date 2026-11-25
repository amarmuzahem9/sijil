/**
 * «مشتركو SAS» import page (specs/015 US1: FR-004–FR-007, FR-010; contracts/api.md): upload, the
 * counts, the prefix mapping table, grouped flagged rows with «تخطي للكل», confirmation, the summary
 * and the errors. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { SasFlaggedRow, SasImportSummary, SasPreview } from '../lib/sasImport';

const uploadSasFile = vi.fn();
const setSasChoices = vi.fn();
const confirmSasImport = vi.fn();
const cancelSasPreview = vi.fn();
vi.mock('../lib/sasImport', async (original) => ({
  ...(await original<typeof import('../lib/sasImport')>()),
  uploadSasFile: (...args: unknown[]) => uploadSasFile(...args),
  setSasChoices: (...args: unknown[]) => setSasChoices(...args),
  confirmSasImport: (...args: unknown[]) => confirmSasImport(...args),
  cancelSasPreview: (...args: unknown[]) => cancelSasPreview(...args),
}));

import { groupSasFlagged, sasFlagText } from '../lib/sasImport';
import SasImport from '../pages/admin/import/SasImport';

const FILE_LABEL = 'ملف مشتركي SAS (xlsx أو csv)';

function row(partial: Partial<SasFlaggedRow> & { index: number }): SasFlaggedRow {
  return {
    sas_id: String(100 + partial.index),
    username: `ALM03-0781000${String(partial.index).padStart(4, '0')}`,
    full_name: 'مشترك تجريبي',
    phone: '07810000001',
    username_phone: '07810000001',
    kind: 'new',
    flags: [],
    allowed: ['import', 'skip'],
    choice: null,
    ...partial,
  };
}

const FLAGGED: SasFlaggedRow[] = [
  row({ index: 8, username: null, flags: [{ code: 'username_missing' }], allowed: ['skip'] }),
  row({ index: 9, flags: [{ code: 'username_dup_file', rows: [10] }] }),
  row({ index: 10, flags: [{ code: 'username_dup_file', rows: [9] }] }),
  row({ index: 14, flags: [{ code: 'phone_in_sijil', requests: ['T3C-1004'] }] }),
];

const COUNTS: SasPreview['counts'] = {
  rows: 18,
  new: 18,
  update: 0,
  unchanged: 0,
  missing_from_file: 0,
  flagged: 4,
  waiting_choice: 4,
  same_username_in_sijil: 1,
  no_valid_phone: 1,
  username_no_phone: 1,
  date_unreadable: 1,
  phone_dup_file: 4,
  phone_in_legacy: 0,
};

function preview(partial: Partial<SasPreview> = {}): SasPreview {
  return {
    id: 'p-1',
    file_name: 'sas.csv',
    expires_at: '2026-11-25T10:00:00Z',
    counts: COUNTS,
    prefixes: [{ prefix: 'ZZQ07', rows: 2, tower_id: null, from_previous: false, chosen: false }],
    waiting_prefixes: 1,
    towers: [
      { id: 1, code: 'ALM03', name: 'العلم 3', is_active: true },
      { id: 2, code: 'SMR01', name: 'سمرة 1', is_active: false },
    ],
    flagged: FLAGGED,
    ...partial,
  };
}

function decided(): SasPreview {
  const flagged = FLAGGED.map(
    (r) => ({ ...r, choice: r.index === 9 ? 'import' : 'skip' }) as const,
  );
  return preview({
    flagged: flagged.map((r) => ({ ...r })),
    counts: { ...COUNTS, waiting_choice: 0 },
    prefixes: [{ prefix: 'ZZQ07', rows: 2, tower_id: 1, from_previous: false, chosen: true }],
    waiting_prefixes: 0,
  });
}

const SUMMARY: SasImportSummary = {
  import_id: 3,
  rows: 18,
  added: 15,
  updated: 0,
  unchanged: 0,
  skipped: 3,
  missing_marked: 0,
  missing_cleared: 0,
  without_phone: 1,
  prefixes_mapped: 1,
  skipped_rows: [
    { index: 8, sas_id: '107' },
    { index: 10, sas_id: '109' },
  ],
};

beforeEach(() => {
  for (const fn of [uploadSasFile, setSasChoices, confirmSasImport, cancelSasPreview])
    fn.mockReset();
});
afterEach(cleanup);

async function openPreview(initial: SasPreview = preview()) {
  uploadSasFile.mockResolvedValue(initial);
  render(<SasImport />);
  fireEvent.change(screen.getByLabelText(FILE_LABEL), {
    target: { files: [new File(['x'], 'sas.csv')] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'رفع ومعاينة' }));
  await screen.findByText('عدد الصفوف: 18');
}

function confirmButton(): HTMLButtonElement {
  return screen.getByRole('button', { name: 'تأكيد الاستيراد' }) as HTMLButtonElement;
}

describe('flag texts and groups', () => {
  it('reads every flag in Arabic with its detail', () => {
    expect(sasFlagText({ code: 'username_missing' })).toBe('بلا يوزر');
    expect(sasFlagText({ code: 'username_dup_file', rows: [10, 12] })).toBe(
      'يوزر مكرر في الملف (مع الصف 10، 12)',
    );
    expect(sasFlagText({ code: 'phone_in_sijil', requests: ['T3C-1004'] })).toBe(
      'الهاتف في طلب سِجلّ (T3C-1004)',
    );
  });

  it('groups rows in a fixed order, each row once', () => {
    const groups = groupSasFlagged([
      row({
        index: 3,
        flags: [{ code: 'phone_in_sijil', requests: ['T3C-1'] }, { code: 'username_dup_file' }],
      }),
      ...FLAGGED,
    ]);
    expect(groups.map((g) => g.code)).toEqual([
      'username_missing',
      'username_dup_file',
      'phone_in_sijil',
    ]);
    expect(groups[1].rows.map((r) => r.index)).toEqual([3, 9, 10]);
  });
});

describe('SasImport', () => {
  it('needs a file before uploading', () => {
    render(<SasImport />);
    expect(
      (screen.getByRole('button', { name: 'رفع ومعاينة' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it('shows an upload error in Arabic', async () => {
    uploadSasFile.mockRejectedValue(
      new ApiError('import_columns_missing', 'الملف ينقصه عمود: username', 422, {
        columns: ['username'],
      }),
    );
    render(<SasImport />);
    fireEvent.change(screen.getByLabelText(FILE_LABEL), {
      target: { files: [new File(['x'], 'sas.csv')] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'رفع ومعاينة' }));
    expect(await screen.findByText('الملف ينقصه عمود: username')).toBeTruthy();
  });

  it('shows the counts, the mapping table and the groups', async () => {
    await openPreview();
    for (const text of [
      'جديد: 18',
      'سيُحدَّث: 0',
      'بلا تغيير: 0',
      'تحتاج قراراً: 4',
      'نفس اليوزر في سِجلّ: 1',
      'بلا هاتف صالح: 1',
      'تاريخ غير مقروء: 1',
    ])
      expect(screen.getByText(text)).toBeTruthy();
    const table = screen.getByTestId('prefix-ZZQ07');
    expect(within(table).getByText('ZZQ07')).toBeTruthy();
    expect(within(table).getByText('2 صف')).toBeTruthy();
    const select = within(table).getByLabelText('برج ZZQ07') as HTMLSelectElement;
    const options = [...select.options].map((o) => o.textContent);
    expect(options).toEqual(['اختر البرج', 'بلا برج', 'العلم 3 (ALM03)', 'سمرة 1 (SMR01) — موقوف']);
    expect(
      within(screen.getByTestId('group-username_missing')).getByText('بلا يوزر (1)'),
    ).toBeTruthy();
    const row8 = screen.getByTestId('row-8');
    expect(within(row8).queryByRole('button', { name: 'استيراد' })).toBeNull();
    expect(
      within(screen.getByTestId('row-14')).getByText('الهاتف في طلب سِجلّ (T3C-1004)'),
    ).toBeTruthy();
  });

  it('sends a tower, or «بلا برج», for a prefix', async () => {
    await openPreview();
    setSasChoices.mockResolvedValue(preview());
    fireEvent.change(screen.getByLabelText('برج ZZQ07'), { target: { value: '1' } });
    await waitFor(() =>
      expect(setSasChoices).toHaveBeenCalledWith('p-1', [], [{ prefix: 'ZZQ07', tower_id: 1 }]),
    );
    fireEvent.change(screen.getByLabelText('برج ZZQ07'), { target: { value: 'none' } });
    await waitFor(() =>
      expect(setSasChoices).toHaveBeenLastCalledWith(
        'p-1',
        [],
        [{ prefix: 'ZZQ07', tower_id: null }],
      ),
    );
  });

  it('«تخطي للكل» skips the group, then one row can be imported again', async () => {
    await openPreview();
    const skipped = preview({
      flagged: FLAGGED.map((r) => (r.index === 9 || r.index === 10 ? { ...r, choice: 'skip' } : r)),
    });
    setSasChoices.mockResolvedValue(skipped);
    const group = screen.getByTestId('group-username_dup_file');
    fireEvent.click(within(group).getByRole('button', { name: 'تخطي للكل' }));
    await waitFor(() =>
      expect(setSasChoices).toHaveBeenCalledWith(
        'p-1',
        [
          { index: 9, choice: 'skip' },
          { index: 10, choice: 'skip' },
        ],
        [],
      ),
    );
    fireEvent.click(within(screen.getByTestId('row-9')).getByRole('button', { name: 'استيراد' }));
    await waitFor(() =>
      expect(setSasChoices).toHaveBeenLastCalledWith('p-1', [{ index: 9, choice: 'import' }], []),
    );
  });

  it('keeps the confirmation closed while a row or a prefix waits', async () => {
    await openPreview();
    expect(confirmButton().disabled).toBe(true);
    expect(screen.getByText('بقيت 4 صفوف بلا اختيار')).toBeTruthy();
    expect(screen.getByText('بقيت 1 بادئة بلا برج')).toBeTruthy();
    cleanup();
    await openPreview({ ...decided(), waiting_prefixes: 1 });
    expect(confirmButton().disabled).toBe(true);
    cleanup();
    await openPreview(decided());
    expect(confirmButton().disabled).toBe(false);
  });

  it('confirms through the dialog and shows the summary', async () => {
    await openPreview(decided());
    confirmSasImport.mockResolvedValue(SUMMARY);
    fireEvent.click(confirmButton());
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/سيُضاف 15 ويُحدَّث 0/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'استيراد' }));
    expect(await screen.findByText('تم الاستيراد')).toBeTruthy();
    expect(confirmSasImport).toHaveBeenCalledWith('p-1');
    expect(screen.getByText('المضاف: 15')).toBeTruthy();
    expect(screen.getByText('بادئات رُبطت: 1')).toBeTruthy();
    expect(screen.getByText('الصفوف المتخطّاة: الصف 8 (SAS 107)، الصف 10 (SAS 109)')).toBeTruthy();
  });

  it('reloads the rows that need a new choice when the data changed', async () => {
    await openPreview(decided());
    const changed = decided();
    changed.flagged = [
      ...changed.flagged,
      row({ index: 2, flags: [{ code: 'phone_in_sijil', requests: ['T3C-1009'] }] }),
    ];
    changed.counts = { ...changed.counts, waiting_choice: 1 };
    confirmSasImport.mockRejectedValue(
      new ApiError('preview_changed', 'تغيّرت البيانات منذ المعاينة، راجع الصفوف المعلّمة', 409, {
        preview: changed,
      }),
    );
    fireEvent.click(confirmButton());
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'استيراد' }),
    );
    expect(
      await screen.findByText('تغيّرت البيانات منذ المعاينة، راجع الصفوف المعلّمة'),
    ).toBeTruthy();
    expect(screen.getByTestId('row-2')).toBeTruthy();
    // The page is hidden from the accessibility tree until the dialog has closed.
    await waitFor(() => expect(confirmButton().disabled).toBe(true));
  });

  it('pages a large group by 200 rows', async () => {
    const many = Array.from({ length: 250 }, (_, i) =>
      row({ index: 100 + i, flags: [{ code: 'phone_in_sijil', requests: ['T3C-1'] }] }),
    );
    await openPreview(preview({ flagged: many }));
    expect(screen.getAllByTestId(/^row-/)).toHaveLength(200);
    fireEvent.click(screen.getByRole('button', { name: 'عرض المزيد (50)' }));
    expect(screen.getAllByTestId(/^row-/)).toHaveLength(250);
  });
});

describe('SasImport on a re-import (specs/015 US5, T048)', () => {
  it('shows the update and missing counts, and a mapping from a previous import', async () => {
    await openPreview(
      preview({
        counts: { ...COUNTS, new: 2, update: 2, unchanged: 14, missing_from_file: 1 },
        prefixes: [{ prefix: 'ZZQ07', rows: 2, tower_id: 1, from_previous: true, chosen: true }],
        waiting_prefixes: 0,
      }),
    );
    expect(screen.getByText('سيُحدَّث: 2')).toBeTruthy();
    expect(screen.getByText('بلا تغيير: 14')).toBeTruthy();
    expect(screen.getByText('غير موجود في آخر ملف: 1')).toBeTruthy();
    const table = screen.getByTestId('prefix-ZZQ07');
    expect(within(table).getByText('من استيراد سابق')).toBeTruthy();
    const select = within(table).getByLabelText('برج ZZQ07') as HTMLSelectElement;
    expect(select.value).toBe('1');
    setSasChoices.mockResolvedValue(preview());
    fireEvent.change(select, { target: { value: '2' } });
    await waitFor(() =>
      expect(setSasChoices).toHaveBeenCalledWith('p-1', [], [{ prefix: 'ZZQ07', tower_id: 2 }]),
    );
  });

  it('shows the missing counts in the summary', async () => {
    await openPreview(decided());
    confirmSasImport.mockResolvedValue({ ...SUMMARY, missing_marked: 1, missing_cleared: 2 });
    fireEvent.click(confirmButton());
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'استيراد' }),
    );
    expect(await screen.findByText('وُسم «غير موجود في آخر ملف»: 1')).toBeTruthy();
    expect(screen.getByText('عاد في هذا الملف: 2')).toBeTruthy();
  });
});
