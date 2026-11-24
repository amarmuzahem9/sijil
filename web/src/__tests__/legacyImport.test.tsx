/**
 * «المشتركون القدامى» import page (specs/014 US1: FR-003–FR-005a, FR-010; contracts/api.md):
 * upload, progress, grouped flagged rows with their allowed choices, «تخطي للكل», the correction
 * field, confirmation and the summary. Synthetic values only.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { FlaggedRow, ImportSummary, LegacyPreview } from '../lib/legacyImport';

const uploadLegacyFile = vi.fn();
const getPreview = vi.fn();
const setChoices = vi.fn();
const confirmImport = vi.fn();
const cancelPreview = vi.fn();
vi.mock('../lib/legacyImport', async (original) => ({
  ...(await original<typeof import('../lib/legacyImport')>()),
  uploadLegacyFile: (...args: unknown[]) => uploadLegacyFile(...args),
  getPreview: (...args: unknown[]) => getPreview(...args),
  setChoices: (...args: unknown[]) => setChoices(...args),
  confirmImport: (...args: unknown[]) => confirmImport(...args),
  cancelPreview: (...args: unknown[]) => cancelPreview(...args),
}));

import { flagText, groupFlagged } from '../lib/legacyImport';
import LegacyImport from '../pages/admin/import/LegacyImport';

function row(partial: Partial<FlaggedRow> & { index: number }): FlaggedRow {
  return {
    legacy_number: `T3C-${String(partial.index).padStart(3, '0')}`,
    full_name: 'اسم تجريبي',
    phone_file: '07811110000',
    phone: '07811110000',
    family_number_file: '1111A0000000000000',
    status_text: 'تم',
    counts_in_check: true,
    flags: [],
    allowed: ['import', 'skip'],
    choice: null,
    corrected_family_number: null,
    ...partial,
  };
}

const FLAGGED: FlaggedRow[] = [
  row({ index: 4, flags: [{ code: 'family_dup_file', rows: [5] }] }),
  row({ index: 5, flags: [{ code: 'family_dup_file', rows: [4] }] }),
  row({
    index: 6,
    family_number_file: '1111A000000006',
    flags: [{ code: 'family_length' }],
    allowed: ['import', 'skip', 'correct'],
  }),
  row({
    index: 11,
    counts_in_check: false,
    status_text: 'مرفوض',
    flags: [{ code: 'image_failed', side: 'back', outcome: 'not_shared' }],
  }),
  row({
    index: 12,
    legacy_number: 'xyz',
    flags: [{ code: 'legacy_number_missing' }],
    allowed: ['skip'],
  }),
  row({ index: 15, flags: [{ code: 'already_imported' }], allowed: [] }),
];

function preview(partial: Partial<LegacyPreview> = {}): LegacyPreview {
  return {
    id: 'p-1',
    status: 'ready',
    file_name: 'legacy.csv',
    expires_at: '2026-11-25T10:00:00Z',
    images_total: 25,
    images_done: 25,
    counts: {
      rows: 9,
      ready: 3,
      flagged: 5,
      already_imported: 1,
      not_counted: 1,
      waiting_choice: 5,
    },
    status_values: [
      { value: 'تم', rows: 7, counts_in_check: true },
      { value: null, rows: 1, counts_in_check: true },
      { value: 'مرفوض', rows: 1, counts_in_check: false },
    ],
    flagged: FLAGGED,
    ...partial,
  };
}

function withChoices(choices: Record<number, FlaggedRow['choice']>): LegacyPreview {
  const flagged = FLAGGED.map((r) => (r.index in choices ? { ...r, choice: choices[r.index] } : r));
  const waiting = flagged.filter((r) => r.allowed.length > 0 && r.choice === null).length;
  return preview({ flagged, counts: { ...preview().counts, waiting_choice: waiting } });
}

const SUMMARY: ImportSummary = {
  import_id: 1,
  rows: 9,
  imported: 6,
  skipped: 2,
  already_imported: 1,
  not_counted: 1,
  incomplete: 1,
  corrected: 1,
  skipped_numbers: ['xyz', 'T3C-005'],
  incomplete_numbers: ['T3C-011'],
};

beforeEach(() => {
  for (const fn of [uploadLegacyFile, getPreview, setChoices, confirmImport, cancelPreview])
    fn.mockReset();
});
afterEach(cleanup);

async function openReadyPreview(initial: LegacyPreview = preview()) {
  uploadLegacyFile.mockResolvedValue(initial);
  render(<LegacyImport pollMs={5} />);
  const input = screen.getByLabelText('ملف المشتركين القدامى (xlsx أو csv)');
  fireEvent.change(input, { target: { files: [new File(['x'], 'legacy.csv')] } });
  fireEvent.click(screen.getByRole('button', { name: 'رفع ومعاينة' }));
  await screen.findByText('عدد الصفوف: 9');
}

describe('flag texts and groups', () => {
  it('reads every flag in Arabic with its detail', () => {
    expect(flagText({ code: 'family_dup_file', rows: [5, 9] })).toBe(
      'رقم عائلي مكرر في الملف (مع الصف 5، 9)',
    );
    expect(flagText({ code: 'in_sijil', requests: ['T3C-1004'] })).toBe(
      'موجود في طلبات سِجلّ (T3C-1004)',
    );
    expect(flagText({ code: 'image_failed', side: 'back', outcome: 'not_shared' })).toBe(
      'تعذّر سحب الصورة (الظهر: الملف غير مشترك)',
    );
    expect(flagText({ code: 'image_missing', side: 'front' })).toBe('صورة ناقصة (الوجه)');
    expect(flagText({ code: 'family_length' })).toBe('طول غير معتاد للرقم العائلي');
  });

  it('puts each row once, under its first flag, with already imported rows last', () => {
    const groups = groupFlagged(FLAGGED);
    expect(groups.map((g) => g.code)).toEqual([
      'legacy_number_missing',
      'family_dup_file',
      'family_length',
      'image_failed',
      'already_imported',
    ]);
    expect(groups[1].rows.map((r) => r.index)).toEqual([4, 5]);
  });
});

describe('LegacyImport', () => {
  it('needs a file before uploading', () => {
    render(<LegacyImport pollMs={5} />);
    expect(
      (screen.getByRole('button', { name: 'رفع ومعاينة' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it('shows the fetching progress, then the preview', async () => {
    uploadLegacyFile.mockResolvedValue(
      preview({ status: 'fetching', images_done: 0, flagged: [] }),
    );
    getPreview
      .mockResolvedValueOnce(preview({ status: 'fetching', images_done: 12, flagged: [] }))
      .mockResolvedValue(preview());
    render(<LegacyImport pollMs={5} />);
    fireEvent.change(screen.getByLabelText('ملف المشتركين القدامى (xlsx أو csv)'), {
      target: { files: [new File(['x'], 'legacy.csv')] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'رفع ومعاينة' }));
    expect(await screen.findByText('جارٍ سحب الصور 0 من 25')).toBeTruthy();
    expect(await screen.findByText('عدد الصفوف: 9')).toBeTruthy();
    expect(getPreview).toHaveBeenCalledWith('p-1');
  });

  it('shows an upload error in Arabic, with the missing columns', async () => {
    uploadLegacyFile.mockRejectedValue(
      new ApiError('import_columns_missing', 'الملف ينقصه عمود: الرقم العائلي، ID', 422, {
        columns: ['الرقم العائلي', 'ID'],
      }),
    );
    render(<LegacyImport pollMs={5} />);
    fireEvent.change(screen.getByLabelText('ملف المشتركين القدامى (xlsx أو csv)'), {
      target: { files: [new File(['x'], 'legacy.csv')] },
    });
    fireEvent.click(screen.getByRole('button', { name: 'رفع ومعاينة' }));
    expect(await screen.findByText('الملف ينقصه عمود: الرقم العائلي، ID')).toBeTruthy();
  });

  it('shows counts, status values and the groups with their allowed choices', async () => {
    await openReadyPreview();
    expect(screen.getByText('جاهزة: 3')).toBeTruthy();
    expect(screen.getByText('تحتاج قراراً: 5')).toBeTruthy();
    expect(screen.getByText('مستورد سابقاً: 1')).toBeTruthy();
    expect(screen.getByText('لا تُحسب في الفحص: 1')).toBeTruthy();
    expect(screen.getByText('مرفوض: 1 (لا تُحسب في الفحص)')).toBeTruthy();
    expect(screen.getByText('(فارغة): 1')).toBeTruthy();

    const dup = screen.getByTestId('group-family_dup_file');
    expect(within(dup).getByText('رقم عائلي مكرر في الملف (مع الصف 5)')).toBeTruthy();
    expect(within(dup).getAllByRole('button', { name: 'استيراد' })).toHaveLength(2);
    expect(within(dup).queryByRole('button', { name: 'تصحيح' })).toBeNull();

    const missing = screen.getByTestId('group-legacy_number_missing');
    expect(within(missing).queryByRole('button', { name: 'استيراد' })).toBeNull();
    expect(within(missing).getByRole('button', { name: 'تخطي' })).toBeTruthy();

    const length = screen.getByTestId('group-family_length');
    expect(within(length).getByRole('button', { name: 'تصحيح' })).toBeTruthy();

    const imported = screen.getByTestId('group-already_imported');
    expect(within(imported).queryByRole('button', { name: 'تخطي' })).toBeNull();
    expect(within(imported).queryByRole('button', { name: 'تخطي للكل' })).toBeNull();

    expect(screen.getByText('لا يُحسب في الفحص')).toBeTruthy();
  });

  it('sends one choice and shows the server answer', async () => {
    await openReadyPreview();
    setChoices.mockResolvedValue(withChoices({ 4: 'import' }));
    const card = screen.getByTestId('row-4');
    fireEvent.click(within(card).getByRole('button', { name: 'استيراد' }));
    await waitFor(() =>
      expect(setChoices).toHaveBeenCalledWith('p-1', [{ index: 4, choice: 'import' }]),
    );
    await waitFor(() =>
      expect(
        within(screen.getByTestId('row-4'))
          .getByRole('button', { name: 'استيراد' })
          .getAttribute('aria-pressed'),
      ).toBe('true'),
    );
  });

  it('«تخطي للكل» skips the group, and a row can then be switched back', async () => {
    await openReadyPreview();
    setChoices.mockResolvedValueOnce(withChoices({ 4: 'skip', 5: 'skip' }));
    fireEvent.click(
      within(screen.getByTestId('group-family_dup_file')).getByRole('button', {
        name: 'تخطي للكل',
      }),
    );
    await waitFor(() =>
      expect(setChoices).toHaveBeenCalledWith('p-1', [
        { index: 4, choice: 'skip' },
        { index: 5, choice: 'skip' },
      ]),
    );
    setChoices.mockResolvedValueOnce(withChoices({ 4: 'skip', 5: 'import' }));
    fireEvent.click(
      within(await screen.findByTestId('row-5')).getByRole('button', { name: 'استيراد' }),
    );
    await waitFor(() =>
      expect(setChoices).toHaveBeenLastCalledWith('p-1', [{ index: 5, choice: 'import' }]),
    );
  });

  it('sends a corrected family number', async () => {
    await openReadyPreview();
    const card = screen.getByTestId('row-6');
    fireEvent.click(within(card).getByRole('button', { name: 'تصحيح' }));
    fireEvent.change(within(card).getByLabelText('الرقم العائلي الصحيح'), {
      target: { value: '1111A0000000000006' },
    });
    setChoices.mockResolvedValue(withChoices({ 6: 'correct' }));
    fireEvent.click(within(card).getByRole('button', { name: 'حفظ التصحيح' }));
    await waitFor(() =>
      expect(setChoices).toHaveBeenCalledWith('p-1', [
        { index: 6, choice: 'correct', family_number: '1111A0000000000006' },
      ]),
    );
  });

  it('keeps «تأكيد الاستيراد» disabled while rows wait', async () => {
    await openReadyPreview();
    expect(
      (screen.getByRole('button', { name: 'تأكيد الاستيراد' }) as HTMLButtonElement).disabled,
    ).toBe(true);
    expect(screen.getByText('بقيت 5 صفوف بلا اختيار')).toBeTruthy();
  });

  it('confirms through a dialog and shows the summary without family numbers', async () => {
    await openReadyPreview(
      withChoices({ 4: 'import', 5: 'import', 6: 'correct', 11: 'import', 12: 'skip' }),
    );
    confirmImport.mockResolvedValue(SUMMARY);
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد الاستيراد' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/لا يمكن التراجع بعد التأكيد/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'استيراد' }));
    expect(await screen.findByText('تم الاستيراد')).toBeTruthy();
    expect(confirmImport).toHaveBeenCalledWith('p-1');
    expect(screen.getByText('المستورد: 6')).toBeTruthy();
    expect(screen.getByText('المتخطّى: 2')).toBeTruthy();
    expect(screen.getByText('غير مكتمل: 1')).toBeTruthy();
    expect(screen.getByText('الصفوف المتخطّاة: xyz، T3C-005')).toBeTruthy();
    expect(screen.getByText('الصفوف غير المكتملة: T3C-011')).toBeTruthy();
    expect(document.body.textContent).not.toContain('1111A');
  });

  it('reloads the preview when the data changed since the preview', async () => {
    await openReadyPreview(
      withChoices({ 4: 'import', 5: 'import', 6: 'correct', 11: 'import', 12: 'skip' }),
    );
    const changed = preview({
      flagged: [
        ...FLAGGED,
        row({ index: 3, flags: [{ code: 'in_sijil', requests: ['T3C-1009'] }] }),
      ],
    });
    confirmImport.mockRejectedValue(
      new ApiError('preview_changed', 'تغيّرت البيانات منذ المعاينة، راجع الصفوف المعلّمة', 409, {
        preview: changed,
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد الاستيراد' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'استيراد' }),
    );
    expect(
      await screen.findByText('تغيّرت البيانات منذ المعاينة، راجع الصفوف المعلّمة'),
    ).toBeTruthy();
    expect(screen.getByText('موجود في طلبات سِجلّ (T3C-1009)')).toBeTruthy();
  });

  it('cancels a preview', async () => {
    await openReadyPreview();
    cancelPreview.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء المعاينة' }));
    await waitFor(() => expect(cancelPreview).toHaveBeenCalledWith('p-1'));
    expect(await screen.findByRole('button', { name: 'رفع ومعاينة' })).toBeTruthy();
  });
});
