import { expect, test, type Browser, type Page } from '@playwright/test';

import { env, signIn } from './helpers';

/**
 * Feature 018: «المشتركون» search and the subscriber's file, end to end (specs/018 T036).
 *
 * The data comes from api/tests/e2e_subscriber_seed.py (run by scripts/e2e.sh): a request with its
 * two card images, a rejected request of another person with the same phone, a legacy row with the
 * same family number, and a deleted request with a fixed number. No SAS row (it would change the
 * counts of sas-import.spec.ts; SAS is covered by the api tests). Synthetic values only.
 *
 * 1. A `review` admin searches by phone, opens the request: its identity block and images, the
 *    rejected request «نفس الهاتف» and the legacy row «نفس العائلة»; the legacy file opens.
 * 2. The deleted request is found by its number only, as «سجل محذوف».
 * 3. A `link` admin sees the same file without identity data and is refused a national-ID search.
 */

const PASSWORD = () => env('DEMO_MARKETER_PASSWORD');
const REVIEW_ADMIN = '07710018001';
const LINK_ADMIN = '07710018002';
const PHONE = '07818000001';
const NATIONAL_ID = '199018000001';
const REQUEST_NAME = 'سجى ملف تجريبية';
const DELETED = 'T3C-990018';

async function pageAs(browser: Browser, phone: string): Promise<Page> {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: true })).newPage();
  await signIn(page, phone, PASSWORD());
  await expect(page).toHaveURL(/\/admin/);
  return page;
}

async function search(page: Page, text: string) {
  await page.goto('/admin/subscribers');
  await page.getByLabel('بحث في المشتركين').fill(text);
  await page.getByRole('button', { name: 'بحث' }).click();
}

test('«المشتركون»: search, the file, linked records and permissions', async ({
  browser,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of seeded records');

  // 1. The review admin.
  const reviewer = await pageAs(browser, REVIEW_ADMIN);
  await expect(
    reviewer.getByRole('navigation', { name: 'القائمة الرئيسية' }).first(),
  ).toContainText('المشتركون');
  await search(reviewer, '0781 800 0001');
  const rows = reviewer.getByTestId('subscriber-row');
  await expect(rows).toHaveCount(2);
  await expect(reviewer.getByTestId('search-total')).toHaveText('النتائج: 2');
  await rows.filter({ hasText: REQUEST_NAME }).click();

  await expect(reviewer.getByRole('heading', { name: REQUEST_NAME })).toBeVisible();
  const identity = reviewer.getByTestId('identity-block');
  await expect(identity).toContainText(NATIONAL_ID);
  await expect(identity.getByRole('img')).toHaveCount(2);
  const linked = reviewer.getByTestId('linked-record');
  await expect(linked.filter({ hasText: 'نفس الهاتف' })).toContainText('سجى هاتف مرفوضة');
  await expect(linked.filter({ hasText: 'نفس العائلة' })).toContainText('مشترك قديم');
  await expect(reviewer.getByTestId('history-line').first()).toContainText('أُرسل');
  // Read-only: no input anywhere in the file.
  await expect(reviewer.getByRole('textbox')).toHaveCount(0);

  const fileUrl = reviewer.url();
  await linked.filter({ hasText: 'نفس العائلة' }).click();
  await expect(reviewer.getByRole('heading', { name: 'سجى ملف قديمة' })).toBeVisible();
  await expect(reviewer.getByText('مشترك قديم').first()).toBeVisible();
  // The way back: the request is linked to the legacy row by the same family number.
  await expect(
    reviewer.getByTestId('linked-record').filter({ hasText: REQUEST_NAME }),
  ).toContainText('نفس العائلة');

  // 2. The deleted request: not by phone, only by number.
  await search(reviewer, '07818000009');
  await expect(reviewer.getByText('لا توجد نتائج')).toBeVisible();
  await search(reviewer, DELETED);
  const deleted = reviewer.getByTestId('subscriber-row');
  await expect(deleted).toHaveCount(1);
  await expect(deleted).toContainText('سجل محذوف');

  // 3. The link admin: the same file without identity data; no national-ID search.
  const linker = await pageAs(browser, LINK_ADMIN);
  await linker.goto(new URL(fileUrl).pathname);
  await expect(linker.getByRole('heading', { name: REQUEST_NAME })).toBeVisible();
  await expect(linker.getByTestId('identity-block')).toHaveCount(0);
  await expect(linker.getByText(NATIONAL_ID)).toHaveCount(0);
  await expect(linker.getByRole('img')).toHaveCount(0);
  await search(linker, NATIONAL_ID);
  await expect(
    linker.getByText('البحث بالرقم الوطني أو العائلي يحتاج صلاحية المراجعة'),
  ).toBeVisible();
});
