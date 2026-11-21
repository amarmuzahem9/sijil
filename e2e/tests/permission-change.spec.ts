import { expect, test, type Page } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

// Quickstart B and G. Sorts after admin-first-login.spec.ts (main admin password already set).
// Seeds its own synthetic admin through the API. Desktop project only (state-changing).
const ADMIN = { name: 'أدمن الصلاحيات', phone: '07700000121', permissions: ['marketers'] };
const SETTINGS_LABEL = 'الإعدادات والأسعار والشرائح';

async function menu(page: Page): Promise<string[]> {
  const list = page.getByTestId('sidebar').getByRole('list', { name: 'صفحات التطبيق' });
  return (await list.getByRole('link').allInnerTexts()).map((l) => l.trim());
}

async function toggleSettings(page: Page) {
  const row = page.getByTestId('account-row').filter({ hasText: ADMIN.name });
  await row.getByRole('button', { name: 'تعديل' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel(SETTINGS_LABEL).click();
  await dialog.getByRole('button', { name: 'حفظ' }).click();
  await expect(dialog).toBeHidden();
}

test('permission changes reach a signed-in admin without signing out', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');

  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await apiCreateReadyAccount(request, main, 'admins', ADMIN);

  // The admin is signed in in a separate browser context.
  const other = await browser.newContext({ ignoreHTTPSErrors: true });
  const adminPage = await other.newPage();
  await signIn(adminPage, ADMIN.phone, NEW_PASSWORD);
  await expect(adminPage).toHaveURL(/\/admin$/);
  expect(await menu(adminPage)).toEqual(['الرئيسية', 'المسوّقون']);

  // G: the main admin's own row has no actions.
  await signIn(page, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByTestId('sidebar').getByRole('link', { name: 'الأدمنية والصلاحيات' }).click();
  const mainRow = page.getByTestId('account-row').filter({ hasText: 'كل الصلاحيات' });
  await expect(mainRow).toHaveCount(1);
  await expect(mainRow.getByRole('button')).toHaveCount(0);

  // B: turn الإعدادات on → shows on the admin's next navigation.
  await toggleSettings(page);
  await adminPage.getByTestId('sidebar').getByRole('link', { name: 'المسوّقون' }).click();
  await expect.poll(() => menu(adminPage)).toEqual(['الرئيسية', 'المسوّقون', 'الإعدادات']);

  // …and off again → gone, and the page is refused.
  await toggleSettings(page);
  await adminPage.getByTestId('sidebar').getByRole('link', { name: 'الرئيسية' }).click();
  await expect.poll(() => menu(adminPage)).toEqual(['الرئيسية', 'المسوّقون']);
  await adminPage.goto('/admin/settings');
  await expect(adminPage).toHaveURL(/\/admin$/);
  await other.close();
});
