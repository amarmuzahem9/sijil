import { Buffer } from 'node:buffer';

import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 014: import of the legacy Google Form subscribers, end to end (specs/014 T051,
 * quickstart scenarios 3, 5, 6, 9, 10, 12).
 *
 * A `reports` admin uploads a synthetic file (the fake Drive fetcher answers its links with
 * generated images or failures), uses «تخطي للكل» and switches one row back, and confirms. Then a
 * marketer's draft with an imported phone is case 1, a request with an imported family number goes
 * to the admin as a second subscription, and the review admin sees «مشترك قديم» with its images.
 *
 * Every phone, family number and national ID here is used by no other spec, and the request typed
 * a national ID of its own, so the rest of the suite (files run in name order) is not affected.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة القدامى';
const TOWER = 'LEG01';
const PLAN = 'LEGPLAN';
const HOME = { latitude: 33.3128, longitude: 44.3615 };
const LINK = 'https://drive.google.com/open?id=';

const HEADER =
  'طابع زمني,الاسم الاول,الاسم الثاني,الاسم الثالث,اسم الام,اسم اب الام,تاريخ الميلاد,الرقم العائلي,' +
  'رقم الهاتف,صورة البطافة الموحدة الوجه,صورة البطاقة الموحدة الظهر,عنوان البريد الإلكتروني,' +
  'البريد الإلكتروني,ID,الحالة';
const row = (n: string, name: string, family: string, phone: string, back: string, status = 'تم') =>
  [
    '2024/05/01 10:00:00',
    name,
    'تجريبي',
    'نموذج',
    'عينة',
    'مثال',
    '1990/01/10',
    family,
    phone,
    `${LINK}fake-ok-f-e2e-${n}`,
    `${LINK}${back}`,
    '',
    '',
    `T3C-2${n}`,
    status,
  ].join(',');
// Row 2 is ready; rows 3 and 4 repeat one family number; row 5 is «ملغي» and its back image is
// not shared.
const CSV = [
  HEADER,
  row('01', 'سمير', '7001A0000000000002', '07800014902', 'fake-ok-b-e2e-01'),
  row('02', 'علي', '7001A0000000000003', '07800014903', 'fake-ok-b-e2e-02'),
  row('03', 'حسن', '7001a00000000000o3', '07800014904', 'fake-ok-b-e2e-03'),
  row('04', 'كريم', '7001A0000000000005', '07800014905', 'fake-private-e2e-04', 'ملغي'),
].join('\n');

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  await request.post(`${base}/towers`, {
    headers: main,
    data: { code: TOWER, name: 'برج القدامى', area_id: area.id },
  });
  await request.post(`${base}/plans`, {
    headers: main,
    data: { name: PLAN, trial_price: 20000, second_price: 35000 },
  });
  return main;
}

async function pageFor(browser: Browser, phone: string, password: string): Promise<Page> {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation(HOME);
  const page = await context.newPage();
  await signIn(page, phone, password);
  // Wait for the signed-in page before navigating, or the next goto lands on «تسجيل الدخول».
  await expect(page).not.toHaveURL(/\/login/);
  await expect(page.getByRole('button', { name: 'دخول' })).toHaveCount(0);
  return page;
}

const saved = (page: Page) => expect(page.getByTestId('save-badge')).toHaveText('محفوظ');

async function choose(page: Page, label: string, option: string | RegExp) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

async function typeField(page: Page, name: string, value: string) {
  await page.getByTestId(`field-${name}`).fill(value);
  await page.getByTestId(`field-${name}`).blur();
  await saved(page);
}

/** A draft from the fake card with everything filled but the phone. */
async function cardDraft(page: Page, numbers?: { nid: string; family: string }) {
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
  if (numbers) {
    await typeField(page, 'national_id', numbers.nid);
    await page.getByTestId('adopt-current-national-id').click();
    await saved(page);
    await typeField(page, 'family_number', numbers.family);
  }
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي القدامى');
  await page.getByTestId('field-landmark').fill('قرب نقطة القدامى');
  await page.getByTestId('field-landmark').blur();
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
}

test('legacy import: preview, «تخطي للكل», confirm; then the check and the review file', async ({
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one import for the whole run');
  test.setTimeout(300_000);
  const main = await ensureCatalog(request);
  const reporter = { name: 'أدمن الاستيراد', phone: '07700001491', permissions: ['reports'] };
  const marketer = { name: 'مسوّق القدامى', phone: '07700001492' };
  await apiCreateReadyAccount(request, main, 'admins', reporter);
  await apiCreateReadyAccount(request, main, 'marketers', marketer);

  // --- the import -------------------------------------------------------------------------
  const admin = await pageFor(browser, reporter.phone, NEW_PASSWORD);
  await admin.goto('/admin/import');
  await expect(admin.getByRole('tab', { name: 'المشتركون القدامى' })).toBeVisible();
  await admin.getByLabel('ملف المشتركين القدامى (xlsx أو csv)').setInputFiles({
    name: 'legacy_e2e.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(CSV, 'utf-8'),
  });
  await admin.getByRole('button', { name: 'رفع ومعاينة' }).click();
  await expect(admin.getByText('عدد الصفوف: 4')).toBeVisible({ timeout: 60_000 });
  await expect(admin.getByText('جاهزة: 1')).toBeVisible();
  await expect(admin.getByText('تحتاج قراراً: 3')).toBeVisible();
  await expect(admin.getByText('ملغي: 1 (لا تُحسب في الفحص)')).toBeVisible();
  await expect(admin.getByRole('button', { name: 'تأكيد الاستيراد' })).toBeDisabled();

  const dup = admin.getByTestId('group-family_dup_file');
  await dup.getByRole('button', { name: 'تخطي للكل' }).click();
  await expect(admin.getByTestId('row-3').getByRole('button', { name: 'تخطي' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(admin.getByTestId('row-4').getByRole('button', { name: 'تخطي' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await admin.getByTestId('row-3').getByRole('button', { name: 'استيراد' }).click();
  await expect(admin.getByTestId('row-3').getByRole('button', { name: 'استيراد' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  const failed = admin.getByTestId('row-5');
  await expect(failed).toContainText('تعذّر سحب الصورة (الظهر: الملف غير مشترك)');
  await expect(failed).toContainText('لا يُحسب في الفحص');
  await failed.getByRole('button', { name: 'استيراد' }).click();

  await admin.getByRole('button', { name: 'تأكيد الاستيراد' }).click();
  const dialog = admin.getByRole('dialog');
  await expect(dialog).toContainText('سيُحفظ 3 مشتركاً قديماً. لا يمكن التراجع بعد التأكيد.');
  await dialog.getByRole('button', { name: 'استيراد' }).click();
  await expect(admin.getByText('تم الاستيراد')).toBeVisible();
  await expect(admin.getByText('المستورد: 3')).toBeVisible();
  await expect(admin.getByText('المتخطّى: 1')).toBeVisible();
  await expect(admin.getByText('الصفوف المتخطّاة: T3C-203')).toBeVisible();
  await expect(admin.getByText('الصفوف غير المكتملة: T3C-204')).toBeVisible();
  await admin.screenshot({ path: testInfo.outputPath('legacy-summary.png'), fullPage: true });

  // --- case 1: an imported phone ------------------------------------------------------------
  const m = await pageFor(browser, marketer.phone, NEW_PASSWORD);
  await cardDraft(m);
  await typeField(m, 'phone_input', '07800014902');
  await m.getByTestId('otp-send').click();
  await expect(m.getByTestId('otp-error')).toHaveText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
  await expect(m.getByText('سمير تجريبي نموذج')).toHaveCount(0); // nothing about the old record
  await expect(m.getByText('T3C-201')).toHaveCount(0);

  // A «ملغي» row's phone does not count.
  await typeField(m, 'phone_input', '07800014905');
  await expect(m.getByTestId('phone-used')).toHaveCount(0);

  // --- case 3: an imported family number (written in lower case) ----------------------------
  await cardDraft(m, { nid: '199900014903', family: '7001a0000000000002' });
  await expect(m.getByTestId('family-exists')).toContainText('لهذه العائلة اشتراك سابق');
  await m.getByTestId('confirm-additional').click();
  await expect(m.getByTestId('family-confirmed')).toBeVisible();
  await typeField(m, 'phone_input', '07800014910');
  await m.getByTestId('otp-send').click();
  await expect(m.getByTestId('otp-digit-0')).toBeFocused();
  await m.keyboard.type(FAKE_CODE);
  await expect(m.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await m.getByTestId('submit-button').click();
  await expect(m).toHaveURL(/\/requests\/\d+$/);
  // Two reasons (family and typed numbers): either pending text of the result screen.
  await expect(m.getByText(/بانتظار موافقة المسؤول|طلبك بانتظار التدقيق/)).toBeVisible();
  const id = m.url().split('/').pop()!;

  // --- the review file ------------------------------------------------------------------------
  const reviewer = await pageFor(browser, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await reviewer.goto(`/admin/pending/${id}`);
  await expect(reviewer.getByText('مشترك قديم', { exact: true })).toBeVisible();
  await expect(reviewer.getByLabel('الرقم القديم')).toHaveValue('T3C-201');
  await expect(reviewer.getByLabel('الحالة في الملف القديم')).toHaveValue('تم');
  await expect(reviewer.getByText('بيانات إضافية')).toBeVisible();
  await expect(reviewer.getByRole('img', { name: 'صورة السجل 1' })).toBeVisible({ timeout: 15_000 });
  await expect(reviewer.getByRole('img', { name: 'صورة السجل 2' })).toBeVisible();
  await reviewer.screenshot({ path: testInfo.outputPath('legacy-review-file.png'), fullPage: true });
});
