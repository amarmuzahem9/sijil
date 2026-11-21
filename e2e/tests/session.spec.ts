import { expect, test } from '@playwright/test';

import { env, signIn } from './helpers';

const DEMO_MARKETER = '07700000001';

test('session survives a new page; sign-out ends it and back does not reveal pages', async ({
  page,
  context,
}) => {
  await signIn(page, DEMO_MARKETER, env('DEMO_MARKETER_PASSWORD'));
  await expect(page.getByTestId('linked-counter')).toBeVisible();

  // Same browser, new page: signed in through the refresh cookie (FR-008).
  const second = await context.newPage();
  await second.goto('/');
  await expect(second.getByTestId('linked-counter')).toBeVisible();
  await second.close();

  await page.goto('/account');
  await page.getByRole('button', { name: 'تسجيل الخروج' }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByTestId('linked-counter')).toHaveCount(0);

  // A full reload must not sign the user back in (the server session is revoked).
  await page.goto('/');
  await expect(page).toHaveURL(/\/login$/);
});
