import { expect, type Page } from '@playwright/test';

export const ADMIN_PAGES = [
  'الرئيسية',
  'طلبات بالانتظار',
  'بانتظار الربط',
  'المشتركون',
  'المسوّقون',
  'الإعدادات',
  'الأدمنية والصلاحيات',
  'التقارير والتصدير',
  'الاستيراد',
  'النسخ الاحتياطي',
  'سجل العمليات',
];

export const MARKETER_TABS = ['الرئيسية', 'الطلبات', 'الإشعارات', 'حسابي'];

export function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set for e2e tests`);
  return value;
}

export async function signIn(page: Page, phone: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.locator('input[name=phone]').fill(phone);
  await page.locator('input[name=password]').fill(password);
  await page.getByRole('button', { name: 'دخول' }).click();
}

/** True when the element's centre is in the right half of the viewport (RTL layout). */
export async function expectOnRightSide(page: Page, testId: string): Promise<void> {
  const box = await page.getByTestId(testId).boundingBox();
  const width = page.viewportSize()!.width;
  expect(box, `${testId} should be visible`).not.toBeNull();
  expect(box!.x + box!.width / 2).toBeGreaterThan(width / 2);
}
