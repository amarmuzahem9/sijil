import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import { apiCreateReadyAccount, apiSignIn, env, MAIN_ADMIN_PASSWORD, NEW_PASSWORD, signIn } from './helpers';
import { scenarioPhoto, type CardScenario } from './helpers/cardImages';

/**
 * Feature 006: reading the national card (specs/006 quickstart A–N).
 *
 * The e2e stack runs the fake reader (OCR_MODE=fake): each synthetic photo's colour selects a
 * scenario (api/app/services/card_reader_fake_data.py). The photos show only «بطاقة تجريبية»;
 * every name and number is made up.
 */

const PROJECT_INDEX: Record<string, number> = { 'desktop-chrome': 0, 'pixel-7': 1, 'iphone-14': 2 };

const READ = {
  first_name: 'مشترك',
  father_name: 'تجريبي',
  grandfather_name: 'اختبار',
  surname: 'الوهمي',
  mother_first_name: 'أم',
  mother_second_name: 'تجريبية',
  national_id: '199912345678',
  family_number: '1064L00M1234567890',
} as const;

const BACK = {
  birth_date: '1999-01-01',
  birth_place: 'مدينة-تجريبية',
  issue_date: '2020-01-02',
  expiry_date: '2030-01-01',
  issuing_authority: 'مديرية الجنسية والمعلومات المدنية',
} as const;

async function marketer(request: APIRequestContext, project: string) {
  const i = PROJECT_INDEX[project] ?? 3;
  const m = { name: `مسوّق القراءة ${i}`, phone: `0770000050${i}` };
  const login = await request.post('/api/auth/login', {
    data: { phone: m.phone, password: NEW_PASSWORD },
  });
  if (login.status() !== 200) {
    const main = await apiSignIn(request, env('SUPERADMIN_PHONE'), MAIN_ADMIN_PASSWORD);
    await apiCreateReadyAccount(request, main, 'marketers', m);
  }
  return m;
}

async function openNewForm(page: Page, phone: string) {
  await signIn(page, phone, NEW_PASSWORD);
  await expect(page).toHaveURL(/\/$/);
  await page.goto('/drafts/new');
}

async function uploadSide(page: Page, side: 'front' | 'back', scenario: CardScenario) {
  await page.getByTestId(`image-${side}-gallery`).setInputFiles(await scenarioPhoto(page, scenario));
  await expect(page.getByTestId(`image-${side}-thumbnail`)).toBeVisible({ timeout: 30_000 });
}

const field = (page: Page, name: string) => page.getByTestId(`field-${name}`);
const mark = (page: Page, name: string) => page.getByTestId(`mark-${name}`);
const saved = (page: Page) => expect(page.getByTestId('save-badge')).toHaveText('محفوظ');

test.describe.configure({ mode: 'serial' });

test('A, B, C, M: a clear card fills the form; an edit keeps the original; a second device sees it', async ({
  page,
  browser,
  request,
}, testInfo) => {
  test.setTimeout(150_000);
  const m = await marketer(request, testInfo.project.name);
  await openNewForm(page, m.phone);

  // A: one side only → no reading yet.
  await uploadSide(page, 'front', 'clear_front');
  await expect(page.getByTestId('reading-waits')).toHaveText('ارفع الوجه الآخر لتبدأ قراءة البطاقة');
  await expect(field(page, 'first_name')).toHaveValue('');

  // B: the back → the eight fields fill, marked «من البطاقة».
  await uploadSide(page, 'back', 'clear_back');
  for (const [name, value] of Object.entries(READ)) {
    await expect(field(page, name)).toHaveValue(value, { timeout: 20_000 });
    await expect(mark(page, name)).toHaveText('من البطاقة');
  }
  // US7: the back fields (owner change, system.md v1.8).
  for (const [name, value] of Object.entries(BACK)) {
    await expect(field(page, name)).toHaveValue(value);
    await expect(mark(page, name)).toHaveText('من البطاقة');
  }
  await expect(page.getByTestId('card-expired')).toHaveCount(0);
  await expect(page.getByTestId('birth-year-mismatch')).toHaveCount(0);
  await expect(page.getByTestId('reading-running')).toHaveCount(0);
  await expect(field(page, 'great_grandfather_name')).toHaveValue('');
  await saved(page);

  // C: correcting a field switches its mark and survives a reload.
  await field(page, 'grandfather_name').fill('مصحح');
  await expect(mark(page, 'grandfather_name')).toHaveText('عُدِّل يدوياً');
  await field(page, 'grandfather_name').blur();
  await saved(page);
  await page.reload();
  await expect(field(page, 'grandfather_name')).toHaveValue('مصحح');
  await expect(mark(page, 'grandfather_name')).toHaveText('عُدِّل يدوياً');
  await expect(mark(page, 'father_name')).toHaveText('من البطاقة');

  // M: the same draft on a second device.
  const url = page.url();
  const other = await browser.newContext({
    baseURL: testInfo.project.use.baseURL as string,
    ignoreHTTPSErrors: true,
  });
  const second = await other.newPage();
  await signIn(second, m.phone, NEW_PASSWORD);
  await expect(second).toHaveURL(/\/$/);
  await second.goto(url);
  await expect(field(second, 'first_name')).toHaveValue(READ.first_name);
  await expect(mark(second, 'first_name')).toHaveText('من البطاقة');
  await expect(field(second, 'grandfather_name')).toHaveValue('مصحح');
  await other.close();
});

test('E: a card without a surname points to «لا يوجد لقب على البطاقة»', async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(120_000);
  const m = await marketer(request, testInfo.project.name);
  await openNewForm(page, m.phone);
  await uploadSide(page, 'front', 'front_no_surname');
  await uploadSide(page, 'back', 'clear_back');

  await expect(field(page, 'first_name')).toHaveValue(READ.first_name, { timeout: 20_000 });
  await expect(field(page, 'surname')).toHaveValue('');
  await expect(page.getByTestId('no-surname-hint')).toBeVisible();
  await expect(page.getByTestId('missing-surname')).toBeVisible();

  await page.getByTestId('field-no_surname').check();
  await expect(page.getByTestId('no-surname-hint')).toHaveCount(0);
  await expect(field(page, 'surname')).toBeDisabled();
  await saved(page);
  await expect(page.getByTestId('missing-surname')).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId('field-no_surname')).toBeChecked();
});

for (const [name, side, scenario, message] of [
  ['G: no card in the photo', 'front', 'no_card', 'لم نتمكن من قراءة وجه البطاقة'],
  ['H: the back in the front slot', 'front', 'clear_back', 'هذه صورة الظهر، ضعها في خانتها'],
  ['I: two cards in one photo', 'front', 'two_cards', 'يظهر أكثر من مستمسك في الصورة'],
] as const) {
  test(`${name}: «أعد التصوير» with tips; typing still works`, async ({ page, request }, testInfo) => {
    test.setTimeout(120_000);
    const m = await marketer(request, testInfo.project.name);
    await openNewForm(page, m.phone);
    await uploadSide(page, side, scenario);
    await uploadSide(page, 'back', 'clear_back');

    const reshoot = page.getByTestId(`image-${side}-reshoot`);
    await expect(reshoot).toContainText(message, { timeout: 20_000 });
    await expect(reshoot).toContainText('بلا لمعة، البطاقة مسطّحة وتملأ الإطار');
    // The back was read: its family number is filled even though the front was not.
    await expect(field(page, 'family_number')).toHaveValue(READ.family_number);
    await expect(field(page, 'first_name')).toHaveValue('');

    await field(page, 'first_name').fill('مكتوب');
    await field(page, 'first_name').blur();
    await saved(page);

    // «أعد التصوير» opens the camera / gallery choice again.
    await reshoot.getByRole('button', { name: 'أعد التصوير' }).click();
    await expect(page.getByTestId(`image-${side}-camera`)).toBeAttached();
    await uploadSide(page, side, 'clear_front');
    await expect(reshoot).toHaveCount(0, { timeout: 20_000 });
    await expect(field(page, 'father_name')).toHaveValue(READ.father_name);
    await expect(field(page, 'first_name')).toHaveValue('مكتوب'); // typed value kept
  });
}

test('J: the same card detected twice is read normally', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  const m = await marketer(request, testInfo.project.name);
  await openNewForm(page, m.phone);
  await uploadSide(page, 'front', 'clear_front');
  await uploadSide(page, 'back', 'duplicate_back');
  await expect(field(page, 'family_number')).toHaveValue(READ.family_number, { timeout: 20_000 });
  await expect(page.getByTestId('image-back-reshoot')).toHaveCount(0);
});

test('US7: an expired card and a birth year that does not match the national ID', async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(120_000);
  const m = await marketer(request, testInfo.project.name);
  await openNewForm(page, m.phone);
  await uploadSide(page, 'front', 'clear_front');
  await uploadSide(page, 'back', 'back_expired');

  await expect(field(page, 'expiry_date')).toHaveValue('2025-01-01', { timeout: 20_000 });
  await expect(page.getByTestId('card-expired')).toHaveText('البطاقة منتهية الصلاحية');
  await saved(page);
  await expect(page.getByTestId('missing-card_expired')).toBeVisible();

  // FR-032: a typed birth year that differs from the national ID only warns.
  await field(page, 'birth_date').fill('1998-01-01');
  await expect(page.getByTestId('birth-year-mismatch')).toHaveText(
    'سنة الميلاد لا تطابق الرقم الوطني، تأكد منهما',
  );
  await expect(mark(page, 'birth_date')).toHaveText('عُدِّل يدوياً');
  await saved(page);
  await expect(page.getByTestId('missing-birth_date')).toHaveCount(0);
});
