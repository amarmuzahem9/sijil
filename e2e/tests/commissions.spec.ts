import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';

import { apiSignIn, env, signIn } from './helpers';

/**
 * Feature 017: rewards and commissions, end to end (specs/017 T052).
 *
 * The data comes from api/tests/e2e_commission_seed.py (run by scripts/e2e.sh): one synthetic
 * marketer with 3 links last month, a return accepted with «لا» last month, and 2 links this month.
 * The browser has no test clock, so last month's links are written by that seed.
 *
 * 1. The `commissions` admin opens «العمولات» on last month: 3 × rate, «بلا عمولة: 1», the details.
 * 2. «تم الدفع» locks it. The marketer's «الأشهر السابقة» shows «تم الدفع» and the locked amount.
 * 3. One paid link is undone: the paid row keeps its figures and shows «تراجع بعد الدفع»; the
 *    admin home warns.
 * 4. A `link`-only admin has no «العمولات» in the menu. The marketer home shows the tier.
 */

const PASSWORD = () => env('DEMO_MARKETER_PASSWORD');
const MARKETER = { phone: '07710017001', name: 'مسوّق عمولات تجريبي' };
const COMMISSIONS_ADMIN = '07710017002';
const LINK_ADMIN = '07710017003';

/** «1,234» like the app (en-US grouping). */
const n = (value: number) => new Intl.NumberFormat('en-US').format(value);

/**
 * The tier rate of the seeded marketer, read from their home (2 counted links this month). The
 * seeded counts (2 and 3) fall in the same tier unless a tier starts at 3; the default tiers and
 * every spec before this one keep the first tier from 0 to 29.
 */
async function currentRate(request: APIRequestContext): Promise<number> {
  const headers = await apiSignIn(request, MARKETER.phone, PASSWORD());
  const res = await request.get('/api/marketer/dashboard', { headers });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.linked_this_month).toBe(2);
  return body.tier_rate;
}

async function pageAs(browser: Browser, phone: string): Promise<Page> {
  const page = await (await browser.newContext({ ignoreHTTPSErrors: true })).newPage();
  await signIn(page, phone, PASSWORD());
  await expect(page).not.toHaveURL(/\/login$/);
  return page;
}

function lastMonth(): string {
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Baghdad' }));
  const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

async function openMonth(page: Page, month: string) {
  await page.goto('/admin/commissions');
  await page.getByRole('combobox', { name: 'الشهر' }).click();
  await page.getByRole('option', { name: month }).click();
}

function marketerRow(page: Page) {
  return page.getByTestId('commission-row').filter({ hasText: MARKETER.name });
}

test('commissions: report, «تم الدفع», undo after payment, past months', async ({
  page,
  request,
  browser,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'one set of seeded links; state-changing');
  const month = lastMonth();
  const rate = await currentRate(request);

  // 1. The report of last month.
  await signIn(page, COMMISSIONS_ADMIN, PASSWORD());
  await expect(page.getByRole('navigation', { name: 'القائمة الرئيسية' }).first()).toContainText(
    'العمولات',
  );
  await openMonth(page, month);
  const row = marketerRow(page);
  await expect(row.getByTestId('row-amount')).toHaveText(
    `3 × ${n(rate)} د.ع = ${n(3 * rate)} د.ع`,
  );
  await expect(row.getByTestId('row-extra')).toHaveText('بلا عمولة: 1 · مدفوع سابقاً: 0');
  await expect(row.getByText('غير مدفوع')).toBeVisible();

  await row.getByRole('button', { name: 'التفاصيل' }).click();
  const detail = page.getByRole('dialog');
  await expect(detail.getByText('المحسوبة (3)')).toBeVisible();
  await expect(detail.getByText('بلا عمولة (1)')).toBeVisible();
  await expect(detail.getByText(/07\d{9}/)).toHaveCount(0); // no phone in the details
  await detail.getByRole('button', { name: 'إغلاق' }).click();

  // 2. «تم الدفع».
  await row.getByRole('button', { name: 'تم الدفع' }).click();
  const pay = page.getByRole('dialog');
  await expect(pay.getByTestId('pay-figures')).toHaveText(
    `3 × ${n(rate)} د.ع = ${n(3 * rate)} د.ع`,
  );
  await pay.getByRole('button', { name: 'تأكيد الدفع' }).click();
  await expect(pay).toBeHidden();
  await expect(row.getByText('تم الدفع', { exact: true })).toBeVisible();
  await expect(row.getByTestId('row-paid')).toContainText('أدمن عمولات تجريبي');
  await expect(row.getByRole('button', { name: 'تم الدفع' })).toHaveCount(0);

  // 3. Undo one paid link (as the same admin, who also holds `link`), through the API.
  const admin = await apiSignIn(request, COMMISSIONS_ADMIN, PASSWORD());
  const recent = await request.get('/api/admin/links/recent?q=07817000001', { headers: admin });
  const [paidLink] = (await recent.json()).items;
  const undo = await request.post(`/api/admin/requests/${paidLink.id}/unlink`, {
    headers: admin,
    data: { reason: 'not_linked_in_sas', link_id: paidLink.link_id },
  });
  expect(undo.status()).toBe(200);

  await openMonth(page, month);
  await expect(row.getByTestId('row-amount')).toHaveText(
    `3 × ${n(rate)} د.ع = ${n(3 * rate)} د.ع`,
  );
  const alert = row.getByTestId('row-alert');
  await expect(alert).toContainText('تراجع بعد الدفع · المدفوع 3، اليوم 2');
  await expect(alert).toContainText(paidLink.number_label);
  await expect(alert).toContainText('لم يُربط فعلياً في SAS');

  await page.goto('/admin');
  await expect(page.getByText('يوجد تراجع بعد الدفع')).toBeVisible();
  await page.getByRole('link', { name: 'صفحة العمولات' }).click();
  await expect(page).toHaveURL(/\/admin\/commissions$/);

  // 4a. A `link`-only admin sees no «العمولات» and no warning.
  const linker = await pageAs(browser, LINK_ADMIN);
  await expect(linker.getByRole('heading', { name: 'الرئيسية' })).toBeVisible();
  await expect(
    linker.getByRole('navigation', { name: 'القائمة الرئيسية' }).first(),
  ).not.toContainText('العمولات');
  await expect(linker.getByText('يوجد تراجع بعد الدفع')).toHaveCount(0);

  // 4b. The marketer: the tier on the home, «تم الدفع» in «الأشهر السابقة».
  const marketer = await pageAs(browser, MARKETER.phone);
  await expect(marketer.getByTestId('linked-counter')).toHaveText('تم الربط هذا الشهر: 2');
  await expect(marketer.getByTestId('expected-amount')).toHaveText(
    `المبلغ المتوقع: ${n(2 * rate)} د.ع`,
  );
  await marketer.getByRole('link', { name: 'الأشهر السابقة' }).click();
  const past = marketer.getByTestId('past-month').first();
  await expect(past.getByText('تم الدفع')).toBeVisible();
  await expect(past.getByTestId('past-month-amount')).toHaveText(
    `3 × ${n(rate)} د.ع = ${n(3 * rate)} د.ع`,
  );
  await expect(past.getByTestId('past-month-without')).toHaveText('و 1 بلا عمولة');
  await expect(past.getByText('أدمن عمولات تجريبي')).toHaveCount(0);
  await expect(marketer.getByTestId('past-month')).toHaveCount(1);
});
