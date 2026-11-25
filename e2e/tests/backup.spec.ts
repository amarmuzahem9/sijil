import { expect, test } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

// Feature 016 (T053): «النسخ الاحتياطي» for the main admin; the e2e stack runs the `backup`
// service with a throwaway key (scripts/e2e.sh), on synthetic data only. Desktop project only.
// 07700000161 belongs to subscriber-form-acceptance (its pixel-7 marketer): reusing it here made
// that spec sign in as this admin in a full run, and wait 3 min for «إضافة مشترك جديد».
// Keep e2e phones unique.
const MANAGER = {
  name: 'أدمن بلا نسخ',
  phone: '07700000981',
  permissions: ['settings', 'reports'],
};

test('the main admin takes a manual backup; another admin never sees the page', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');

  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await apiCreateReadyAccount(request, main, 'admins', MANAGER);

  // An added admin: no menu item, and the direct address goes back home.
  const other = await browser.newContext({ ignoreHTTPSErrors: true });
  const managerPage = await other.newPage();
  await signIn(managerPage, MANAGER.phone, NEW_PASSWORD);
  await expect(managerPage).toHaveURL(/\/admin$/);
  await expect(
    managerPage.getByTestId('sidebar').getByRole('link', { name: 'النسخ الاحتياطي' }),
  ).toHaveCount(0);
  await managerPage.goto('/admin/backup');
  await expect(managerPage).toHaveURL(/\/admin$/);
  await other.close();

  // The main admin.
  await signIn(page, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await page.getByTestId('sidebar').getByRole('link', { name: 'النسخ الاحتياطي' }).click();
  await expect(page.getByRole('heading', { name: 'النسخ الاحتياطي', level: 1 })).toBeVisible();
  const last = page.getByRole('region', { name: 'آخر نسخة' });
  await expect(last).toBeVisible();

  const button = page.getByRole('button', { name: 'نسخة يدوية الآن' });
  await expect(button).toBeEnabled({ timeout: 30_000 }); // the service's first heartbeat
  await button.click();
  // The service picks the request up within 15 s; the page follows it every 5 s. A nightly
  // backup may also run when the stack starts after 03:00 Baghdad (it catches up), so look
  // for the manual one.
  const manual = page
    .getByRole('region', { name: 'النسخ المحفوظة' })
    .getByRole('listitem')
    .filter({ hasText: 'يدوية' });
  await expect(manual).toContainText('ناجحة', { timeout: 90_000 });
  await expect(manual).toHaveCount(1);
  await expect(page.getByText('جارٍ النسخ…')).toHaveCount(0);
});
