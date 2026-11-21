import { expect, test } from '@playwright/test';

import { env, signIn } from './helpers';

const LOCKOUT_ACCOUNT = '07700000002'; // dedicated synthetic account from `seed-demo --e2e`

test('five wrong passwords lock the account, even for the correct password', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'state-changing test: one project only');

  for (let i = 1; i <= 5; i++) {
    await signIn(page, LOCKOUT_ACCOUNT, `wrong-password-${i}`);
    const expected = i < 5 ? 'رقم الهاتف أو كلمة السر غير صحيحة' : 'تم إيقاف الدخول مؤقتاً';
    await expect(page.getByRole('alert')).toContainText(expected);
  }
  await expect(page.getByRole('button', { name: 'دخول' })).toBeDisabled();

  // Fresh page, correct password: still locked, with the wait in minutes.
  await signIn(page, LOCKOUT_ACCOUNT, env('DEMO_MARKETER_PASSWORD'));
  const alert = page.getByRole('alert');
  await expect(alert).toContainText('تم إيقاف الدخول مؤقتاً');
  await expect(alert).toContainText('دقيقة');
  await expect(page).toHaveURL(/\/login$/);
});
