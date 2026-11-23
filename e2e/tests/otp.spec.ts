import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

/**
 * Feature 007: phone verification by WhatsApp OTP (specs/007 quickstart, tasks T026).
 *
 * The e2e stack runs the in-memory sender with a fixed code (OTP_MODE=fake,
 * OTP_FAKE_CODE=246810): no WhatsApp message is sent and no code ever appears in a response.
 * Phones and names are synthetic.
 */

const FAKE_CODE = '246810';
const AREA = 'منطقة التحقق';
const TOWER = 'OTP01';
const PLAN_A = 'OTPBASIC';
const PLAN_B = 'OTPEXTRA'; // not 'PLUS': settings-acceptance filters rows by that text
const PROJECT_INDEX: Record<string, number> = { 'desktop-chrome': 0, 'pixel-7': 1, 'iphone-14': 2 };

async function ensureCatalog(request: APIRequestContext) {
  const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
  const base = '/api/admin/settings';
  const areas = (await (await request.get(`${base}/areas`, { headers: main })).json()).items;
  let area = areas.find((a: { name: string }) => a.name === AREA);
  if (!area) {
    area = await (await request.post(`${base}/areas`, { headers: main, data: { name: AREA } })).json();
  }
  const towers = (await (await request.get(`${base}/towers`, { headers: main })).json()).items;
  if (!towers.some((t: { code: string }) => t.code === TOWER)) {
    await request.post(`${base}/towers`, {
      headers: main,
      data: { code: TOWER, name: 'برج التحقق', area_id: area.id },
    });
  }
  const plans = (await (await request.get(`${base}/plans`, { headers: main })).json()).items;
  for (const [name, trial, second] of [
    [PLAN_A, 15000, 25000],
    [PLAN_B, 20000, 35000],
  ] as const) {
    if (!plans.some((p: { name: string }) => p.name === name)) {
      await request.post(`${base}/plans`, {
        headers: main,
        data: { name, trial_price: trial, second_price: second },
      });
    }
  }
  return main;
}

async function marketer(request: APIRequestContext, main: Record<string, string>, i: number) {
  const m = { name: `مسوّق التحقق ${i}`, phone: `0770000060${i}` };
  const login = await request.post('/api/auth/login', {
    data: { phone: m.phone, password: NEW_PASSWORD },
  });
  if (login.status() !== 200) await apiCreateReadyAccount(request, main, 'marketers', m);
  return m;
}

async function choose(page: Page, label: string, option: string | RegExp) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

const saved = (page: Page) => expect(page.getByTestId('save-badge')).toHaveText('محفوظ');
const digit = (page: Page, i: number) => page.getByTestId(`otp-digit-${i}`);

/** Type into the six boxes the way a marketer does: the first box is focused, focus moves on. */
async function typeCode(page: Page, code: string) {
  await expect(digit(page, 0)).toBeFocused();
  await page.keyboard.type(code);
}

test('send, verify, a category change cancels, verify again', async ({ page, request }, testInfo) => {
  test.setTimeout(150_000);
  const i = PROJECT_INDEX[testInfo.project.name] ?? 3;
  const main = await ensureCatalog(request);
  const m = await marketer(request, main, i);
  // A different synthetic subscriber phone per project: the hourly limit counts per phone.
  const subscriberPhone = `0780000070${i}`;

  await signIn(page, m.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await page.goto('/drafts/new');

  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await choose(page, 'الفئة', new RegExp(PLAN_A));
  await saved(page);

  const send = page.getByTestId('otp-send');
  await expect(send).toBeDisabled(); // empty phone
  await page.getByTestId('field-phone_input').fill(subscriberPhone);
  await expect(page.getByTestId('missing-phone_verification')).toBeVisible();

  // «تحقّق» saves the typed phone first, then sends.
  await send.click();
  await expect(page.getByTestId('otp-sent-to')).toHaveText(
    `أُرسل رمز التحقق عبر الواتساب إلى ${subscriberPhone}`,
  );
  await expect(page.getByTestId('otp-send')).toContainText('إعادة الإرسال بعد');
  await expect(page.getByTestId('otp-send')).toBeDisabled();

  // Six boxes, left to right on the Arabic page, inside the screen width (phone sizes too).
  const viewport = page.viewportSize()!;
  const first = (await digit(page, 0).boundingBox())!;
  const last = (await digit(page, 5).boundingBox())!;
  expect(first.x).toBeLessThan(last.x);
  expect(last.x + last.width).toBeLessThanOrEqual(viewport.width);
  await page.getByTestId('otp-code').screenshot({ path: testInfo.outputPath('otp-boxes.png') });

  // A wrong code first: the sixth digit submits by itself; red, then the boxes clear.
  await typeCode(page, '000000');
  await expect(page.getByTestId('otp-error')).toHaveText('الرمز غير صحيح، بقيت محاولتان');
  await expect(digit(page, 0)).toHaveValue('');
  await expect(page.getByTestId('otp-code')).toHaveAttribute('data-phase', 'idle');

  // The right code, typed with Arabic digits: each box shows its Latin digit, then green, then ✓.
  await typeCode(page, '٢٤٦٨١٠');
  await expect(page.getByTestId('otp-code')).toHaveAttribute('data-phase', 'success');
  await expect(digit(page, 5)).toHaveValue('0');
  await page.getByTestId('otp-code').screenshot({ path: testInfo.outputPath('otp-boxes-ok.png') });
  await expect(page.getByTestId('otp-verified')).toHaveText('تم التحقق');
  await expect(page.getByTestId('missing-phone_verification')).toHaveCount(0);

  // The acceptance criterion: changing the category cancels the verification.
  await choose(page, 'الفئة', new RegExp(PLAN_B));
  await saved(page);
  await expect(page.getByTestId('otp-needs-reverify')).toHaveText('يحتاج تحقق جديد');
  await expect(page.getByTestId('otp-verified')).toHaveCount(0);
  await expect(page.getByTestId('missing-phone_verification')).toBeVisible();

  // A reload keeps the server state (nothing is kept on the device).
  await page.reload();
  await expect(page.getByTestId('otp-needs-reverify')).toBeVisible();

  // Verify again after the 60 s resend wait from the first send.
  await expect(page.getByTestId('otp-send')).toHaveText('تحقّق', { timeout: 70_000 });
  await page.getByTestId('otp-send').click();
  // Paste the whole code into the first box: it spreads over the six and submits.
  await expect(digit(page, 0)).toBeFocused();
  await page.evaluate((code) => {
    const data = new DataTransfer();
    data.setData('text', code);
    document.activeElement!.dispatchEvent(
      new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }),
    );
  }, FAKE_CODE);
  await expect(page.getByTestId('otp-verified')).toHaveText('تم التحقق');
});
