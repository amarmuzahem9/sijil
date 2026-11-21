import { expect, test } from '@playwright/test';

test('installable PWA: manifest, iOS tags, service worker, API never served from cache', async ({
  page,
  request,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-chrome', 'checks static assets once');

  const manifestRes = await request.get('/manifest.webmanifest');
  expect(manifestRes.ok()).toBeTruthy();
  const manifest = await manifestRes.json();
  expect(manifest).toMatchObject({
    name: 'سِجلّ',
    short_name: 'سِجلّ',
    lang: 'ar',
    dir: 'rtl',
    display: 'standalone',
    start_url: '/',
  });
  const icons = manifest.icons as { src: string; sizes: string; purpose?: string }[];
  expect(icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(['192x192', '512x512']));
  expect(icons.some((i) => i.purpose === 'maskable')).toBeTruthy();
  for (const icon of icons) {
    expect((await request.get(icon.src)).ok(), icon.src).toBeTruthy();
  }

  await page.goto('/login');
  await expect(page.locator('link[rel="manifest"]')).toHaveCount(1);
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute(
    'href',
    '/icons/apple-touch-icon.png',
  );
  await expect(page.locator('meta[name="apple-mobile-web-app-capable"]')).toHaveAttribute(
    'content',
    'yes',
  );
  await expect(page.locator('meta[name="apple-mobile-web-app-title"]')).toHaveAttribute(
    'content',
    'سِجلّ',
  );
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#0f5fa8');
  expect((await request.get('/icons/apple-touch-icon.png')).ok()).toBeTruthy();

  // The service worker installs and takes control.
  const active = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    return Boolean(reg.active);
  });
  expect(active).toBeTruthy();
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);

  // With the worker in control, API calls still go to the network.
  const apiResponse = page.waitForResponse((r) => r.url().includes('/api/auth/refresh'));
  await page.reload();
  expect((await apiResponse).fromServiceWorker()).toBe(false);
});
