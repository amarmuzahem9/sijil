import type { Role, User } from '../lib/api';

export const ROLE_LABELS: Record<Role, string> = {
  super_admin: 'أدمن رئيسي',
  admin: 'أدمن',
  marketer: 'مسوّق',
};

export const ADMIN_ROLES: Role[] = ['super_admin', 'admin'];

/** data-model.md "Role → landing page". */
export function landingPath(user: Pick<User, 'role' | 'must_change_password'>): string {
  if (user.must_change_password) return '/change-password';
  return user.role === 'marketer' ? '/' : '/admin';
}
