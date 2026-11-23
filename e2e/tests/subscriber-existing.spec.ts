import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto } from './helpers/cardImages';

/**
 * Feature 009: «طلب العودة للخدمة» by identity and by phone, to the result screen
 * (specs/009 quickstart 1–2, tasks T046).
 *
 * The fake card reader (OCR_MODE=fake) always gives the same person and the in-memory OTP sender
 * the fixed code. The file runs after submit.spec.ts (files run in name order), which approves
 * that person with SUBMIT_PHONE; run alone, the first step approves them here instead. Either way
 * the person exists with a known phone before the return. Phones and names are synthetic.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة العودة';
const TOWER = 'RET01';
const PLAN = 'RETPLAN';
const SUBMIT_PHONE = '07800000801'; // submit.spec.ts
const OWN_PHONE = '07800000951';
const HOME = { latitude: 33.3128, longitude: 44.3615 };

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  await request.post(`${base}/towers`, {
    headers: main,
    data: { code: TOWER, name: 'برج العودة', area_id: area.id },
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

/** A new draft with the fake card read and everything but the phone filled. */
async function cardDraft(page: Page) {
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
  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await page.getByTestId('field-address').fill('حي العودة');
  await page.getByTestId('field-landmark').fill('قرب نقطة العودة');
  await page.getByTestId('field-landmark').blur();
  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN));
  await saved(page);
  await expect(page.locator('.MuiBackdrop-root')).toHaveCount(0);
}

async function typePhone(page: Page, phone: string) {
  await page.getByTestId('field-phone_input').fill(phone);
  await page.getByTestId('field-phone_input').blur();
  await saved(page);
}

async function verifyAndSend(page: Page) {
  await page.getByTestId('otp-send').click();
  await expect(page.getByTestId('otp-digit-0')).toBeFocused();
  await page.keyboard.type(FAKE_CODE);
  await expect(page.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await expect(page.getByTestId('submit-button')).toBeEnabled();
  await page.getByTestId('submit-button').click();
  await expect(page).toHaveURL(/\/requests\/\d+$/);
}

/** The person's phone in the records: submit.spec's, or approve them here first. */
async function existingPhone(page: Page): Promise<string> {
  await cardDraft(page);
  // The check arrives with the saves; give it a moment before deciding. The draft is left as a
  // draft: it is not a subscriber and does not count in the checks.
  const exists = await page
    .getByTestId('return-offer')
    .waitFor({ timeout: 5_000 })
    .then(() => true)
    .catch(() => false);
  if (exists) return SUBMIT_PHONE;
  await typePhone(page, OWN_PHONE);
  await verifyAndSend(page);
  await expect(page.getByText('تمت الموافقة')).toBeVisible();
  return OWN_PHONE;
}

test('return to service by identity, then by phone, each to «بانتظار موافقة المسؤول»', async ({
  page,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one person and one pending return');
  test.setTimeout(300_000);
  const main = await ensureCatalog(request);
  const m = { name: 'مسوّق العودة', phone: '07700000951' };
  await apiCreateReadyAccount(request, main, 'marketers', m);

  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation(HOME);
  await signIn(page, m.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  const oldPhone = await existingPhone(page);

  // --- by identity: the same national ID and family number, with a new phone ----------------
  await cardDraft(page);
  const offer = page.getByTestId('return-offer');
  await expect(offer).toContainText('المشترك لديه اشتراك سابق');
  await expect(offer).not.toContainText(oldPhone); // nothing about the other record
  await page.getByRole('button', { name: 'طلب العودة للخدمة' }).first().click();
  await expect(page.getByTestId('return-chosen')).toContainText('تم اختيار طلب العودة للخدمة');
  await typePhone(page, '07800000952');
  await verifyAndSend(page);
  await expect(page.getByText('بانتظار موافقة المسؤول')).toBeVisible();
  await expect(page.getByText('اسم المستخدم')).toBeVisible();
  await expect(page.getByText('بانتظار الموافقة')).toBeVisible();
  await expect(page.getByRole('button', { name: 'نسخ التفاصيل' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('return-identity.png'), fullPage: true });

  // --- by phone: another family number on the card (not the same person), the old phone -------
  // (Not the national ID: a typed one that differs from the back of the card asks «تأكد».)
  await cardDraft(page);
  await page.getByTestId('field-family_number').fill('9999Z0000000000952');
  await page.getByTestId('field-family_number').blur();
  await saved(page);
  await typePhone(page, oldPhone);
  await page.getByTestId('otp-send').click();
  await expect(page.getByTestId('otp-error')).toHaveText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
  const phoneOffer = page.getByTestId('return-offer');
  await expect(phoneOffer).toContainText('المشترك موجود سابقاً، هل يود العودة للخدمة؟');
  await expect(page.getByRole('button', { name: 'الاتصال بالإدارة' })).toBeDisabled();
  await phoneOffer.getByRole('button', { name: 'طلب العودة للخدمة' }).click();
  await expect(page.getByTestId('return-chosen')).toBeVisible();
  await verifyAndSend(page);
  await expect(page.getByText('بانتظار موافقة المسؤول')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('return-phone.png'), fullPage: true });
});
