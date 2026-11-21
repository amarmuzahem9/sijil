/**
 * Admin page → permission map (docs/system.md §10 v1.1). Mirror of api/app/core/access.py;
 * both are tested against the shared fixture page_access.json. Hiding pages is convenience only:
 * the server checks every request (Principle IX).
 */
import type { User } from '../lib/api';

export type AccessRule = 'any_admin' | 'super_admin' | readonly string[];

export const PAGE_ACCESS = {
  home: 'any_admin',
  pending: ['review'],
  awaiting_link: ['link'],
  subscribers: ['review', 'link', 'reports'],
  marketers: ['marketers'],
  settings: ['settings'],
  admins: 'super_admin',
  reports: ['reports'],
  import: ['reports'],
  backup: 'super_admin',
  audit: 'super_admin',
  account: 'any_admin',
} as const satisfies Record<string, AccessRule>;

export type PageKey = keyof typeof PAGE_ACCESS;

export const PAGE_PATHS: Record<PageKey, string> = {
  home: '/admin',
  pending: '/admin/pending',
  awaiting_link: '/admin/awaiting-link',
  subscribers: '/admin/subscribers',
  marketers: '/admin/marketers',
  settings: '/admin/settings',
  admins: '/admin/admins',
  reports: '/admin/reports',
  import: '/admin/import',
  backup: '/admin/backup',
  audit: '/admin/audit',
  account: '/admin/account',
};

export function canAccess(user: Pick<User, 'role' | 'permissions'> | null, page: PageKey): boolean {
  if (!user || (user.role !== 'super_admin' && user.role !== 'admin')) return false;
  const rule: AccessRule = PAGE_ACCESS[page];
  if (rule === 'any_admin') return true;
  if (rule === 'super_admin') return user.role === 'super_admin';
  if (user.role === 'super_admin') return true;
  return rule.some((p) => user.permissions.includes(p));
}

export function pageKeyForPath(path: string): PageKey | null {
  const entry = (Object.entries(PAGE_PATHS) as [PageKey, string][]).find(([, p]) => p === path);
  return entry ? entry[0] : null;
}
