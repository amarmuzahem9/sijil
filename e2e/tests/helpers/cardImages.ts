/**
 * Synthetic «card» photos for the fake card reader (specs/006 research R10).
 *
 * The whole picture is filled with the scenario's colour (fixtures/ocr-scenarios.json, generated
 * from api/app/services/card_reader_fake_data.py), so the fake reader picks that scenario even
 * after the browser's resize and JPEG compression. Only the words «بطاقة تجريبية» are drawn:
 * never a real card, name or number.
 */
import { readFileSync } from 'node:fs';

import type { Page } from '@playwright/test';

const palette = JSON.parse(
  readFileSync(new URL('../fixtures/ocr-scenarios.json', import.meta.url), 'utf8'),
) as Record<string, [number, number, number]>;

export type CardScenario = keyof typeof palette & string;

export async function scenarioPhoto(
  page: Page,
  scenario: CardScenario,
  width = 1200,
  height = 760,
): Promise<{ name: string; mimeType: string; buffer: Buffer }> {
  const rgb = palette[scenario];
  if (!rgb) throw new Error(`unknown card scenario: ${scenario}`);
  const base64 = await page.evaluate(
    async ({ rgb, width, height, scenario }) => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = '#ffffff';
      ctx.strokeRect(width / 4, height / 3, width / 2, height / 3);
      ctx.fillStyle = '#ffffff';
      ctx.font = `${Math.round(height / 14)}px sans-serif`;
      ctx.fillText(`بطاقة تجريبية — ${scenario}`, width / 4 + 10, height / 2);
      const blob: Blob = await new Promise((r) => canvas.toBlob((b) => r(b!), 'image/jpeg', 0.9));
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let s = '';
      for (const b of bytes) s += String.fromCharCode(b);
      return btoa(s);
    },
    { rgb, width, height, scenario },
  );
  return {
    name: `${scenario}.jpg`,
    mimeType: 'image/jpeg',
    buffer: Buffer.from(base64, 'base64'),
  };
}
