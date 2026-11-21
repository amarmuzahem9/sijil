import { expect, test } from '@playwright/test';

import { ADMIN_PAGES, env, expectOnRightSide, MAIN_ADMIN_PASSWORD, signIn } from './helpers';

// Changes state (the bootstrap admin's first password change): desktop project only, fresh stack.
test('main admin: first sign-in from desktop, forced password change, admin panel', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');

  const phone = env('SUPERADMIN_PHONE'); // e.g. 07700000000
  const plusFormat = `+964 ${phone.slice(1, 4)} ${phone.slice(4, 7)} ${phone.slice(7)}`;
  await signIn(page, plusFormat, env('SUPERADMIN_PASSWORD'));

  await expect(page).toHaveURL(/\/change-password$/);
  await page.locator('input[name=current_password]').fill(env('SUPERADMIN_PASSWORD'));
  await page.locator('input[name=new_password]').fill(MAIN_ADMIN_PASSWORD);
  await page.locator('input[name=confirm_password]').fill(MAIN_ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'حفظ' }).click();

  await expect(page).toHaveURL(/\/admin$/);
  const sidebar = page.getByTestId('sidebar');
  await expect(sidebar).toBeVisible();
  const labels = await sidebar
    .getByRole('list', { name: 'صفحات التطبيق' })
    .getByRole('link')
    .allInnerTexts();
  expect(labels.map((l) => l.trim())).toEqual(ADMIN_PAGES);
  await expectOnRightSide(page, 'sidebar');
  await expect(page.getByTestId('user-identity')).toContainText('أدمن رئيسي');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
});
