import { Buffer } from 'node:buffer';

import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 015: import of the SAS subscribers, end to end (specs/015 T052, quickstart scenarios
 * 3, 5, 6, 9–13).
 *
 * A `reports` admin uploads a synthetic SAS export (its `ct_password` column holds markers that
 * must never show), maps an unknown prefix, uses «تخطي للكل» and switches one row back, and
 * confirms. Then a marketer's draft with a SAS phone (in the phone column, or only inside the
 * username) is case 1; a return by that phone goes to the admin, who sees «مشترك SAS» with the
 * expiry «حسب آخر استيراد» and accepts it, and the request keeps the SAS username. A re-import shows
 * the update and «غير موجود في آخر ملف» counts, and the mapping is remembered.
 *
 * Every phone, username, tower and number here is used by no other spec, and the drafts type
 * national IDs of their own, so the rest of the suite (files run in name order) is not affected.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة SAS';
const TOWER = 'SAE01';
const TOWER_NAME = 'برج SAS للاختبار';
const PLAN = 'SASPLAN';
const HOME = { latitude: 33.3128, longitude: 44.3615 };

const HEADER =
  'id,username,firstname,lastname,phone,expiration,notes,parent_name,ct_password,created_at,last_online,group_name';
const row = (id: string, username: string, phone: string) =>
  [
    id,
    username,
    'مشترك',
    'خاص',
    phone,
    '2099-12-01 00:00:00',
    '',
    'admin',
    `SYNTH-PW-E2E-${id}`,
    '2025-01-10 10:00:00',
    '2026-11-20 08:00:00',
    'PLUS',
  ].join(',');
// Row 2 is ready; row 3 has its phone only inside the username; row 4 has an unknown prefix;
// rows 5 and 6 repeat one username.
const FIRST = [
  HEADER,
  row('9001', `${TOWER}-07800015001`, '07800015001'),
  row('9002', `${TOWER}-07800015002`, ''),
  row('9003', 'ZZE09-07800015003', '07800015003'),
  row('9004', `${TOWER}-07800015004`, '07800015004'),
  row('9005', `${TOWER.toLowerCase()}-07800015004`, '07800015005'),
].join('\n');
// The same file without row 2 (it becomes «غير موجود في آخر ملف») and with a phone on row 3.
const SECOND = [
  HEADER,
  row('9002', `${TOWER}-07800015002`, '07800015009'),
  row('9003', 'ZZE09-07800015003', '07800015003'),
  row('9004', `${TOWER}-07800015004`, '07800015004'),
  row('9005', `${TOWER.toLowerCase()}-07800015004`, '07800015005'),
].join('\n');

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  await request.post(`${base}/towers`, {
    headers: main,
    data: { code: TOWER, name: TOWER_NAME, area_id: area.id },
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

/** A draft from the fake card, with typed numbers of its own, everything filled but the phone. */
async function cardDraft(page: Page, numbers: { nid: string; family: string }) {
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
  await typeField(page, 'national_id', numbers.nid);
  await page.getByTestId('adopt-current-national-id').click();
  await saved(page);
  await typeField(page, 'family_number', numbers.family);
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي SAS');
  await page.getByTestId('field-landmark').fill('قرب نقطة SAS');
  await page.getByTestId('field-landmark').blur();
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
}

async function upload(admin: Page, name: string, csv: string) {
  await admin.goto('/admin/import');
  await admin.getByRole('tab', { name: 'مشتركو SAS' }).click();
  await admin.getByLabel('ملف مشتركي SAS (xlsx أو csv)').setInputFiles({
    name,
    mimeType: 'text/csv',
    buffer: Buffer.from(csv, 'utf-8'),
  });
  await admin.getByRole('button', { name: 'رفع ومعاينة' }).click();
}

async function skipAllThenImport(admin: Page, index: number) {
  const dup = admin.getByTestId('group-username_dup_file');
  await dup.getByRole('button', { name: 'تخطي للكل' }).click();
  await expect(admin.getByTestId(`row-${index}`).getByRole('button', { name: 'تخطي' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await admin.getByTestId(`row-${index}`).getByRole('button', { name: 'استيراد' }).click();
  await expect(admin.getByTestId(`row-${index}`).getByRole('button', { name: 'استيراد' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
}

async function confirm(admin: Page, message: string) {
  await admin.getByRole('button', { name: 'تأكيد الاستيراد' }).click();
  const dialog = admin.getByRole('dialog');
  await expect(dialog).toContainText(message);
  await dialog.getByRole('button', { name: 'استيراد' }).click();
  await expect(admin.getByText('تم الاستيراد')).toBeVisible();
}

test('SAS import: mapping, «تخطي للكل», confirm; the check, the return, the review file, a re-import', async ({
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one import for the whole run');
  test.setTimeout(360_000);
  const main = await ensureCatalog(request);
  const reporter = { name: 'أدمن استيراد SAS', phone: '07700001591', permissions: ['reports'] };
  const marketer = { name: 'مسوّق SAS', phone: '07700001592' };
  await apiCreateReadyAccount(request, main, 'admins', reporter);
  await apiCreateReadyAccount(request, main, 'marketers', marketer);

  // --- the import -------------------------------------------------------------------------
  const admin = await pageFor(browser, reporter.phone, NEW_PASSWORD);
  await upload(admin, 'sas_e2e.csv', FIRST);
  await expect(admin.getByText('عدد الصفوف: 5')).toBeVisible({ timeout: 60_000 });
  await expect(admin.getByText('جديد: 5')).toBeVisible();
  await expect(admin.getByText('تحتاج قراراً: 2')).toBeVisible();
  await expect(admin.getByText(/SYNTH-PW/)).toHaveCount(0);
  await expect(admin.getByRole('button', { name: 'تأكيد الاستيراد' })).toBeDisabled();
  await expect(admin.getByText('بقيت 1 بادئة بلا برج')).toBeVisible();

  const prefix = admin.getByTestId('prefix-ZZE09');
  await prefix.getByLabel('برج ZZE09').selectOption({ label: `${TOWER_NAME} (${TOWER})` });
  await expect(admin.getByText('بقيت 1 بادئة بلا برج')).toHaveCount(0);
  await skipAllThenImport(admin, 5);
  await confirm(admin, 'سيُضاف 4 ويُحدَّث 0 من مشتركي SAS. لا يمكن التراجع بعد التأكيد.');
  await expect(admin.getByText('المضاف: 4')).toBeVisible();
  await expect(admin.getByText('المتخطّى: 1')).toBeVisible();
  await expect(admin.getByText('بادئات رُبطت: 1')).toBeVisible();
  await expect(admin.getByText('الصفوف المتخطّاة: الصف 6 (SAS 9005)')).toBeVisible();
  await admin.screenshot({ path: testInfo.outputPath('sas-summary.png'), fullPage: true });

  // --- case 1: the phone column, then the phone only inside the username ----------------------
  const m = await pageFor(browser, marketer.phone, NEW_PASSWORD);
  await cardDraft(m, { nid: '199900015001', family: '7015A0000000000001' });
  await typeField(m, 'phone_input', '07800015001');
  await m.getByTestId('otp-send').click();
  await expect(m.getByTestId('otp-error')).toHaveText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
  await expect(m.getByText(`${TOWER}-07800015001`)).toHaveCount(0); // nothing about the SAS record

  await typeField(m, 'phone_input', '07800015002');
  await m.getByTestId('otp-send').click();
  await expect(m.getByTestId('otp-error')).toHaveText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
  const offer = m.getByTestId('return-offer');
  await offer.getByRole('button', { name: 'طلب العودة للخدمة' }).click();
  await expect(m.getByTestId('return-chosen')).toBeVisible();
  await m.getByTestId('otp-send').click();
  await expect(m.getByTestId('otp-digit-0')).toBeFocused();
  await m.keyboard.type(FAKE_CODE);
  await expect(m.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await m.getByTestId('submit-button').click();
  await expect(m).toHaveURL(/\/requests\/\d+$/);
  await expect(m.getByText(/بانتظار موافقة المسؤول|طلبك بانتظار التدقيق/)).toBeVisible();
  await expect(m.getByText('مشترك SAS')).toHaveCount(0);
  await expect(m.getByText('مشترك خاص')).toHaveCount(0);
  const id = m.url().split('/').pop()!;

  // --- the review file, then the accepted return keeps the SAS username -------------------------
  const reviewer = await pageFor(browser, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  await reviewer.goto(`/admin/pending/${id}`);
  await expect(reviewer.getByText('مشترك SAS', { exact: true })).toBeVisible();
  // The request file shows its own «اليوزر» too: read the linked SAS record's card.
  const card = reviewer.locator('.MuiCard-root', { hasText: 'مشترك SAS' });
  await expect(card.getByLabel('اليوزر', { exact: true })).toHaveValue(`${TOWER}-07800015002`);
  await expect(card.getByLabel('تاريخ الانتهاء', { exact: true })).toHaveValue(
    /^2099-12-01 \(حسب آخر استيراد \d{4}-\d{2}-\d{2}\)$/,
  );
  await expect(card.getByLabel('الباقة في SAS', { exact: true })).toHaveValue('PLUS');
  // Its phone is only inside the username: «هاتف اليوزر» shows it.
  await expect(card.getByLabel('هاتف اليوزر', { exact: true })).toHaveValue('07800015002');
  await expect(card.getByText('منتهي')).toHaveCount(0);
  await reviewer.screenshot({ path: testInfo.outputPath('sas-review-file.png'), fullPage: true });
  await reviewer.getByRole('button', { name: 'قبول' }).click();
  const acceptDialog = reviewer.getByRole('dialog');
  await acceptDialog.getByRole('radio', { name: 'نعم' }).check();
  await acceptDialog.getByRole('button', { name: 'تأكيد القبول' }).click();
  await expect(reviewer.getByText('تم القبول')).toBeVisible();

  await m.goto(`/requests/${id}`);
  await expect(m.getByText('تمت الموافقة')).toBeVisible();
  await expect(m.getByTestId('request-username')).toHaveText(`${TOWER}-07800015002`);

  // --- a re-import: an update, a missing row, the remembered mapping -------------------------
  await upload(admin, 'sas_e2e_2.csv', SECOND);
  await expect(admin.getByText('عدد الصفوف: 4')).toBeVisible({ timeout: 60_000 });
  await expect(admin.getByText('سيُحدَّث: 2')).toBeVisible(); // row 2's phone, and row 5's repeat
  await expect(admin.getByText('غير موجود في آخر ملف: 1')).toBeVisible();
  await expect(admin.getByTestId('prefix-ZZE09')).toContainText('من استيراد سابق');
  await skipAllThenImport(admin, 4);
  await confirm(admin, 'سيُضاف 0 ويُحدَّث 1 من مشتركي SAS. لا يمكن التراجع بعد التأكيد.');
  await expect(admin.getByText('المحدَّث: 1')).toBeVisible();
  await expect(admin.getByText('وُسم «غير موجود في آخر ملف»: 1')).toBeVisible();

  // The row missing from the new file still counts in the check.
  await cardDraft(m, { nid: '199900015003', family: '7015A0000000000003' });
  await typeField(m, 'phone_input', '07800015001');
  await m.getByTestId('otp-send').click();
  await expect(m.getByTestId('otp-error')).toHaveText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
});
