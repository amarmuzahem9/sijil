/**
 * «إدخال إحداثية» (docs/system.md §5.2 v1.6): read "lat, lng" typed by hand or a pasted Google Maps
 * link, and check that the point is inside Iraq's bounding box. The server checks the same box
 * (api/app/core/iraq_bounds.py), so keep the two in sync.
 */
import type { LatLngLiteral } from './googleMaps';

export const IRAQ_BOUNDS = { latMin: 29.0, latMax: 37.5, lngMin: 38.7, lngMax: 48.8 } as const;

export function inIraq(pos: LatLngLiteral): boolean {
  return (
    pos.lat >= IRAQ_BOUNDS.latMin &&
    pos.lat <= IRAQ_BOUNDS.latMax &&
    pos.lng >= IRAQ_BOUNDS.lngMin &&
    pos.lng <= IRAQ_BOUNDS.lngMax
  );
}

export type CoordinateError = 'empty' | 'format' | 'short_link' | 'swapped' | 'outside_iraq';

export type CoordinateResult =
  { ok: true; pos: LatLngLiteral } | { ok: false; error: CoordinateError };

export const COORDINATE_ERRORS: Record<CoordinateError, string> = {
  empty: 'اكتب الإحداثية أو الصق رابط Google Maps',
  format: 'الصيغة غير مفهومة. اكتب «خط العرض, خط الطول» مثل 34.70, 43.68',
  short_link:
    'الروابط المختصرة (maps.app.goo.gl) غير مدعومة. افتح الرابط في Google Maps وانسخ الإحداثية أو الرابط الكامل',
  swapped: 'يبدو أن خط العرض وخط الطول مقلوبان. خط العرض أولاً (بين 29 و37)',
  outside_iraq: 'الموقع خارج العراق، تأكد من الإحداثيات',
};

const NUMBER = String.raw`[-+]?\d{1,3}(?:\.\d+)?`;
const PAIR = new RegExp(String.raw`^(${NUMBER})\s*[,\s]\s*(${NUMBER})$`);

/** Arabic-Indic and Persian digits to Latin, the Arabic decimal mark and comma to "." and ",". */
function latinize(text: string): string {
  let out = '';
  for (const ch of text) {
    const c = ch.codePointAt(0) ?? 0;
    if (c >= 0x0660 && c <= 0x0669) out += String(c - 0x0660);
    else if (c >= 0x06f0 && c <= 0x06f9) out += String(c - 0x06f0);
    else if (c === 0x066b)
      out += '.'; // Arabic decimal separator
    else if (c === 0x060c || c === 0x066c)
      out += ','; // Arabic comma, thousands separator
    else out += ch;
  }
  return out;
}

function pairFrom(text: string): LatLngLiteral | null {
  const m = PAIR.exec(text.trim());
  if (!m) return null;
  return { lat: Number(m[1]), lng: Number(m[2]) };
}

/** Coordinates inside a Google Maps link, the most precise form first. */
function fromLink(text: string): LatLngLiteral | null {
  let decoded = text;
  try {
    decoded = decodeURIComponent(text);
  } catch {
    // keep the raw text
  }
  // The place itself (…!3d34.70!4d43.68), not the viewport centre.
  const place = new RegExp(String.raw`!3d(${NUMBER})!4d(${NUMBER})`).exec(decoded);
  if (place) return { lat: Number(place[1]), lng: Number(place[2]) };
  // ?q=, ?query=, ?ll=, ?destination=, ?center=, ?daddr=
  const param = new RegExp(
    String.raw`[?&](?:q|query|ll|destination|center|daddr|sll)=(?:loc:)?(${NUMBER})\s*,\s*(${NUMBER})`,
  ).exec(decoded);
  if (param) return { lat: Number(param[1]), lng: Number(param[2]) };
  // /@34.70,43.68,17z (the map view)
  const at = new RegExp(String.raw`@(${NUMBER}),(${NUMBER})`).exec(decoded);
  if (at) return { lat: Number(at[1]), lng: Number(at[2]) };
  // /search/34.70,+43.68 or /place/34.70,43.68
  const path = new RegExp(String.raw`/(?:search|place|dir)/(${NUMBER}),\s*\+?(${NUMBER})`).exec(
    decoded,
  );
  if (path) return { lat: Number(path[1]), lng: Number(path[2]) };
  return null;
}

export function parseCoordinates(raw: string): CoordinateResult {
  const text = latinize(raw).trim();
  if (!text) return { ok: false, error: 'empty' };
  if (/(?:maps\.app\.goo\.gl|goo\.gl\/maps|g\.co\/kgs)/i.test(text)) {
    return { ok: false, error: 'short_link' };
  }

  let pos: LatLngLiteral | null;
  if (/^geo:/i.test(text)) pos = pairFrom(text.slice(4).split(/[;?]/)[0]);
  else if (/^https?:\/\/|google\.|^www\./i.test(text)) pos = fromLink(text);
  else pos = pairFrom(text);

  if (
    !pos ||
    !Number.isFinite(pos.lat) ||
    !Number.isFinite(pos.lng) ||
    Math.abs(pos.lat) > 90 ||
    Math.abs(pos.lng) > 180
  ) {
    return { ok: false, error: 'format' };
  }
  if (!inIraq(pos)) {
    const swapped = { lat: pos.lng, lng: pos.lat };
    return { ok: false, error: inIraq(swapped) ? 'swapped' : 'outside_iraq' };
  }
  return { ok: true, pos };
}
