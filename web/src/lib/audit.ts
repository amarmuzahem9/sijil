/** Audit viewer API, main admin only (specs/002 contracts/api.md › Audit log). */
import { apiFetch } from './api';
import type { Role } from './api';

export interface Person {
  id: number;
  name: string;
  role: Role;
}

export interface AuditEntry {
  id: number;
  created_at: string;
  action: string;
  actor: Person | null;
  entity_type: string;
  entity_id: string;
  target: Person | null;
  /** Settings items (004): current area/plan name or tower code. */
  target_label: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  /** The request this entry is about was deleted later (specs/011 R12); the entry is unchanged. */
  entity_deleted?: boolean;
}

export interface AuditPage {
  items: AuditEntry[];
  has_more: boolean;
  next_before_id: number | null;
}

export interface AuditFilters {
  /** Baghdad dates, `YYYY-MM-DD`, inclusive. */
  from?: string;
  to?: string;
  /** A user id, or `system` for entries without an actor. */
  actorId?: string;
}

export const SYSTEM_ACTOR = 'system';

export const auditApi = {
  page: (filters: AuditFilters, beforeId?: number) => {
    const params = new URLSearchParams();
    if (filters.from) params.set('from', filters.from);
    if (filters.to) params.set('to', filters.to);
    if (filters.actorId) params.set('actor_id', filters.actorId);
    if (beforeId) params.set('before_id', String(beforeId));
    const qs = params.toString();
    return apiFetch<AuditPage>(`/api/admin/audit${qs ? `?${qs}` : ''}`);
  },
  actors: () => apiFetch<{ items: Person[] }>('/api/admin/audit/actors').then((r) => r.items),
};
