import { expect, test, type Browser, type Download, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

import { env, signIn } from './helpers';
import { readXlsx, readZip } from './helpers/zip';

/**
 * Feature 019: «التقارير والتصدير», end to end (specs/019 T045).
 *
 * The data comes from api/tests/e2e_reports_seed.py (run by scripts/e2e.sh): three requests with
 * their card images and one deleted request in tower RPT01, all submitted this month, and four
 * accounts. Synthetic values only; the downloaded files stay inside the e2e container.
 *
 * 1. A `reports` + `review` admin filters by the tower, ticks the identity box, exports and
 *    downloads: the ZIP holds the sheet with identity columns, `cards/` named by number, links
 *    from the sheet to the images, the «=» name as text and the deleted request without images.
 * 2. A `reports`-only admin has no box; the ZIP holds the sheet only, without identity columns.
 * 3. A `commissions` admin downloads «العمولات» as a sheet.
 * 4. A marketer reaches neither the page nor its API.
 */

const PASSWORD = () => env('DEMO_MARKETER_PASSWORD');
const REPORTS_ADMIN = '07710019001';
const REPORTS_REVIEW_ADMIN = '07710019002';
const COMMISSIONS_ADMIN = '07710019003';
const MARKETER = '07710019004';
const TOWER = 'برج التقارير التجريبي (RPT01)';
const LIVE = [990101, 990102, 990103];
const DELETED = 990104;
const NATIONAL_ID = '199019000001';
const FORMULA_NAME = '=تجربة تصدير';
const BOX = 'تضمين الرقم الوطني والعائلي والصور';

async function pageAs(browser: Browser, phone: string): Promise<Page> {
  const page = await (
    await browser.newContext({ ignoreHTTPSErrors: true, acceptDownloads: true })
  ).newPage();
  await signIn(page, phone, PASSWORD());
  // Signed in before any page is opened by address.
  await expect(page).not.toHaveURL(/\/login/);
  return page;
}

async function bearer(page: Page) {
  const r = await page.request.post('/api/auth/refresh');
  return { Authorization: `Bearer ${(await r.json()).access_token}` };
}

async function filterTower(page: Page) {
  await page.goto('/admin/reports');
  await expect(page.getByRole('heading', { name: 'التقارير والتصدير' })).toBeVisible();
  await page.getByLabel('البرج').selectOption({ label: TOWER });
  await expect(page.getByTestId('report-total')).toHaveText('العدد: 4');
  await expect(page.getByTestId('report-row')).toHaveCount(4);
}

/** «تصدير», wait for «جاهز», then «تنزيل»: the browser downloads through the one-use link. */
async function exportAndDownload(page: Page): Promise<Download> {
  await page.getByRole('button', { name: 'تصدير' }).click();
  const list = page.getByTestId('exports-list');
  const item = list.getByTestId('export-item').first();
  await expect(item.getByRole('button', { name: 'تنزيل' })).toBeVisible({
    timeout: 30_000,
  });
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    item.getByRole('button', { name: 'تنزيل' }).click(),
  ]);
  return download;
}

async function bytes(download: Download): Promise<Buffer> {
  const path = await download.path();
  expect(path, 'the download was saved').toBeTruthy();
  return readFile(path!);
}

test('«التقارير والتصدير»: the report, the guarded ZIP and who may export', async ({
  browser,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of seeded records');

  // 1. reports + review: the box, identity columns and the images.
  const reviewer = await pageAs(browser, REPORTS_REVIEW_ADMIN);
  await expect(reviewer).toHaveURL(/\/admin/);
  await filterTower(reviewer);
  const deletedRow = reviewer.getByTestId('report-row').filter({ hasText: `T3C-${DELETED}` });
  await expect(deletedRow).toContainText('محذوف');
  const box = reviewer.getByLabel(BOX);
  await expect(box).not.toBeChecked();
  await box.check();
  const full = await exportAndDownload(reviewer);
  expect(full.suggestedFilename()).toMatch(/^sijil-requests-\d{4}-\d{2}-\d{2}-\d{4}\.zip$/);
  const zip = readZip(await bytes(full));
  const cards = LIVE.flatMap((n) => [`cards/T3C-${n}-front.jpg`, `cards/T3C-${n}-back.jpg`]);
  expect([...zip.keys()].sort()).toEqual(['requests.xlsx', ...cards].sort());
  for (const card of cards) expect(zip.get(card)!.subarray(0, 2).toString('hex')).toBe('ffd8');
  const sheet = readXlsx(zip.get('requests.xlsx')!);
  expect(sheet.texts).toContain('الرقم الوطني');
  expect(sheet.texts).toContain(NATIONAL_ID);
  expect(sheet.texts).toContain(FORMULA_NAME); // text, not a formula
  expect(sheet.formulas).toBe(0);
  expect(sheet.texts).toContain('محذوف');
  expect(sheet.texts).not.toContain('محذوف تقرير تجريبي'); // the erased name never comes back
  expect(sheet.links.sort()).toEqual(cards.sort());
  // A second click asks for a new one-use link and downloads again.
  const [again] = await Promise.all([
    reviewer.waitForEvent('download'),
    reviewer
      .getByTestId('exports-list')
      .getByTestId('export-item')
      .first()
      .getByRole('button', { name: 'تنزيل' })
      .click(),
  ]);
  expect(readZip(await bytes(again)).size).toBe(1 + cards.length);

  // 2. reports only: no box, no identity column, no images.
  const reports = await pageAs(browser, REPORTS_ADMIN);
  await filterTower(reports);
  await expect(reports.getByLabel(BOX)).toHaveCount(0);
  await expect(reports.getByText('الملف بدون الرقم الوطني والعائلي والصور.')).toBeVisible();
  const plain = readZip(await bytes(await exportAndDownload(reports)));
  expect([...plain.keys()]).toEqual(['requests.xlsx']);
  const plainSheet = readXlsx(plain.get('requests.xlsx')!);
  expect(plainSheet.texts).toContain('رنا تقرير تجريبية');
  expect(plainSheet.texts).not.toContain('الرقم الوطني');
  expect(plainSheet.texts).not.toContain(NATIONAL_ID);
  expect(plainSheet.links).toEqual([]);
  // The server refuses identity data to this admin even when asked directly.
  const forced = await reports.request.post('/api/admin/exports', {
    headers: await bearer(reports),
    data: { period: 'month', include_identity: true },
  });
  expect(forced.status()).toBe(403);
  expect((await forced.json()).code).toBe('identity_export_forbidden');

  // 3. commissions: «العمولات» as a sheet.
  const commissions = await pageAs(browser, COMMISSIONS_ADMIN);
  await commissions.goto('/admin/commissions');
  const [sheetDownload] = await Promise.all([
    commissions.waitForEvent('download'),
    commissions.getByRole('button', { name: 'تصدير' }).click(),
  ]);
  expect(sheetDownload.suggestedFilename()).toMatch(/^sijil-commissions-\d{4}-\d{2}\.xlsx$/);
  const commissionSheet = readXlsx(await bytes(sheetDownload));
  expect(commissionSheet.texts).toContain('المجموع');

  // 4. A marketer: no page, no API.
  const marketer = await pageAs(browser, MARKETER);
  await expect(marketer).not.toHaveURL(/\/admin/);
  await marketer.goto('/admin/reports');
  await expect(marketer).not.toHaveURL(/\/admin\/reports/);
  await expect(marketer.getByRole('heading', { name: 'التقارير والتصدير' })).toHaveCount(0);
  const auth = await bearer(marketer);
  for (const [method, url] of [
    ['get', '/api/admin/reports/options'],
    ['get', '/api/admin/exports'],
    ['post', '/api/admin/exports'],
  ] as const) {
    const response =
      method === 'get'
        ? await marketer.request.get(url, { headers: auth })
        : await marketer.request.post(url, {
            headers: auth,
            data: { period: 'month' },
          });
    expect(response.status(), `${method} ${url}`).toBe(403);
  }
});
