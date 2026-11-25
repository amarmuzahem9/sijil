/**
 * «النسخ الاحتياطي» (docs/system.md §10 item 10, specs/016 US3: FR-016, FR-017). Main admin only;
 * ids, times, sizes and counts, never subscriber data.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/api';
import type { BackupPage } from '../lib/backup';
import { formatBaghdad } from '../lib/time';

const getBackupPage = vi.fn();
const requestBackup = vi.fn();
vi.mock('../lib/backup', async (original) => ({
  ...(await original<typeof import('../lib/backup')>()),
  getBackupPage: (...args: unknown[]) => getBackupPage(...args),
  requestBackup: (...args: unknown[]) => requestBackup(...args),
}));

import Backup from '../pages/admin/Backup';

const GB = 1024 ** 3;
const LAST = '2026-11-27T00:02:00+00:00';

function page(over: Partial<BackupPage> = {}): BackupPage {
  return {
    status: {
      service_ok: true,
      heartbeat_at: '2026-11-27T09:00:00+00:00',
      nightly_at: '03:00',
      free_bytes: 40 * GB,
      total_bytes: 100 * GB,
      min_free_bytes: 2 * GB,
      backup_dir_bytes: 3 * GB,
      external_dir: '/media/sijil-external',
      key_configured: true,
    },
    running: null,
    runs: [
      {
        id: '20261127-000000-nightly',
        snapshot_id: '20261127-000000-nightly',
        kind: 'nightly',
        status: 'succeeded',
        error_code: null,
        started_at: '2026-11-27T00:00:00+00:00',
        finished_at: LAST,
        total_size: 250 * 1024 ** 2,
        image_count: 830,
        counts: { requests: 412, legacy_subscribers: 109, sas_subscribers: 20000, users: 15 },
      },
      {
        id: 'run-2',
        snapshot_id: null,
        kind: 'manual',
        status: 'failed',
        error_code: 'disk_low',
        started_at: '2026-11-26T10:00:00+00:00',
        finished_at: '2026-11-26T10:00:05+00:00',
        total_size: null,
        image_count: null,
        counts: null,
      },
    ],
    last_external: { at: '2026-11-22T08:00:00+00:00', result: 'succeeded', snapshot_id: 's' },
    last_drill: {
      at: '2026-11-22T08:10:00+00:00',
      result: 'passed',
      snapshot_id: 's',
      source: 'external',
      reason: null,
    },
    deploys: [
      { at: '2026-11-20T12:00:00+00:00', result: 'succeeded', mode: 'staging', commit: 'abc1234' },
    ],
    warnings: [],
    ...over,
  };
}

beforeEach(() => {
  getBackupPage.mockReset();
  requestBackup.mockReset();
  getBackupPage.mockResolvedValue(page());
});
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Backup />
    </QueryClientProvider>,
  );
}

describe('Backup page', () => {
  it('shows the last backup with its time, size and counts', async () => {
    show();
    const last = await screen.findByRole('region', { name: 'آخر نسخة' });
    expect(last.textContent).toContain(formatBaghdad(LAST));
    expect(last.textContent).toContain('ناجحة');
    expect(last.textContent).toContain('250');
    expect(last.textContent).toContain('ليلية');
    expect(last.textContent).toMatch(/طلبات/);
  });

  it('lists the kept backups, a failure with its reason', async () => {
    show();
    const list = await screen.findByRole('region', { name: 'النسخ المحفوظة' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(rows[1].textContent).toContain('فشلت');
    expect(rows[1].textContent).toContain('المساحة غير كافية');
    expect(rows[1].textContent).toContain('يدوية');
  });

  it('shows the external copy, the drill, deploys, free space and the drive path', async () => {
    show();
    const ext = await screen.findByRole('region', { name: 'الهارد الخارجي' });
    expect(ext.textContent).toContain(formatBaghdad('2026-11-22T08:00:00+00:00'));
    expect(ext.textContent).toContain('/media/sijil-external');
    const drill = screen.getByRole('region', { name: 'تجربة الاسترجاع' });
    expect(drill.textContent).toContain('نجحت');
    const server = screen.getByRole('region', { name: 'السيرفر' });
    expect(server.textContent).toContain('03:00');
    expect(server.textContent).toMatch(/40/);
    const deploys = screen.getByRole('region', { name: 'آخر عمليات النشر' });
    expect(deploys.textContent).toContain('abc1234');
  });

  it('starts a manual backup and shows it in progress', async () => {
    requestBackup.mockResolvedValue({ id: 'req-1' });
    show();
    await screen.findByRole('region', { name: 'آخر نسخة' });
    const button = screen.getByRole('button', { name: 'نسخة يدوية الآن' });
    getBackupPage.mockResolvedValue(
      page({ running: { id: 'req-1', kind: 'manual', status: 'requested', started_at: null } }),
    );
    fireEvent.click(button);
    await waitFor(() => expect(requestBackup).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('جارٍ النسخ…')).toBeTruthy();
    expect(
      (screen.getByRole('button', { name: 'نسخة يدوية الآن' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it('says a backup is already running on 409', async () => {
    requestBackup.mockRejectedValue(new ApiError('backup_busy', 'يوجد نسخ جارٍ الآن', 409));
    show();
    await screen.findByRole('region', { name: 'آخر نسخة' });
    fireEvent.click(screen.getByRole('button', { name: 'نسخة يدوية الآن' }));
    expect(await screen.findByText('يوجد نسخ جارٍ الآن')).toBeTruthy();
  });

  it('lists the warnings with their Arabic texts', async () => {
    getBackupPage.mockResolvedValue(page({ warnings: ['last_failed', 'external_overdue'] }));
    show();
    expect(await screen.findByText('فشل آخر نسخ احتياطي')).toBeTruthy();
    expect(screen.getByText('النسخة الأسبوعية على الهارد الخارجي متأخرة')).toBeTruthy();
  });

  it('says when no backup exists yet', async () => {
    getBackupPage.mockResolvedValue(page({ runs: [], last_external: null, last_drill: null }));
    show();
    expect(await screen.findByText('لا توجد نسخة بعد')).toBeTruthy();
    expect(screen.getByText('لا توجد نسخ محفوظة')).toBeTruthy();
  });
});
