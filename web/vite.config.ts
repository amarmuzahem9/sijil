/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    // contracts/ui-routes.md "PWA manifest". Only the app shell is cached — never /api/*,
    // so no account data is ever stored by the service worker (Principle II).
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'script',
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'سِجلّ',
        short_name: 'سِجلّ',
        description: 'تسجيل طلبات اشتراك الإنترنت — تكنولوجي للإنترنت',
        lang: 'ar',
        dir: 'rtl',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        theme_color: '#0f5fa8',
        background_color: '#f4f6f9',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: '/icons/icon-512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
        cleanupOutdatedCaches: true,
      },
      devOptions: { enabled: false },
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // Served through Caddy at https://localhost; HMR uses the page's own host/port (wss).
    allowedHosts: ['localhost', 'web'],
    watch: process.env.VITE_POLL === 'true' ? { usePolling: true, interval: 300 } : undefined,
  },
  build: {
    target: 'es2020',
    sourcemap: false,
    // Budget is 300 KB gzipped for the app shell (plan.md); MUI makes the raw size ~560 KB.
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    // The first MUI render of a page in a file takes 0.4–0.7 s alone; with the files running in
    // parallel and the e2e stack building on the same machine it crossed the 5 s default and
    // timed out now and then (specs/011, batch 5). Real hangs still fail, after 15 s.
    testTimeout: 15_000,
  },
});
