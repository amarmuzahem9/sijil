/** Settings and catalog API (specs/004 contracts/api.md). Money is always an integer here. */
import { apiFetch } from './api';

export interface Area {
  id: number;
  name: string;
  is_active: boolean;
  in_use: boolean;
  tower_count: number;
}

export interface Tower {
  id: number;
  code: string;
  name: string;
  area: { id: number; name: string; is_active: boolean };
  is_active: boolean;
  in_use: boolean;
}

export interface Plan {
  id: number;
  name: string;
  trial_price: number;
  second_price: number;
  is_active: boolean;
  in_use: boolean;
}

export interface Tier {
  min_count: number;
  rate: number;
}

export interface Catalog {
  areas: { id: number; name: string }[];
  towers: { id: number; code: string; name: string; area_id: number }[];
  plans: { id: number; name: string; trial_price: number; second_price: number }[];
}

export type Collection = 'areas' | 'towers' | 'plans';

const BASE = '/api/admin/settings';

function crud<T, C, U>(collection: Collection) {
  const url = `${BASE}/${collection}`;
  return {
    list: () => apiFetch<{ items: T[] }>(url).then((r) => r.items),
    create: (body: C) => apiFetch<T>(url, { method: 'POST', body }),
    update: (id: number, body: U) => apiFetch<T>(`${url}/${id}`, { method: 'PATCH', body }),
    deactivate: (id: number) => apiFetch<T>(`${url}/${id}/deactivate`, { method: 'POST' }),
    reactivate: (id: number) => apiFetch<T>(`${url}/${id}/reactivate`, { method: 'POST' }),
    remove: (id: number) => apiFetch<void>(`${url}/${id}`, { method: 'DELETE' }),
  };
}

export const areasApi = crud<Area, { name: string }, { name?: string }>('areas');
export const towersApi = crud<
  Tower,
  { code: string; name: string; area_id: number },
  { code?: string; name?: string; area_id?: number }
>('towers');
export const plansApi = crud<
  Plan,
  { name: string; trial_price: number; second_price: number },
  { name?: string; trial_price?: number; second_price?: number }
>('plans');

export const tiersApi = {
  get: () => apiFetch<{ items: Tier[] }>(`${BASE}/tiers`).then((r) => r.items),
  replace: (items: Tier[]) =>
    apiFetch<{ items: Tier[] }>(`${BASE}/tiers`, { method: 'PUT', body: { items } }).then(
      (r) => r.items,
    ),
};

export interface GeneralSettings {
  otp_validity_minutes: number;
  /** «رقم واتساب الإدارة» (specs/009), null when not set. */
  admin_whatsapp: string | null;
}

/** PATCH sends only the keys given; each changes alone (specs/009 T030). */
export const generalApi = {
  get: () => apiFetch<GeneralSettings>(`${BASE}/general`),
  update: (changes: Partial<GeneralSettings>) =>
    apiFetch<GeneralSettings>(`${BASE}/general`, { method: 'PATCH', body: changes }),
};

export const catalogApi = { get: () => apiFetch<Catalog>('/api/catalog') };

/**
 * The range each tier row covers, in the rows' own order: «0 إلى 29», «50 فأكثر». Rows may be in
 * any order while editing; a row whose count is missing or duplicated shows «—».
 */
export function tierRanges(counts: (number | null)[]): string[] {
  const valid = counts.filter((c): c is number => c !== null);
  const sorted = [...new Set(valid)].sort((a, b) => a - b);
  const fmt = (n: number) => new Intl.NumberFormat('en-US').format(n);
  return counts.map((c) => {
    if (c === null || valid.indexOf(c) !== valid.lastIndexOf(c)) return '—';
    const next = sorted.find((n) => n > c);
    return next === undefined ? `${fmt(c)} فأكثر` : `${fmt(c)} إلى ${fmt(next - 1)}`;
  });
}
