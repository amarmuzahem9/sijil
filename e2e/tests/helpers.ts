import { expect, type APIRequestContext, type Page } from '@playwright/test';

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
  'أرشيف الحسابات',
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

/** Set by admin-first-login.spec.ts, which runs first (workers: 1, files in name order). */
export const MAIN_ADMIN_PASSWORD = 'E2e-New-Passw0rd';

/** Synthetic accounts for feature 002 (never real people). */
export const TEMP_PASSWORD = 'Temp-Passw0rd-1';
export const NEW_PASSWORD = 'Own-Passw0rd-22';

export async function changeForcedPassword(page: Page, current: string, next: string) {
  await expect(page).toHaveURL(/\/change-password$/);
  await page.locator('input[name=current_password]').fill(current);
  await page.locator('input[name=new_password]').fill(next);
  await page.locator('input[name=confirm_password]').fill(next);
  await page.getByRole('button', { name: 'حفظ' }).click();
  await expect(page).not.toHaveURL(/\/change-password$/);
}

export async function apiSignIn(request: APIRequestContext, phone: string, password: string) {
  const r = await request.post('/api/auth/login', { data: { phone, password } });
  expect(r.status(), `login ${phone}`).toBe(200);
  return { Authorization: `Bearer ${(await r.json()).access_token}` };
}

/** Create an account as `headers` and clear its forced password change; returns its id. */
export async function apiCreateReadyAccount(
  request: APIRequestContext,
  headers: Record<string, string>,
  kind: 'admins' | 'marketers',
  body: { name: string; phone: string; permissions?: string[] },
): Promise<number> {
  const r = await request.post(`/api/admin/${kind}`, {
    headers,
    data: { ...body, temporary_password: TEMP_PASSWORD },
  });
  expect(r.status(), `create ${body.phone}`).toBe(201);
  const own = await apiSignIn(request, body.phone, TEMP_PASSWORD);
  const c = await request.post('/api/auth/change-password', {
    headers: own,
    data: { current_password: TEMP_PASSWORD, new_password: NEW_PASSWORD },
  });
  expect(c.status()).toBe(200);
  return (await r.json()).id;
}
