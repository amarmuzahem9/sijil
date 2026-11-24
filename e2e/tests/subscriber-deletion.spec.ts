import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 011: «حذف مشترك», end to end (specs/011 tasks T058).
 *
 * Like admin-review.spec.ts, every request types its own synthetic national ID and family number
 * over the fake card's reading, so it is an «تعديل الأرقام» request and the fake person's numbers
 * are never stored. Phones, names and numbers are synthetic.
 *
 * 1. The marketer submits A and B (B a second subscription of A's family); both wait.
 * 2. An admin with «مراجعة» and «حذف مشترك» deletes A with «طلب مكرر», typing the number in
 *    Arabic-Indic digits: the banner, and B's linked record reads «سجل محذوف».
 * 3. The marketer sees A as «محذوف» and submits again with A's phone: it is free.
 * 4. B is rejected, opened again through «فتح طلب برقمه» and deleted with «خطأ إدخال».
 * 5. An admin with «مراجعة» only sees no «حذف».
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة الحذف';
const TOWER = 'DEL01';
const PLAN = 'DELPLAN';
const HOME = { latitude: 33.3128, longitude: 44.3615 };
const FAMILY = '6666D0000000000001';
const PHONE_A = '07800001201';

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  await request.post(`${base}/towers`, {
    headers: main,
    data: { code: TOWER, name: 'برج الحذف', area_id: area.id },
  });
  await request.post(`${base}/plans`, {
    headers: main,
    data: { name: PLAN, trial_price: 20000, second_price: 35000 },
  });
  return main;
}

async function choose(page: Page, label: string, option: string | RegExp) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

const saved = (page: Page) => expect(page.getByTestId('save-badge')).toHaveText('محفوظ');

async function typeField(page: Page, name: string, value: string) {
  await page.getByTestId(`field-${name}`).fill(value);
  await page.getByTestId(`field-${name}`).blur();
  await saved(page);
}

/** Submit a pending request with typed numbers; its id and number label («T3C-…»). */
async function submitEdited(
  page: Page,
  nid: string,
  family: string,
  phone: string,
  { additional = false } = {},
): Promise<{ id: string; label: string }> {
  await page.goto('/drafts/new');
  for (const [side, scenario] of [
    ['front', 'clear_front'],
    ['back', 'clear_back'],
  ] as const) {
    await page.getByTestId(`image-${side}-gallery`).setInputFiles(await scenarioPhoto(page, scenario));
    await expect(page.getByTestId(`image-${side}-thumbnail`)).toBeVisible({ timeout: 30_000 });
  }
  await expect(page.getByTestId('field-national_id')).toHaveValue('199912345678', { timeout: 30_000 });
  await page.getByTestId('field-great_grandfather_name').fill('نموذج');
  await typeField(page, 'national_id', nid);
  await page.getByTestId('adopt-current-national-id').click();
  await saved(page);
  await typeField(page, 'family_number', family);
  if (additional) {
    await page.getByTestId('confirm-additional').click();
    await expect(page.getByTestId('family-confirmed')).toBeVisible();
  }
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي الحذف');
  await page.getByTestId('field-landmark').fill('قرب نقطة الحذف');
  await page.getByTestId('field-landmark').blur();
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
  await typeField(page, 'phone_input', phone);
  // A used phone would stop here with «المشترك موجود سابقاً…».
  await expect(page.getByText('المشترك موجود سابقاً، هل يود العودة للخدمة؟')).toHaveCount(0);

  await page.getByTestId('otp-send').click();
  await expect(page.getByTestId('otp-digit-0')).toBeFocused();
  await page.keyboard.type(FAKE_CODE);
  await expect(page.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await page.getByTestId('submit-button').click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
  const heading = await page.getByTestId('request-result').locator('h6').first().textContent();
  return { id: page.url().split('/').pop()!, label: heading!.replace('#', '').trim() };
}

async function adminPage(browser: Browser, phone: string): Promise<Page> {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: true })).newPage();
  await signIn(page, phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/admin/);
  return page;
}

const toArabicIndic = (digits: string) => digits.replace(/\d/g, (d) => '٠١٢٣٤٥٦٧٨٩'[Number(d)]);

async function deleteOpenFile(admin: Page, label: string, reason: string, typed: string) {
  await admin.getByRole('button', { name: 'حذف', exact: true }).click();
  const dialog = admin.getByRole('dialog');
  await expect(dialog.getByText('ستُمسح البيانات الشخصية وصور البطاقة نهائياً ولا يمكن التراجع')).toBeVisible();
  const confirm = dialog.getByRole('button', { name: 'حذف نهائي' });
  await dialog.getByRole('radio', { name: reason }).check();
  await expect(confirm).toBeDisabled();
  await dialog.getByRole('textbox', { name: /اكتب رقم الطلب للتأكيد/ }).fill(typed);
  await expect(confirm).toBeEnabled();
  await confirm.click();
  const banner = admin.getByRole('status');
  await expect(banner).toContainText('تم حذف بيانات هذا الطلب');
  await expect(banner).toContainText(reason);
  await expect(admin.getByRole('region', { name: 'البطاقة' })).toHaveCount(0);
  await expect(admin.getByRole('heading', { name: new RegExp(label) })).toBeVisible();
}

test('the admin deletes a duplicate and a rejected request; the phone is free again', async ({ page, request, browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of requests');
  test.setTimeout(600_000);
  const main = await ensureCatalog(request);
  const m = { name: 'مسوّق الحذف', phone: '07700001201' };
  const deleter = { name: 'أدمن الحذف', phone: '07700001202', permissions: ['review', 'delete'] };
  const reviewer = { name: 'أدمن المراجعة فقط', phone: '07700001203', permissions: ['review'] };
  await apiCreateReadyAccount(request, main, 'marketers', m);
  await apiCreateReadyAccount(request, main, 'admins', deleter);
  await apiCreateReadyAccount(request, main, 'admins', reviewer);

  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation(HOME);
  await signIn(page, m.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);

  // --- 1. two waiting requests of one family ---------------------------------------------------
  const a = await submitEdited(page, '199966660001', FAMILY, PHONE_A);
  const b = await submitEdited(page, '199966660002', FAMILY, '07800001202', { additional: true });

  // --- 5 first: «مراجعة» alone offers no «حذف» -------------------------------------------------
  const viewer = await adminPage(browser, reviewer.phone);
  await viewer.goto(`/admin/pending/${a.id}`);
  await expect(viewer.getByRole('heading', { name: new RegExp(a.label) })).toBeVisible();
  await expect(viewer.getByRole('button', { name: 'حذف', exact: true })).toHaveCount(0);
  await viewer.close();

  // --- 2. delete A, typing its number in Arabic-Indic digits -------------------------------------
  const admin = await adminPage(browser, deleter.phone);
  await admin.goto(`/admin/pending/${a.id}`);
  await deleteOpenFile(admin, a.label, 'طلب مكرر', toArabicIndic(a.label.replace('T3C-', '')));
  await admin.goto('/admin/pending');
  await expect(admin.getByText(a.label, { exact: true })).toHaveCount(0);
  await admin.goto(`/admin/pending/${b.id}`);
  await expect(admin.getByText(`سجل محذوف (#${a.label})`)).toBeVisible();

  // --- 3. the marketer's view, and A's phone is free ---------------------------------------------
  await page.goto('/requests');
  const row = page.getByTestId('submitted-list').getByRole('link').filter({ hasText: a.label });
  await expect(row.getByText('محذوف', { exact: true })).toBeVisible();
  await expect(row.getByText('سبب الحذف: طلب مكرر')).toBeVisible();
  await row.click();
  await expect(page.getByText('تم حذف الطلب')).toBeVisible();
  await expect(page.getByRole('button', { name: /نسخ/ })).toHaveCount(0);
  const again = await submitEdited(page, '199966660003', '6666D0000000000003', PHONE_A);
  expect(Number(again.label.replace('T3C-', ''))).toBeGreaterThan(Number(a.label.replace('T3C-', '')));

  // --- 4. reject B, open it by its number and delete it -----------------------------------------
  await admin.goto(`/admin/pending/${b.id}`);
  await admin.getByRole('button', { name: 'رفض' }).click();
  await admin.getByRole('radio', { name: 'سبب آخر' }).check();
  await admin.getByRole('textbox', { name: /^سبب الرفض/ }).fill('ملاحظة تجريبية');
  await admin.getByRole('button', { name: 'تأكيد الرفض' }).click();
  await expect(admin.getByText('تم رفض الطلب')).toBeVisible();
  await admin.goto('/admin/pending');
  await admin.getByRole('textbox', { name: 'فتح طلب برقمه' }).fill(b.label);
  await admin.getByRole('textbox', { name: 'فتح طلب برقمه' }).press('Enter');
  await expect(admin).toHaveURL(new RegExp(`/admin/pending/${b.id}$`));
  await deleteOpenFile(admin, b.label, 'خطأ إدخال', b.label);
  await expect(admin.getByRole('status')).toContainText('سبب الرفض: سبب آخر');
  await expect(admin.getByText('ملاحظة تجريبية')).toHaveCount(0);
  await admin.screenshot({ path: testInfo.outputPath('deleted-file.png'), fullPage: true });

  await admin.goto('/admin/pending');
  await admin.getByRole('textbox', { name: 'فتح طلب برقمه' }).fill('999999');
  await admin.getByRole('button', { name: 'فتح', exact: true }).click();
  await expect(admin.getByText('لا يوجد طلب بهذا الرقم')).toBeVisible();
  await admin.close();
});
