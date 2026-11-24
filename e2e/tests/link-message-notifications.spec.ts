import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 012: the link message, the notifications and the search, end to end (specs/012 T052).
 *
 * Like admin-review.spec.ts, every request types its own synthetic national ID and family number
 * over the fake card's reading, so it waits for the admin («تعديل الأرقام») and the fake person's
 * numbers are never stored. Phones, names and numbers are synthetic.
 *
 * 1. R1 waits: no link message. The admin accepts it; the marketer's bell shows 1.
 * 2. The notification opens R1: the link message (§8.4) is copied and shared to WhatsApp.
 * 3. R2 is rejected with «سبب آخر» and then deleted: the marketer gets «تم حذف الطلب», and the
 *    rejection notification shows «محذوف» without the name.
 * 4. Search: R1 by name, R2 by its number only; another marketer finds nothing.
 * The notifications page is then checked at phone width.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة الإشعارات';
const TOWER = 'NTF01';
const TOWER_NAME = 'برج الإشعارات';
const PLAN = 'NTFPLAN';
const HOME = { latitude: 33.3128, longitude: 44.3615 };
const N1 = '199977770001';
const N2 = '199977770002';
const F1 = '7777N0000000000001';
const F2 = '7777N0000000000002';
const NOTE = 'ملاحظة الإشعارات التجريبية';

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
async function submitEdited(page: Page, nid: string, family: string, phone: string): Promise<{ id: string; label: string }> {
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
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي الإشعارات');
  await page.getByTestId('field-landmark').fill('قرب نقطة الإشعارات');
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
  const heading = await page.getByTestId('request-result').locator('h6').first().textContent();
  return { id: page.url().split('/').pop()!, label: heading!.replace('#', '').trim() };
}

async function adminPage(browser: Browser, phone: string): Promise<Page> {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: true })).newPage();
  await signIn(page, phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/admin/);
  return page;
}

const search = (page: Page) => page.getByRole('searchbox', { name: 'بحث بالاسم أو الهاتف أو رقم الطلب' });

test('link message, notifications on decisions and deletion, and search', async ({ page, request, browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of requests; phone width is checked below');
  test.setTimeout(600_000);
  const main = await ensureCatalog(request);
  const m = { name: 'مسوّق الإشعارات', phone: '07700001301' };
  const other = { name: 'مسوّق آخر للإشعارات', phone: '07700001303' };
  const admin = { name: 'أدمن الإشعارات', phone: '07700001302', permissions: ['review', 'delete'] };
  await apiCreateReadyAccount(request, main, 'marketers', m);
  await apiCreateReadyAccount(request, main, 'marketers', other);
  await apiCreateReadyAccount(request, main, 'admins', admin);

  await page.context().grantPermissions(['geolocation', 'clipboard-read', 'clipboard-write']);
  await page.context().setGeolocation(HOME);
  await signIn(page, m.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);

  // --- 1. R1 waits, then is accepted: the bell shows 1 -----------------------------------------
  const r1 = await submitEdited(page, N1, F1, '07800001301');
  await expect(page.getByTestId('link-message')).toHaveCount(0);
  await expect(page.getByTestId('unread-badge')).toHaveCount(0);

  const reviewer = await adminPage(browser, admin.phone);
  await reviewer.goto(`/admin/pending/${r1.id}`);
  await reviewer.getByRole('button', { name: 'قبول' }).click();
  await reviewer.getByRole('dialog').getByRole('button', { name: 'تأكيد القبول' }).click();
  await expect(reviewer.getByText('تم القبول')).toBeVisible();

  // The marketer stays on a page; the badge comes with the next 15 s poll.
  await page.goto('/');
  await expect(page.getByTestId('unread-badge')).toHaveText('1', { timeout: 20_000 });

  // --- 2. open it: the link message, copied and shared --------------------------------------------
  await page.getByRole('link', { name: /الإشعارات/ }).first().click();
  const row = page.getByRole('button').filter({ hasText: `#${r1.label}` });
  await expect(row).toContainText('تمت الموافقة على الطلب');
  await row.click();
  await expect(page).toHaveURL(new RegExp(`/requests/${r1.id}$`));
  const text = (await page.getByTestId('link-message-text').textContent())!;
  const lines = text.split('\n');
  expect(lines[0]).toBe(`طلب ربط جديد | رقم الطلب: #${r1.label}`);
  expect(lines).toContain(`البرج: ${TOWER_NAME} (${TOWER})`);
  expect(lines).toContain('الهاتف: 07800001301');
  expect(lines).toContain(`اليوزر: ${TOWER}-07800001301`);
  expect(lines).toContain('الفئة: NTFPLAN | التجريبي 20,000 د.ع | الثاني 35,000 د.ع');
  expect(lines).toContain('العنوان: حي الإشعارات، قرب نقطة الإشعارات');
  expect(lines).toContain('الموقع: https://maps.google.com/?q=33.3128,44.3615');
  expect(lines.at(-1)).toBe(`المسوّق: ${m.name}`);
  for (const secret of [N1, F1, '199912345678']) expect(text).not.toContain(secret);
  const name = lines[1].replace('الاسم: ', '');

  await page.getByRole('button', { name: 'نسخ رسالة الربط' }).click();
  await expect(page.getByTestId('link-message-status')).toHaveText('تم النسخ');
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(text);
  const share = page.getByRole('link', { name: 'مشاركة بالواتساب' });
  expect(await share.getAttribute('href')).toBe(`https://wa.me/?text=${encodeURIComponent(text)}`);
  await expect(page.getByTestId('unread-badge')).toHaveCount(0);

  // --- 3. R2 rejected, then deleted ----------------------------------------------------------------
  const r2 = await submitEdited(page, N2, F2, '07800001302');
  await reviewer.goto(`/admin/pending/${r2.id}`);
  await reviewer.getByRole('button', { name: 'رفض' }).click();
  await reviewer.getByRole('radio', { name: 'سبب آخر' }).check();
  await reviewer.getByRole('textbox', { name: /^سبب الرفض/ }).fill(NOTE);
  await reviewer.getByRole('button', { name: 'تأكيد الرفض' }).click();
  await expect(reviewer.getByText('تم رفض الطلب')).toBeVisible();

  await page.goto('/notifications');
  const rejected = page.getByRole('button').filter({ hasText: 'تم رفض الطلب' });
  await expect(rejected).toContainText(name);
  await expect(rejected).toContainText('السبب: سبب آخر');
  await expect(page.getByText(NOTE)).toHaveCount(0);

  await reviewer.getByRole('button', { name: 'حذف', exact: true }).click();
  const dialog = reviewer.getByRole('dialog');
  await dialog.getByRole('radio', { name: 'طلب مكرر' }).check();
  await dialog.getByRole('textbox', { name: /اكتب رقم الطلب للتأكيد/ }).fill(r2.label);
  await dialog.getByRole('button', { name: 'حذف نهائي' }).click();
  await expect(reviewer.getByRole('status')).toContainText('تم حذف بيانات هذا الطلب');
  await reviewer.close();

  await page.reload();
  const deleted = page.getByRole('button').filter({ hasText: 'تم حذف الطلب' });
  await expect(deleted).toContainText(`#${r2.label}`);
  await expect(deleted).toContainText('السبب: طلب مكرر');
  await expect(rejected).toContainText('محذوف');
  await expect(rejected).not.toContainText(name);
  await page.getByRole('button', { name: 'تعليم الكل كمقروء' }).click();
  await expect(page.getByTestId('unread-badge')).toHaveCount(0);
  await expect(page.locator('[data-unread="true"]')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('notifications.png'), fullPage: true });

  // --- 4. search ------------------------------------------------------------------------------------
  await page.goto('/requests');
  await search(page).fill(name.split(' ')[0]);
  const list = page.getByTestId('submitted-list');
  await expect(list.getByRole('link').filter({ hasText: r1.label })).toContainText('مقبول (بانتظار الربط)');
  await expect(list.getByRole('link').filter({ hasText: r2.label })).toHaveCount(0);
  await search(page).fill(r2.label);
  await expect(list.getByRole('link').filter({ hasText: r2.label })).toContainText('محذوف');
  await search(page).fill('0780 000 1302');
  await expect(page.getByText('لا توجد نتائج')).toBeVisible();

  const second = await (await browser.newContext({ ignoreHTTPSErrors: true })).newPage();
  await signIn(second, other.phone, NEW_PASSWORD);
  await expect(second).toHaveURL(/\/$/);
  await second.goto('/requests');
  await search(second).fill(r1.label);
  await expect(second.getByText('لا توجد نتائج')).toBeVisible();
  await second.close();

  // --- the notifications page at phone width -------------------------------------------------------
  const phone = await (await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 412, height: 915 } })).newPage();
  await signIn(phone, m.phone, NEW_PASSWORD);
  await expect(phone).toHaveURL(/\/$/);
  await phone.goto('/notifications');
  await expect(phone.getByRole('button').filter({ hasText: 'تم حذف الطلب' })).toBeVisible();
  const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await phone.goto(`/requests/${r1.id}`);
  await expect(phone.getByTestId('link-message')).toBeVisible();
  const messageOverflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(messageOverflow).toBeLessThanOrEqual(0);
  await phone.screenshot({ path: testInfo.outputPath('link-message-phone.png'), fullPage: true });
  await phone.close();
});
