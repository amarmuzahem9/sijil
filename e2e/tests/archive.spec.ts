import { devices, expect, test } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

// Feature 003 (quickstart A–E). Sorts after admin-first-login.spec.ts; seeds its own synthetic
// accounts through the API. Desktop project only (state-changing).
const MARKETER = { name: 'مسوّق الأرشيف', phone: '07700000311' };
const MANAGER = { name: 'أدمن بلا حذف', phone: '07700000131', permissions: ['marketers'] };

test('archive, restore as deactivated, reactivate; only the main admin sees «حذف»', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');

  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await apiCreateReadyAccount(request, main, 'marketers', MARKETER);
  await apiCreateReadyAccount(request, main, 'admins', MANAGER);

  // E: an admin holding `marketers` has no «حذف» and no archive page.
  const other = await browser.newContext({ ignoreHTTPSErrors: true });
  const managerPage = await other.newPage();
  await signIn(managerPage, MANAGER.phone, NEW_PASSWORD);
  await expect(managerPage).toHaveURL(/\/admin$/);
  await expect(
    managerPage.getByTestId('sidebar').getByRole('link', { name: 'أرشيف الحسابات' }),
  ).toHaveCount(0);
  await managerPage.getByTestId('sidebar').getByRole('link', { name: 'المسوّقون' }).click();
  const managerRow = managerPage.getByTestId('account-row').filter({ hasText: MARKETER.name });
  await expect(managerRow.getByRole('button', { name: 'تعديل' })).toBeVisible();
  await expect(managerRow.getByRole('button', { name: 'حذف' })).toHaveCount(0);
  await managerPage.goto('/admin/archive');
  await expect(managerPage).toHaveURL(/\/admin$/);
  await other.close();

  // The marketer is signed in on a phone.
  const phone = await browser.newContext({ ...devices['Pixel 7'], ignoreHTTPSErrors: true });
  const mPage = await phone.newPage();
  await signIn(mPage, MARKETER.phone, NEW_PASSWORD);
  await expect(mPage.getByTestId('linked-counter')).toBeVisible();

  // A: the main admin archives them.
  await signIn(page, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByTestId('sidebar').getByRole('link', { name: 'المسوّقون' }).click();
  const row = page.getByTestId('account-row').filter({ hasText: MARKETER.name });
  await row.getByRole('button', { name: 'حذف' }).click();
  const confirm = page.getByRole('dialog');
  await expect(confirm).toContainText('أرشيف الحسابات');
  await confirm.getByRole('button', { name: 'حذف' }).click();
  await expect(row).toHaveCount(0);

  await mPage.getByRole('link', { name: 'الطلبات' }).click();
  await expect(mPage).toHaveURL(/\/login$/);
  await expect(mPage.getByText('الحساب موقوف، راجع الإدارة')).toBeVisible();

  // B: listed in the archive with who archived it.
  await page.getByTestId('sidebar').getByRole('link', { name: 'أرشيف الحسابات' }).click();
  const archived = page.getByTestId('account-row').filter({ hasText: MARKETER.name });
  await expect(archived).toContainText('مسوّق');
  await expect(archived).toContainText('بواسطة');

  // C: restore → back in the list as «موقوف»; sign-in still refused.
  await archived.getByRole('button', { name: 'استرجاع' }).click();
  await expect(page.getByText('لا توجد حسابات مؤرشفة')).toBeVisible();
  await signIn(mPage, MARKETER.phone, NEW_PASSWORD);
  await expect(mPage.getByText('الحساب موقوف، راجع الإدارة')).toBeVisible();

  // D: reactivate → signs in with the old password.
  await page.getByTestId('sidebar').getByRole('link', { name: 'المسوّقون' }).click();
  const back = page.getByTestId('account-row').filter({ hasText: MARKETER.name });
  await expect(back).toContainText('موقوف');
  await back.getByRole('button', { name: 'إعادة تفعيل' }).click();
  await expect(back).toContainText('فعّال');
  await signIn(mPage, MARKETER.phone, NEW_PASSWORD);
  await expect(mPage.getByTestId('linked-counter')).toBeVisible();
  await phone.close();
});
