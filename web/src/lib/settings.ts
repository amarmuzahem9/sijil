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

export const generalApi = {
  get: () => apiFetch<{ otp_validity_minutes: number }>(`${BASE}/general`),
  update: (otp_validity_minutes: number) =>
    apiFetch<{ otp_validity_minutes: number }>(`${BASE}/general`, {
      method: 'PATCH',
      body: { otp_validity_minutes },
    }),
};

export const catalogApi = { get: () => apiFetch<Catalog>('/api/catalog') };
