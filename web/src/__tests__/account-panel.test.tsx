import { cleanup, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Role } from '../lib/api';

const auth = vi.hoisted(() => ({ state: {} as Record<string, unknown> }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => auth.state }));

import AccountPanel from '../pages/AccountPanel';

function renderAs(role: Role) {
  auth.state = {
    user: {
      id: 1,
      name: 'اسم تجريبي',
      phone: '07700000009',
      role,
      permissions: [],
      must_change_password: false,
    },
    logout: vi.fn(),
    refreshUser: vi.fn(),
  };
  const router = createMemoryRouter([{ path: '/', element: <AccountPanel /> }]);
  render(<RouterProvider router={router} />);
}

afterEach(cleanup);

describe('«حسابي» (docs/system.md §3.5)', () => {
  it.each<Role>(['marketer', 'admin', 'super_admin'])(
    'shows name and phone read-only for %s',
    (role) => {
      renderAs(role);
      expect(screen.getByText('اسم تجريبي')).toBeTruthy();
      expect(screen.getByText('07700000009')).toBeTruthy();
      expect(screen.queryAllByRole('textbox')).toHaveLength(0);
      expect(screen.getByRole('link', { name: 'تغيير كلمة السر' })).toBeTruthy();
      expect(screen.getByRole('button', { name: 'تسجيل الخروج' })).toBeTruthy();
    },
  );

  it.each<[Role, boolean]>([
    ['marketer', false],
    ['admin', false],
    ['super_admin', true],
  ])('«تعديل الاسم» for %s: %s', (role, shown) => {
    renderAs(role);
    expect(screen.queryByRole('button', { name: 'تعديل الاسم' }) !== null).toBe(shown);
  });
});
