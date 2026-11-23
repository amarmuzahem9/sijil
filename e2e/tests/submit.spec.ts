import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 008: the check and decision at «إرسال» (specs/008 quickstart 1–2, tasks T047).
 *
 * The fake card reader fills the card (OCR_MODE=fake) and the in-memory OTP sender uses the fixed
 * code (OTP_FAKE_CODE=246810): no WhatsApp message, no real card. Every fake card carries the
 * same national ID, so only one project submits it: a second approval of the same person would be
 * refused by design (§6.1 row 2). Phones and names are synthetic.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة الإرسال';
const TOWER = 'SUB01';
const PLAN = 'SUBPLAN';
const PHONE = '07800000801';
const HOME = { latitude: 33.3128, longitude: 44.3615 };

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  await request.post(`${base}/towers`, {
    headers: main,
    data: { code: TOWER, name: 'برج الإرسال', area_id: area.id },
  });
  await request.post(`${base}/plans`, {
    headers: main,
    data: { name: PLAN, trial_price: 20000, second_price: 35000 },
  });
  return main;
}

async function marketer(request: APIRequestContext, main: Record<string, string>, i: number) {
  const m = { name: `مسوّق الإرسال ${i}`, phone: `0770000080${i}` };
  await apiCreateReadyAccount(request, main, 'marketers', m);
  return m;
}

async function choose(page: Page, label: string, option: string | RegExp) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

const saved = (page: Page) => expect(page.getByTestId('save-badge')).toHaveText('محفوظ');

async function chooseSubscription(page: Page) {
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  // The menu's invisible backdrop must be gone, or the next tap only closes it.
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
}

/** Type the phone and let it save before «تحقّق», as a marketer does. */
async function typePhone(page: Page, phone: string) {
  await page.getByTestId('field-phone_input').fill(phone);
  await page.getByTestId('field-phone_input').blur();
  await saved(page);
}

test('a clean draft is approved with its number and username; the same phone gets no code', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one approval of the fake card is enough');
  test.setTimeout(180_000);
  const main = await ensureCatalog(request);
  const first = await marketer(request, main, 1);
  const second = await marketer(request, main, 2);

  // --- the first marketer: a full, verified draft --------------------------------------------
  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation(HOME);
  await signIn(page, first.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await page.goto('/drafts/new');

  for (const [side, scenario] of [
    ['front', 'clear_front'],
    ['back', 'clear_back'],
  ] as const) {
    await page.getByTestId(`image-${side}-gallery`).setInputFiles(await scenarioPhoto(page, scenario));
    await expect(page.getByTestId(`image-${side}-thumbnail`)).toBeVisible({ timeout: 30_000 });
  }
  await expect(page.getByTestId('field-first_name')).toHaveValue('مشترك', { timeout: 30_000 });
  await expect(page.getByTestId('field-national_id')).toHaveValue('199912345678');

  await page.getByTestId('field-great_grandfather_name').fill('نموذج');
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي تجريبي');
  await page.getByTestId('field-landmark').fill('قرب نقطة تجريبية');
  await page.getByTestId('field-landmark').blur();
  await chooseSubscription(page);

  const send = page.getByTestId('submit-button');
  await expect(send).toBeDisabled();
  await expect(page.getByText('أكمل النواقص ليتفعّل الإرسال')).toBeVisible();

  await typePhone(page, PHONE);
  await page.getByTestId('otp-send').click();
  await expect(page.getByTestId('otp-digit-0')).toBeFocused();
  await page.keyboard.type(FAKE_CODE);
  await expect(page.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await expect(page.getByTestId('missing-summary')).toContainText('كل الحقول مكتملة');

  // --- «إرسال» → «تمت الموافقة» ----------------------------------------------------------------
  await expect(send).toBeEnabled();
  await send.click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
  await expect(page.getByText('تمت الموافقة')).toBeVisible();
  await expect(page.getByText(/^#T3C-1\d{3,}$/)).toBeVisible();
  await expect(page.getByTestId('request-username')).toHaveText(`${TOWER}-${PHONE}`);
  await expect(page.getByTestId('request-status')).toHaveText('مقبول');
  await page.screenshot({ path: testInfo.outputPath('approved.png'), fullPage: true });

  // The draft became a request: «مقبولة» lists it, «مسودات» no longer does.
  await page.goto('/requests?tab=approved');
  await expect(page.getByTestId('submitted-list')).toContainText('مشترك');
  await page.goto('/requests?tab=drafts');
  await expect(page.getByText('مشترك تجريبي')).toHaveCount(0);

  // --- the second marketer, same phone: «تحقّق» sends nothing --------------------------------
  const other = await browser.newContext();
  const b = await other.newPage();
  await signIn(b, second.phone, NEW_PASSWORD);
  await expect(b).toHaveURL(/\/$/);
  await b.goto('/drafts/new');
  await chooseSubscription(b);
  await typePhone(b, '+964 780 000 0801');
  await b.getByTestId('otp-send').click();
  await expect(b.getByTestId('otp-error')).toHaveText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
  // v1.10 (specs/009 US2): the phone's owner can return, or the marketer contacts the admin.
  await expect(b.getByTestId('return-offer')).toBeVisible();
  await expect(b.getByRole('button', { name: 'طلب العودة للخدمة' })).toBeVisible();
  // No administration number in the e2e settings: the contact button is disabled.
  await expect(b.getByRole('button', { name: 'الاتصال بالإدارة' })).toBeDisabled();
  await expect(b.getByTestId('otp-digit-0')).toHaveCount(0);
  await expect(b.getByTestId('missing-phone_used')).toBeVisible();
  await other.close();
});
