import { expect, test } from '@playwright/test';

import { env, signIn } from './helpers';

const FLAGGED_ACCOUNT = '07700000003'; // `seed-demo --e2e`: must_change_password = true

test('a flagged account is confined to /change-password until it saves', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'pixel-7', 'state-changing test: one project only');

  await signIn(page, FLAGGED_ACCOUNT, env('DEMO_MARKETER_PASSWORD'));
  await expect(page).toHaveURL(/\/change-password$/);

  for (const path of ['/', '/requests', '/account', '/admin']) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/change-password$/);
  }

  await page.locator('input[name=current_password]').fill(env('DEMO_MARKETER_PASSWORD'));
  await page.locator('input[name=new_password]').fill('Flagged-New-Passw0rd');
  await page.locator('input[name=confirm_password]').fill('Flagged-New-Passw0rd');
  await page.getByRole('button', { name: 'حفظ' }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('linked-counter')).toHaveText('تم الربط هذا الشهر: 0');
});
