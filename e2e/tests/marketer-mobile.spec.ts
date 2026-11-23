import { expect, test } from '@playwright/test';

import { env, expectOnRightSide, MARKETER_TABS, signIn } from './helpers';

const DEMO_MARKETER = '07700000001'; // synthetic account from `seed-demo`

test('marketer: dashboard skeleton, navigation and admin refusal', async ({ page }, testInfo) => {
  await signIn(page, DEMO_MARKETER, env('DEMO_MARKETER_PASSWORD'));

  await expect(page).toHaveURL(/\/$/);
  // Enabled since feature 005: it opens the single-page form.
  await expect(page.getByRole('link', { name: 'إضافة مشترك جديد' })).toHaveAttribute(
    'href',
    '/drafts/new',
  );
  // Enabled since feature 009: the same form; the checks decide the path.
  await expect(page.getByRole('link', { name: 'إضافة اشتراك لمشترك موجود' })).toHaveAttribute(
    'href',
    '/drafts/new',
  );
  await expect(page.getByTestId('linked-counter')).toHaveText('تم الربط هذا الشهر: 0');

  if (testInfo.project.name === 'desktop-chrome') {
    await expect(page.getByTestId('sidebar')).toBeVisible();
    await expectOnRightSide(page, 'sidebar');
    await expect(page.getByTestId('user-identity')).toContainText('مسوّق');
    await expect(page.getByTestId('bottom-nav')).toHaveCount(0);
  } else {
    const bottom = page.getByTestId('bottom-nav');
    await expect(bottom).toBeVisible();
    const labels = await bottom.getByRole('link').allInnerTexts();
    expect(labels.map((l) => l.trim())).toEqual(MARKETER_TABS);
    await expect(page.getByTestId('sidebar')).toHaveCount(0);
  }

  // A marketer opening an admin address is sent back to the dashboard (session restored on reload).
  await page.goto('/admin');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('linked-counter')).toBeVisible();
});
