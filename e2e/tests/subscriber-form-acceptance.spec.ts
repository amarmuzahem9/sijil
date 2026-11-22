import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import {
  apiCreateReadyAccount,
  apiSignIn,
  env,
  MAIN_ADMIN_PASSWORD,
  NEW_PASSWORD,
  signIn,
} from './helpers';

/**
 * Feature 005 acceptance (specs/005 quickstart A, B, D, E, F, H, I, J; tasks T039, T051).
 * A marketer fills half the form on one phone, opens it on another and finds everything,
 * images included. All data is synthetic: generated rectangles with the text «بطاقة تجريبية»,
 * made-up names and numbers.
 */

const AREA = 'منطقة الاستمارة';
const TOWER = 'FRM01';
const PLAN = 'FORMTEST';
const HOME = { latitude: 33.3128, longitude: 44.3615 };

/** Synthetic names for the nine fields of the ministry form (system.md §5.1 v1.5). */
const NAMES: Record<string, string> = {
  first_name: 'مشترك',
  father_name: 'تجريبي',
  grandfather_name: 'اختبار',
  great_grandfather_name: 'نموذج',
  surname: 'الوهمي',
  mother_first_name: 'أم',
  mother_second_name: 'تجريبية',
  mother_third_name: 'ثالث',
  mother_surname: 'لقب',
};
const FULL_NAME = 'مشترك تجريبي اختبار نموذج الوهمي';

const PROJECT_INDEX: Record<string, number> = { 'desktop-chrome': 0, 'pixel-7': 1, 'iphone-14': 2 };

function marketerFor(project: string, n = 0) {
  const i = PROJECT_INDEX[project] ?? 3;
  return { name: `مسوّق الاستمارة ${i}${n}`, phone: `077000001${6 + n}${i}` };
}

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
    const r = await request.post(`${base}/towers`, {
      headers: main,
      data: { code: TOWER, name: 'برج الاستمارة', area_id: area.id },
    });
    expect(r.status()).toBe(201);
  }
  const plans = (await (await request.get(`${base}/plans`, { headers: main })).json()).items;
  if (!plans.some((p: { name: string }) => p.name === PLAN)) {
    const r = await request.post(`${base}/plans`, {
      headers: main,
      data: { name: PLAN, trial_price: 20000, second_price: 35000 },
    });
    expect(r.status()).toBe(201);
  }
  return main;
}

async function ensureMarketer(request: APIRequestContext, main: Record<string, string>, m: {
  name: string;
  phone: string;
}) {
  const login = await request.post('/api/auth/login', {
    data: { phone: m.phone, password: NEW_PASSWORD },
  });
  if (login.status() === 200) return;
  await apiCreateReadyAccount(request, main, 'marketers', m);
}

/** A synthetic card photo drawn in the page (JPEG), returned as bytes for setInputFiles. */
async function syntheticPhoto(page: Page, width: number, height: number, label: string) {
  const base64 = await page.evaluate(
    async ({ width, height, label }) => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = '#2f6db5';
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = '#ffffff';
      ctx.font = `${Math.round(height / 10)}px sans-serif`;
      ctx.fillText(`بطاقة تجريبية — ${label}`, width / 10, height / 2);
      // Noise so the JPEG is a realistic size rather than a flat colour.
      for (let i = 0; i < 4000; i++) {
        ctx.fillStyle = `hsl(${(i * 37) % 360} 60% 50%)`;
        ctx.fillRect((i * 97) % width, (i * 53) % height, 12, 12);
      }
      const blob: Blob = await new Promise((r) => canvas.toBlob((b) => r(b!), 'image/jpeg', 0.92));
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let s = '';
      for (const b of bytes) s += String.fromCharCode(b);
      return btoa(s);
    },
    { width, height, label },
  );
  return { name: `${label}.jpg`, mimeType: 'image/jpeg', buffer: Buffer.from(base64, 'base64') };
}

async function newPhoneContext(browser: Browser, testInfo: { project: { use: Record<string, unknown> } }) {
  const use = testInfo.project.use;
  return browser.newContext({
    baseURL: use.baseURL as string,
    ignoreHTTPSErrors: true,
    viewport: use.viewport as { width: number; height: number } | undefined,
    userAgent: use.userAgent as string | undefined,
    isMobile: use.isMobile as boolean | undefined,
    hasTouch: use.hasTouch as boolean | undefined,
    deviceScaleFactor: use.deviceScaleFactor as number | undefined,
    locale: 'ar-IQ',
    timezoneId: 'Asia/Baghdad',
  });
}

async function choose(page: Page, label: string, option: string | RegExp) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

const saved = (page: Page) => expect(page.getByTestId('save-badge')).toHaveText('محفوظ');

test.describe.configure({ mode: 'serial' });

test('A, B, D: half a form on one phone, everything on the other (SC-001)', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.setTimeout(180_000);
  const main = await ensureCatalog(request);
  const marketer = marketerFor(testInfo.project.name);
  await ensureMarketer(request, main, marketer);

  // --- phone A ---------------------------------------------------------------------------------
  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation(HOME);
  await signIn(page, marketer.phone, NEW_PASSWORD);
  await page.getByRole('link', { name: 'إضافة مشترك جديد' }).click();
  await expect(page).toHaveURL(/\/drafts\/new$/);

  // Two separate buttons per slot; only «تصوير» opens the camera (owner requirement).
  for (const side of ['front', 'back']) {
    const slot = page.getByTestId(`image-slot-${side}`);
    await expect(slot.getByText('تصوير', { exact: true })).toBeVisible();
    await expect(slot.getByText('من المعرض', { exact: true })).toBeVisible();
    await expect(page.getByTestId(`image-${side}-camera`)).toHaveAttribute('capture', 'environment');
    await expect(page.getByTestId(`image-${side}-gallery`)).not.toHaveAttribute('capture', /.*/);
  }

  // D: a 4000×3000 photo is compressed on the device before upload.
  await page
    .getByTestId('image-front-gallery')
    .setInputFiles(await syntheticPhoto(page, 4000, 3000, 'وجه'));
  await expect(page.getByTestId('image-front-thumbnail')).toBeVisible({ timeout: 30_000 });
  await expect(page).toHaveURL(/\/drafts\/[0-9a-f-]{36}$/);
  const draftId = page.url().split('/').pop()!;
  await page
    .getByTestId('image-back-camera')
    .setInputFiles(await syntheticPhoto(page, 1200, 800, 'ظهر'));
  await expect(page.getByTestId('image-back-thumbnail')).toBeVisible({ timeout: 30_000 });

  for (const [field, value] of Object.entries(NAMES)) {
    await page.getByTestId(`field-${field}`).fill(value);
  }
  await expect(page.getByText('غير موجود على البطاقة، اسأل المشترك')).toBeVisible();
  await page.getByTestId('field-national_id').fill('199012345678');
  await page.getByTestId('field-family_number').fill('A1B2C3');
  await page.getByTestId('field-family_number').blur();

  await page.getByRole('button', { name: 'استخدم موقعي الحالي' }).click();
  await expect(page.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  // J: no map key in the e2e stack; GPS still sets the pin.
  await expect(page.getByTestId('map-unavailable')).toHaveText('الخريطة غير متوفرة حالياً');

  await choose(page, 'المنطقة', AREA);
  await choose(page, 'البرج', new RegExp(TOWER));
  await saved(page);

  // SC-003: the stored front image is at most 1600 px and under 700 KB.
  const own = await apiSignIn(request, marketer.phone, NEW_PASSWORD);
  const stored = await (
    await request.get(`/api/drafts/${draftId}`, { headers: { ...own, 'X-Client-Id': crypto.randomUUID() } })
  ).json();
  expect(Math.max(stored.images.front.width, stored.images.front.height)).toBe(1600);
  expect(stored.images.front.size_bytes).toBeLessThan(700 * 1024);
  expect(stored.tower_code).toBe(TOWER);

  // --- phone B, same account ----------------------------------------------------------------------
  const phoneB = await newPhoneContext(browser, testInfo);
  const b = await phoneB.newPage();
  await signIn(b, marketer.phone, NEW_PASSWORD);
  await b.getByRole('link', { name: 'الطلبات' }).first().click();
  await expect(b.getByRole('tab', { name: 'مسودات', selected: true })).toBeVisible();
  await b.getByTestId('draft-card').filter({ hasText: FULL_NAME }).getByRole('link').click();
  await expect(b).toHaveURL(new RegExp(`/drafts/${draftId}$`));

  for (const [field, value] of Object.entries(NAMES)) {
    await expect(b.getByTestId(`field-${field}`)).toHaveValue(value);
  }
  await expect(b.getByTestId('field-national_id')).toHaveValue('199012345678');
  await expect(b.getByTestId('field-family_number')).toHaveValue('A1B2C3');
  await expect(b.getByTestId('location-coords')).toHaveText('33.312800, 44.361500');
  await expect(b.getByRole('combobox', { name: 'المنطقة' })).toHaveText(AREA);
  await expect(b.getByRole('combobox', { name: 'البرج' })).toContainText(TOWER);
  for (const side of ['front', 'back']) {
    const img = b.getByTestId(`image-${side}-thumbnail`);
    await expect(img).toHaveAttribute('src', /^blob:/);
    await expect
      .poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth))
      .toBeGreaterThan(0);
  }

  // B: B changes the address; A is told within 30 s and loads the newer version.
  await b.getByTestId('field-address').fill('عنوان من الجهاز الثاني');
  await b.getByTestId('field-address').blur();
  await saved(b);
  await expect(page.getByTestId('conflict-banner')).toContainText('تغيّرت المسودة من جهاز آخر', {
    timeout: 35_000,
  });
  await page.getByRole('button', { name: 'تحميل الأحدث' }).click();
  await expect(page.getByTestId('field-address')).toHaveValue('عنوان من الجهاز الثاني');
  await expect(page.getByTestId('conflict-banner')).toHaveCount(0);

  // Two tabs of the same session behave like two devices (analysis U1).
  const tab2 = await page.context().newPage();
  await tab2.goto(`/drafts/${draftId}`);
  await tab2.getByTestId('field-landmark').fill('قرب نقطة تجريبية');
  await tab2.getByTestId('field-landmark').blur();
  await saved(tab2);
  await expect(page.getByTestId('conflict-banner')).toBeVisible({ timeout: 35_000 });

  await phoneB.close();
});

test('E, F: field checks, «النواقص» and the disabled «إرسال»', async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one project is enough for the checks');
  const main = await ensureCatalog(request);
  const marketer = marketerFor(testInfo.project.name);
  await ensureMarketer(request, main, marketer);
  await signIn(page, marketer.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await page.goto('/drafts/new');

  const summary = page.getByTestId('missing-summary');
  // 18 items of 005 + the five required back-of-card fields (006, system.md v1.8).
  await expect(summary).toContainText('النواقص (23)');
  await expect(page.getByTestId('missing-expiry_date')).toContainText('تاريخ النفاذ');

  // Names: a digit is refused at once and never saved; each missing name is listed by name.
  await page.getByTestId('field-first_name').fill('علي2');
  await expect(page.getByText('الاسم أحرف عربية فقط')).toBeVisible();
  await expect(page.getByTestId('missing-great_grandfather_name')).toContainText('الاسم الرابع');
  await page.getByTestId('field-first_name').fill('علي');
  await expect(page.getByText('الاسم أحرف عربية فقط')).toHaveCount(0);
  await expect(page.getByTestId('missing-first_name')).toHaveCount(0);
  await expect(page.getByTestId('missing-mother_third_name')).toHaveCount(0); // optional

  await page.getByTestId('field-national_id').fill('١٢٣٤٥٦٧٨٩٠١');
  await page.getByTestId('field-national_id').blur();
  await expect(page.getByText('الرقم الوطني 12 رقماً').first()).toBeVisible();
  await expect(page.getByTestId('missing-national_id')).toContainText('الرقم الوطني 12 رقماً');

  await page.getByTestId('field-phone_input').fill('+964 780 123 4567');
  await page.getByTestId('field-phone_input').blur();
  await expect(page.getByText('سيُحفظ كـ 07801234567')).toBeVisible();
  await saved(page);
  await expect(page.getByTestId('missing-phone')).toHaveCount(0);

  // A summary link takes the marketer to the field.
  await page.getByTestId('missing-family_number').getByRole('button').click();
  await expect(page.getByTestId('field-family_number')).toBeFocused();

  const send = page.getByRole('button', { name: 'إرسال', exact: true });
  await expect(send).toBeDisabled();
  await expect(page.getByText('الإرسال يتفعّل بعد إضافة التحقق من الهاتف')).toBeVisible();
});

test('H, I: deleting a draft, and another marketer cannot open it', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one project is enough');
  const main = await ensureCatalog(request);
  const owner = marketerFor(testInfo.project.name);
  const other = marketerFor(testInfo.project.name, 1);
  await ensureMarketer(request, main, owner);
  await ensureMarketer(request, main, other);

  await signIn(page, owner.phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await page.goto('/drafts/new');
  await page.getByTestId('field-first_name').fill('مسودة');
  await page.getByTestId('field-father_name').fill('للحذف');
  await page.getByTestId('field-father_name').blur();
  await saved(page);
  const draftUrl = new URL(page.url()).pathname;

  // I: another marketer sees «المسودة غير موجودة».
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, baseURL: testInfo.project.use.baseURL });
  const otherPage = await ctx.newPage();
  await signIn(otherPage, other.phone, NEW_PASSWORD);
  await expect(otherPage).toHaveURL(/\/$/);
  await otherPage.goto(draftUrl);
  await expect(otherPage.getByText('المسودة غير موجودة')).toBeVisible();
  await ctx.close();

  // H: the owner deletes it from «الطلبات ← مسودات».
  await page.goto('/requests?tab=drafts');
  const card = page.getByTestId('draft-card').filter({ hasText: 'مسودة للحذف' });
  await card.getByRole('button', { name: 'حذف' }).click();
  await expect(page.getByRole('dialog')).toContainText('حذف المسودة نهائياً؟');
  await page.getByRole('dialog').getByRole('button', { name: 'حذف' }).click();
  await expect(card).toHaveCount(0);

  // «سجل العمليات» shows «حذف مسودة» without the subscriber's name.
  const audit = await request.get('/api/admin/audit?limit=20', { headers: main });
  const entries = (await audit.json()).items as { action: string; before: unknown }[];
  const entry = entries.find((e) => e.action === 'draft.deleted');
  expect(entry).toBeTruthy();
  expect(JSON.stringify(entry)).not.toContain('مسودة للحذف');
});
