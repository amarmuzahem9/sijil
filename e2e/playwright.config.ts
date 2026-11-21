import { defineConfig, devices } from '@playwright/test';

// Runs inside the e2e container against the isolated stack started by scripts/e2e.sh.
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  // One worker: files run in name order, so admin-first-login (which sets the main admin's
  // password) runs before the feature-002 specs that sign in as the main admin.
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'https://proxy',
    ignoreHTTPSErrors: true,
    locale: 'ar-IQ',
    timezoneId: 'Asia/Baghdad',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    // The e2e stack uses Caddy's internal CA. Chromium only registers service workers on a
    // trusted certificate, and ignoreHTTPSErrors does not cover that — hence the launch flag.
    {
      name: 'desktop-chrome',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: { args: ['--ignore-certificate-errors'] },
      },
    },
    {
      name: 'pixel-7',
      use: { ...devices['Pixel 7'], launchOptions: { args: ['--ignore-certificate-errors'] } },
    },
    { name: 'iphone-14', use: { ...devices['iPhone 14'] } },
  ],
});
