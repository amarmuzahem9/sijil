/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// PWA (vite-plugin-pwa) is configured in feature 001 / US6.
export default defineConfig({
  plugins: [react()],
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
  },
});
