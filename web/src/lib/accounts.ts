/** Account management API (specs/002 contracts/api.md). */
import { apiFetch } from './api';
import type { Role } from './api';
import type { Permission } from './labels';

export interface Account {
  id: number;
  name: string;
  phone: string;
  role: Role;
  permissions: Permission[];
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

export type AccountKind = 'admins' | 'marketers';

export interface AccountInput {
  name: string;
  phone: string;
  temporary_password: string;
  permissions?: Permission[];
}

export interface AccountPatch {
  name?: string;
  phone?: string;
  permissions?: Permission[];
}

/** An archived account (specs/003 contracts/api.md). */
export interface ArchivedAccount {
  id: number;
  name: string;
  phone: string;
  role: Role;
  permissions: Permission[];
  archived_at: string;
  archived_by: { id: number; name: string; role: Role } | null;
}

const base = (kind: AccountKind) => `/api/admin/${kind}`;

export const accountsApi = {
  list: (kind: AccountKind) => apiFetch<{ items: Account[] }>(base(kind)).then((r) => r.items),
  create: (kind: AccountKind, body: AccountInput) =>
    apiFetch<Account>(base(kind), { method: 'POST', body }),
  update: (kind: AccountKind, id: number, body: AccountPatch) =>
    apiFetch<Account>(`${base(kind)}/${id}`, { method: 'PATCH', body }),
  deactivate: (kind: AccountKind, id: number) =>
    apiFetch<Account>(`${base(kind)}/${id}/deactivate`, { method: 'POST' }),
  reactivate: (kind: AccountKind, id: number) =>
    apiFetch<Account>(`${base(kind)}/${id}/reactivate`, { method: 'POST' }),
  resetPassword: (kind: AccountKind, id: number, temporary_password: string) =>
    apiFetch<Account>(`${base(kind)}/${id}/reset-password`, {
      method: 'POST',
      body: { temporary_password },
    }),
  /** «حذف»: moves the account to the archive (main admin only). */
  archive: (id: number) => apiFetch<Account>(`/api/admin/archive/${id}`, { method: 'POST' }),
  listArchived: () =>
    apiFetch<{ items: ArchivedAccount[] }>('/api/admin/archive').then((r) => r.items),
  restore: (id: number) =>
    apiFetch<Account>(`/api/admin/archive/${id}/restore`, { method: 'POST' }),
};
