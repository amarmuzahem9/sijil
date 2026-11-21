import { devices, expect, test } from '@playwright/test';

import {
  changeForcedPassword,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
  TEMP_PASSWORD,
} from './helpers';

// Feature 002 acceptance (quickstart A, A2, A3). Named to sort after admin-first-login.spec.ts,
// which sets MAIN_ADMIN_PASSWORD. State-changing: desktop project only, on a fresh stack.
const ADMIN = { name: 'أدمن تجريبي', phone: '07700000101' };
const MARKETER = { name: 'مسوّق القبول', phone: '07700000201' };

test.describe.configure({ mode: 'serial' });

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');
});

test('main admin adds an admin with only «إدارة المسوّقين»', async ({ page }) => {
  await signIn(page, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByTestId('sidebar').getByRole('link', { name: 'الأدمنية والصلاحيات' }).click();

  await page.getByRole('button', { name: 'إضافة أدمن' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('الاسم').fill(ADMIN.name);
  await dialog.getByLabel('رقم الهاتف').fill(ADMIN.phone);
  await dialog.getByLabel('كلمة السر المؤقتة').fill(TEMP_PASSWORD);
  await dialog.getByLabel('إدارة المسوّقين وتصفير كلمات السر').check();
  await dialog.getByRole('button', { name: 'حفظ' }).click();

  await expect(dialog).toBeHidden();
  const row = page.getByTestId('account-row').filter({ hasText: ADMIN.name });
  await expect(row).toContainText('إدارة المسوّقين وتصفير كلمات السر');
  await expect(row).toContainText('فعّال');
});

test('that admin sees المسوّقون but not الإعدادات, and is refused by address', async ({
  page,
}) => {
  await signIn(page, ADMIN.phone, TEMP_PASSWORD);
  await changeForcedPassword(page, TEMP_PASSWORD, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/admin$/);

  const menu = page.getByTestId('sidebar').getByRole('list', { name: 'صفحات التطبيق' });
  const labels = (await menu.getByRole('link').allInnerTexts()).map((l) => l.trim());
  expect(labels).toEqual(['الرئيسية', 'المسوّقون']);

  await page.goto('/admin/settings');
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByText('ليست لديك صلاحية')).toBeVisible();

  const api = await page.request.get('/api/admin/admins', {
    headers: await bearer(page),
  });
  expect(api.status()).toBe(403);
});

test('that admin adds a marketer, who must change the password on a phone', async ({
  page,
  browser,
}) => {
  await signIn(page, ADMIN.phone, NEW_PASSWORD);
  await page.getByTestId('sidebar').getByRole('link', { name: 'المسوّقون' }).click();
  await page.getByRole('button', { name: 'إضافة مسوّق' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('الاسم').fill(MARKETER.name);
  await dialog.getByLabel('رقم الهاتف').fill('+964 770 000 0201');
  await dialog.getByLabel('كلمة السر المؤقتة').fill(TEMP_PASSWORD);
  await dialog.getByRole('button', { name: 'حفظ' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId('account-row').filter({ hasText: MARKETER.name })).toContainText(
    MARKETER.phone,
  );

  const phone = await browser.newContext({ ...devices['Pixel 7'], ignoreHTTPSErrors: true });
  const mPage = await phone.newPage();
  await signIn(mPage, MARKETER.phone, TEMP_PASSWORD);
  await changeForcedPassword(mPage, TEMP_PASSWORD, NEW_PASSWORD);
  await expect(mPage.getByTestId('linked-counter')).toBeVisible();
  await phone.close();
});

/** Access token of the page's session, via the refresh cookie. */
async function bearer(page: import('@playwright/test').Page) {
  const r = await page.request.post('/api/auth/refresh');
  return { Authorization: `Bearer ${(await r.json()).access_token}` };
}
