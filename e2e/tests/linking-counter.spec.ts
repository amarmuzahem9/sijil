import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 013: «تم الربط», its undo and the marketer's counter, end to end (specs/013 T049).
 *
 * Like link-message-notifications.spec.ts, the request types its own synthetic national ID and
 * family number over the fake card's reading, so it waits for the admin and the fake person's
 * numbers are never stored; the main admin accepts it through the API. Phones, names and numbers
 * are synthetic.
 *
 * 1. A `link`-only admin finds it in «بانتظار الربط» and presses «تم الربط»: the marketer's bell
 *    and counter show 1, and the name is in the latest links.
 * 2. The admin undoes it with «ضُغط بالخطأ»: the counter goes back to 0 and the marketer reads
 *    «تم التراجع عن الربط» with the reason.
 * 3. A new link counts once again. The home is then checked at phone width.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة الربط';
const TOWER = 'LNK01';
const TOWER_NAME = 'برج الربط';
const PLAN = 'LNKPLAN';
const HOME = { latitude: 33.3128, longitude: 44.3615 };
const NID = '199977780001';
const FAMILY = '7778N0000000000001';
const PHONE = '07800001401';

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
async function submitEdited(page: Page): Promise<{ id: string; label: string }> {
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
  await typeField(page, 'national_id', NID);
  await page.getByTestId('adopt-current-national-id').click();
  await saved(page);
  await typeField(page, 'family_number', FAMILY);
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي الربط');
  await page.getByTestId('field-landmark').fill('قرب نقطة الربط');
  await page.getByTestId('field-landmark').blur();
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
  await typeField(page, 'phone_input', PHONE);

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

const counter = (page: Page) => page.getByTestId('linked-counter');

test('«تم الربط», its undo with a reason, and the marketer counter', async ({ page, request, browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of requests; phone width is checked below');
  test.setTimeout(600_000);
  const main = await ensureCatalog(request);
  const m = { name: 'مسوّق الربط', phone: '07700001401' };
  const linker = { name: 'أدمن الربط', phone: '07700001402', permissions: ['link'] };
  await apiCreateReadyAccount(request, main, 'marketers', m);
  await apiCreateReadyAccount(request, main, 'admins', linker);

  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation(HOME);
  await signIn(page, m.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await expect(counter(page)).toHaveText('تم الربط هذا الشهر: 0');

  const r = await submitEdited(page);
  const accepted = await request.post(`/api/admin/requests/${r.id}/accept`, { headers: main, data: {} });
  expect(accepted.status()).toBe(200);
  // Acceptance is 012's notification; read it so the badge below counts the link only.
  await page.goto('/notifications');
  await page.getByRole('button', { name: 'تعليم الكل كمقروء' }).click();
  await expect(page.getByTestId('unread-badge')).toHaveCount(0);

  // --- 1. the link ---------------------------------------------------------------------------------
  const admin = await adminPage(browser, linker.phone);
  await admin.goto('/admin/awaiting-link');
  await admin.getByRole('searchbox', { name: 'بحث برقم الطلب أو الهاتف أو اليوزر' }).fill(r.label);
  const row = admin.getByTestId('link-row').filter({ hasText: r.label });
  await expect(row).toContainText(`${TOWER}-${PHONE}`);
  await expect(row).toContainText(`${TOWER_NAME} (${TOWER})`);
  for (const secret of [NID, FAMILY]) await expect(admin.getByText(secret)).toHaveCount(0);
  await row.getByRole('button', { name: 'تم الربط' }).click();
  await admin.getByRole('dialog').getByRole('button', { name: 'تأكيد الربط' }).click();
  await expect(admin.getByText(`تم ربط ${r.label}`)).toBeVisible();
  await expect(admin.getByTestId('link-row')).toHaveCount(0);

  await page.goto('/');
  await expect(page.getByTestId('unread-badge')).toHaveText('1', { timeout: 20_000 });
  await expect(counter(page)).toHaveText('تم الربط هذا الشهر: 1');
  await expect(page.getByTestId('recent-links')).toContainText(`#${r.label}`);
  await page.goto(`/requests/${r.id}`);
  await expect(page.getByTestId('request-status')).toHaveText('تم الربط');
  await expect(page.getByText('تاريخ الربط')).toBeVisible();
  await expect(page.getByTestId('link-message')).toBeVisible();

  // --- 2. the undo ---------------------------------------------------------------------------------
  await admin.getByRole('tab', { name: 'المربوطة مؤخراً' }).click();
  const linkedRow = admin.getByTestId('link-row').filter({ hasText: r.label });
  await expect(linkedRow).toContainText(`ربطه: ${linker.name}`);
  await linkedRow.getByRole('button', { name: 'التراجع عن الربط' }).click();
  const dialog = admin.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: 'تأكيد التراجع' })).toBeDisabled();
  await expect(dialog.getByRole('textbox')).toHaveCount(0);
  await dialog.getByRole('radio', { name: 'ضُغط بالخطأ' }).check();
  await dialog.getByRole('button', { name: 'تأكيد التراجع' }).click();
  await expect(admin.getByText(`تم التراجع عن ربط ${r.label}`)).toBeVisible();

  await page.goto('/');
  await expect(counter(page)).toHaveText('تم الربط هذا الشهر: 0');
  await expect(page.getByText('لا يوجد مشتركون مربوطون هذا الشهر')).toBeVisible();
  await page.goto('/notifications');
  const undone = page.getByRole('button').filter({ hasText: 'تم التراجع عن الربط' });
  await expect(undone).toContainText(`#${r.label}`);
  await expect(undone).toContainText('السبب: ضُغط بالخطأ');

  // --- 3. linked again: counted once ---------------------------------------------------------------
  await admin.getByRole('tab', { name: 'بانتظار الربط' }).click();
  await admin.getByTestId('link-row').filter({ hasText: r.label }).getByRole('button', { name: 'تم الربط' }).click();
  await admin.getByRole('dialog').getByRole('button', { name: 'تأكيد الربط' }).click();
  await expect(admin.getByText(`تم ربط ${r.label}`)).toBeVisible();
  await admin.close();

  await page.goto('/');
  await expect(counter(page)).toHaveText('تم الربط هذا الشهر: 1');
  await page.goto('/requests?tab=linked');
  await expect(page.getByTestId('submitted-list')).toContainText('تاريخ الربط');

  // The home at phone width: no horizontal scroll.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(counter(page)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await page.screenshot({ path: testInfo.outputPath('linked-home.png'), fullPage: true });
});
