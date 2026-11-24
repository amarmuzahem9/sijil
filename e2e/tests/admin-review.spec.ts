import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 010: the admin review of pending requests, end to end (specs/010 tasks T058).
 *
 * Every fake card carries the same person, whom submit.spec.ts and subscriber-existing.spec.ts
 * submit later (files run in name order). So every request here types its own synthetic national
 * ID and family number over the reading: each one is an «تعديل الأرقام» request, and the fake
 * person's numbers are never stored on a request. Phones, names and numbers are synthetic.
 *
 * 1. R1 (N1, FX) is accepted: it becomes the existing family.
 * 2. R2 (N2, FX) is a second subscription; the admin accepts it, and the marketer sees «تمت الموافقة».
 * 3. R3 is rejected with «سبب آخر»; the marketer reads the note.
 * 4. R4's numbers are pinned to R1's: the red «نفس الشخص» warning, then «القبول رغم التحذير؟».
 * 5. An admin with only «الإعدادات» has no «طلبات بالانتظار».
 * The review file is then checked at phone width.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة المراجعة';
const TOWER = 'REV01';
const PLAN = 'REVPLAN';
const HOME = { latitude: 33.3128, longitude: 44.3615 };
const N1 = '199955550001';
const N2 = '199955550002';
const N3 = '199955550003';
const N4 = '199955550004';
const FX = '5555K0000000000001';
const NOTE = 'طلب مكرر للتجربة';

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  await request.post(`${base}/towers`, {
    headers: main,
    data: { code: TOWER, name: 'برج المراجعة', area_id: area.id },
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

/** Submit a request from the fake card with a typed national ID and family number; its id. */
async function submitEdited(
  page: Page,
  nid: string,
  family: string,
  phone: string,
  { additional = false } = {},
): Promise<string> {
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
  // The typed number differs from the back of the card: keep the typed one.
  await page.getByTestId('adopt-current-national-id').click();
  await saved(page);
  await typeField(page, 'family_number', family);
  if (additional) {
    await page.getByTestId('confirm-additional').click();
    await expect(page.getByTestId('family-confirmed')).toBeVisible();
  }
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي المراجعة');
  await page.getByTestId('field-landmark').fill('قرب نقطة المراجعة');
  await page.getByTestId('field-landmark').blur();
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
  await typeField(page, 'phone_input', phone);

  await page.getByTestId('otp-send').click();
  await expect(page.getByTestId('otp-digit-0')).toBeFocused();
  await page.keyboard.type(FAKE_CODE);
  await expect(page.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await page.getByTestId('submit-button').click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
  return page.url().split('/').pop()!;
}

async function adminPage(browser: Browser, phone: string): Promise<Page> {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: true })).newPage();
  await signIn(page, phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/admin/);
  return page;
}

async function accept(page: Page, id: string) {
  await page.goto(`/admin/pending/${id}`);
  await page.getByRole('button', { name: 'قبول' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'تأكيد القبول' }).click();
  await expect(page.getByText('تم القبول')).toBeVisible();
}

async function pinTyped(page: Page, group: string, value: string) {
  const scope = page.getByRole('group', { name: group });
  await scope.getByRole('textbox', { name: 'قيمة أخرى' }).fill(value);
  await scope.getByRole('button', { name: 'تثبيت القيمة: قيمة أخرى' }).click();
  await expect(scope.getByRole('textbox', { name: 'القيمة الحالية' })).toHaveValue(value);
}

test('the admin accepts, rejects, pins and accepts despite a warning', async ({ page, request, browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of requests; phone width is checked below');
  test.setTimeout(600_000);
  const main = await ensureCatalog(request);
  const m = { name: 'مسوّق المراجعة', phone: '07700001101' };
  const reviewer = { name: 'أدمن المراجعة', phone: '07700001102', permissions: ['review'] };
  const settingsOnly = { name: 'أدمن الإعدادات فقط', phone: '07700001103', permissions: ['settings'] };
  await apiCreateReadyAccount(request, main, 'marketers', m);
  await apiCreateReadyAccount(request, main, 'admins', reviewer);
  await apiCreateReadyAccount(request, main, 'admins', settingsOnly);

  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation(HOME);
  await signIn(page, m.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  const admin = await adminPage(browser, reviewer.phone);

  // --- 1. R1 becomes the existing family -------------------------------------------------------
  const r1 = await submitEdited(page, N1, FX, '07800001101');
  await admin.goto('/admin/pending');
  await expect(admin.getByText('تعديل الأرقام').first()).toBeVisible();
  await accept(admin, r1);

  // --- 2. the second subscription: accept, and the marketer sees the username -------------------
  const r2 = await submitEdited(page, N2, FX, '07800001102', { additional: true });
  await admin.goto(`/admin/pending/${r2}`);
  await expect(admin.getByText('إذا كان للاشتراك الأول 15 يوماً أو أكثر متبقية: قبول. أقل من ذلك: رفض.')).toBeVisible();
  await expect(admin.getByText('تاريخ الانتهاء غير متوفر')).toBeVisible();
  await accept(admin, r2);
  await page.goto(`/requests/${r2}`);
  await expect(page.getByText('تمت الموافقة')).toBeVisible();
  // The username also shows inside «رسالة الربط» since 012; check its own field.
  await expect(page.getByTestId('request-username')).toHaveText(`${TOWER}-07800001102`);
  await expect(page.getByText(reviewer.name)).toHaveCount(0);

  // --- 3. reject with «سبب آخر» ------------------------------------------------------------------
  const r3 = await submitEdited(page, N3, '5555K0000000000003', '07800001103');
  await admin.goto(`/admin/pending/${r3}`);
  await admin.getByRole('button', { name: 'رفض' }).click();
  await admin.getByRole('radio', { name: 'سبب آخر' }).check();
  await expect(admin.getByText('لا تكتب أي معلومة عن مشترك آخر')).toBeVisible();
  await admin.getByRole('textbox', { name: /^سبب الرفض/ }).fill(NOTE);
  await admin.getByRole('button', { name: 'تأكيد الرفض' }).click();
  await expect(admin.getByText('تم رفض الطلب')).toBeVisible();
  await page.goto(`/requests/${r3}`);
  await expect(page.getByText('تم رفض الطلب')).toBeVisible();
  await expect(page.getByTestId('rejection-label')).toHaveText(NOTE);

  // --- 4. pin to R1's numbers: the red warning and «القبول رغم التحذير؟» --------------------------
  const r4 = await submitEdited(page, N4, '5555K0000000000004', '07800001104');
  await admin.goto(`/admin/pending/${r4}`);
  await pinTyped(admin, 'الرقم الوطني', N1);
  await pinTyped(admin, 'الرقم العائلي', FX);
  await expect(admin.getByText('تحذير: الأرقام المثبّتة تطابق مشتركاً موجوداً (نفس الشخص)')).toBeVisible();
  await expect(admin.getByText('تم التثبيت')).toBeVisible();
  await admin.getByRole('button', { name: 'قبول' }).click();
  const dialog = admin.getByRole('dialog', { name: 'القبول رغم التحذير؟' });
  await expect(dialog).toContainText('نفس الشخص');
  await dialog.getByRole('button', { name: 'القبول رغم التحذير' }).click();
  await expect(admin.getByText('تم القبول')).toBeVisible();
  await admin.screenshot({ path: testInfo.outputPath('review-despite-warning.png'), fullPage: true });
  await admin.close();

  // --- the review file at phone width ------------------------------------------------------------
  const phone = await (await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 412, height: 915 } })).newPage();
  await signIn(phone, reviewer.phone, NEW_PASSWORD);
  await expect(phone).toHaveURL(/\/admin/);
  await phone.goto(`/admin/pending/${r4}`);
  await expect(phone.getByText('تم القبول')).toBeVisible();
  const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const columns = await phone
    .getByTestId('readonly-fields')
    .first()
    .evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').length);
  expect(columns).toBe(1);
  await phone.screenshot({ path: testInfo.outputPath('review-phone.png'), fullPage: true });
  await phone.close();

  // --- 5. «الإعدادات» only: no «طلبات بالانتظار» -----------------------------------------------
  const other = await adminPage(browser, settingsOnly.phone);
  await expect(other.getByRole('link', { name: 'الإعدادات' }).first()).toBeVisible();
  await expect(other.getByRole('link', { name: 'طلبات بالانتظار' })).toHaveCount(0);
  await other.goto(`/admin/pending/${r4}`);
  await expect(other.getByText('تم القبول')).toHaveCount(0);
  await other.close();
});
