import { devices, expect, test } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  changeForcedPassword,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

// Quickstart D, E, F. Self-contained: it seeds its own synthetic admin and marketer through
// the API, so it does not depend on the US1 screens. Desktop project only (state-changing).
const ADMIN = { name: 'أدمن إيقاف', phone: '07700000111', permissions: ['marketers'] };
const MARKETER = { name: 'مسوّق إيقاف', phone: '07700000211' };
const RESET_PASSWORD = 'Reset-Passw0rd-3';

test('deactivate signs the marketer out; reactivate restores; reset forces a change', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');

  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await apiCreateReadyAccount(request, main, 'admins', ADMIN);
  await apiCreateReadyAccount(request, main, 'marketers', MARKETER);

  // The marketer is signed in on a phone.
  const phone = await browser.newContext({ ...devices['Pixel 7'], ignoreHTTPSErrors: true });
  const mPage = await phone.newPage();
  await signIn(mPage, MARKETER.phone, NEW_PASSWORD);
  await expect(mPage.getByTestId('linked-counter')).toBeVisible();

  // D: the marketers admin deactivates them from the desktop.
  await signIn(page, ADMIN.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByTestId('sidebar').getByRole('link', { name: 'المسوّقون' }).click();
  const row = page.getByTestId('account-row').filter({ hasText: MARKETER.name });
  await row.getByRole('button', { name: 'إيقاف' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'إيقاف' }).click();
  await expect(row).toContainText('موقوف');

  await mPage.getByRole('link', { name: 'الطلبات' }).click();
  await expect(mPage).toHaveURL(/\/login$/);
  await expect(mPage.getByText('الحساب موقوف، راجع الإدارة')).toBeVisible();
  await signIn(mPage, MARKETER.phone, NEW_PASSWORD);
  await expect(mPage.getByText('الحساب موقوف، راجع الإدارة')).toBeVisible();

  // E: reactivate → the same password works again.
  await row.getByRole('button', { name: 'إعادة تفعيل' }).click();
  await expect(row).toContainText('فعّال');
  await signIn(mPage, MARKETER.phone, NEW_PASSWORD);
  await expect(mPage.getByTestId('linked-counter')).toBeVisible();

  // F: reset → the open session ends; the temporary password forces a change.
  await row.getByRole('button', { name: 'تصفير كلمة السر' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('كلمة السر المؤقتة الجديدة').fill(RESET_PASSWORD);
  await dialog.getByRole('button', { name: 'تصفير كلمة السر' }).click();
  await expect(dialog).toBeHidden();

  await mPage.getByRole('link', { name: 'الطلبات' }).click();
  await expect(mPage).toHaveURL(/\/login$/);
  await signIn(mPage, MARKETER.phone, RESET_PASSWORD);
  await changeForcedPassword(mPage, RESET_PASSWORD, 'After-Reset-44');
  await expect(mPage.getByTestId('linked-counter')).toBeVisible();
  await phone.close();
});
