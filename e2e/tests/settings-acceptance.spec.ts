import { expect, test, type Page } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

// Feature 004 acceptance (quickstart A, B, D, I). Sorts after admin-first-login.spec.ts; seeds its
// own synthetic admins through the API. Desktop project only (state-changing).
const SETTINGS_ADMIN = { name: 'أدمن الإعدادات', phone: '07700000141', permissions: ['settings'] };
const OTHER_ADMIN = { name: 'أدمن بلا إعدادات', phone: '07700000142', permissions: ['marketers'] };

async function openTab(page: Page, label: string) {
  await page.getByRole('tab', { name: label }).click();
}

test('an admin with only «الإعدادات» creates العلم, ALM01 and PLUS', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'desktop-only, state-changing test');

  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await apiCreateReadyAccount(request, main, 'admins', SETTINGS_ADMIN);
  await apiCreateReadyAccount(request, main, 'admins', OTHER_ADMIN);

  await signIn(page, SETTINGS_ADMIN.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByTestId('sidebar').getByRole('link', { name: 'الإعدادات' }).click();

  // Region.
  await page.getByRole('button', { name: 'إضافة منطقة' }).click();
  await page.getByRole('dialog').getByLabel('اسم المنطقة').fill('العلم');
  await page.getByRole('dialog').getByRole('button', { name: 'حفظ' }).click();
  await expect(page.getByTestId('item-row').filter({ hasText: 'العلم' })).toBeVisible();

  // Tower, typed in lower case.
  await openTab(page, 'الأبراج');
  await page.getByRole('button', { name: 'إضافة برج' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('رمز البرج').fill('alm01');
  await dialog.getByLabel('اسم البرج').fill('العلم 1');
  await dialog.getByLabel('المنطقة').click();
  await page.getByRole('option', { name: 'العلم' }).click();
  await dialog.getByRole('button', { name: 'حفظ' }).click();
  await expect(dialog).toBeHidden();
  const tower = page.getByTestId('item-row').filter({ hasText: 'ALM01' });
  await expect(tower).toContainText('العلم 1');

  // B: the same code again is refused.
  await page.getByRole('button', { name: 'إضافة برج' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('رمز البرج').fill('ALM01');
  await dialog.getByLabel('اسم البرج').fill('مكرر');
  await dialog.getByLabel('المنطقة').click();
  await page.getByRole('option', { name: 'العلم' }).click();
  await dialog.getByRole('button', { name: 'حفظ' }).click();
  await expect(dialog.getByText('رمز البرج مستخدم')).toBeVisible();
  await dialog.getByRole('button', { name: 'إلغاء' }).click();

  // Category with a price typed in Arabic digits.
  await openTab(page, 'الفئات');
  await page.getByRole('button', { name: 'إضافة فئة' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('اسم الفئة').fill('PLUS');
  await dialog.getByLabel('سعر الشهر التجريبي').fill('20000');
  await dialog.getByLabel('سعر الشهر الثاني').fill('٣٥٬٠٠٠');
  await dialog.getByRole('button', { name: 'حفظ' }).click();
  await expect(dialog).toBeHidden();
  const plan = page.getByTestId('item-row').filter({ hasText: 'PLUS' });
  await expect(plan).toContainText('20,000 د.ع');
  await expect(plan).toContainText('35,000 د.ع');

  // D: العلم has a tower, so no «حذف».
  await openTab(page, 'المناطق');
  const area = page.getByTestId('item-row').filter({ hasText: 'العلم' });
  await expect(area.getByRole('button', { name: 'تعديل' })).toBeVisible();
  await expect(area.getByRole('button', { name: 'حذف' })).toHaveCount(0);

  // The tab survives a reload (?tab=).
  await openTab(page, 'الشرائح');
  await page.reload();
  await expect(page.getByRole('tab', { name: 'الشرائح', selected: true })).toBeVisible();
  await expect(page.getByTestId('tier-row')).toHaveCount(3);

  // I: an admin without «الإعدادات» has no menu item and is redirected.
  const other = await browser.newContext({ ignoreHTTPSErrors: true });
  const otherPage = await other.newPage();
  await signIn(otherPage, OTHER_ADMIN.phone, NEW_PASSWORD);
  await expect(otherPage).toHaveURL(/\/admin$/);
  await expect(
    otherPage.getByTestId('sidebar').getByRole('link', { name: 'الإعدادات' }),
  ).toHaveCount(0);
  await otherPage.goto('/admin/settings');
  await expect(otherPage).toHaveURL(/\/admin$/);
  await other.close();
});
