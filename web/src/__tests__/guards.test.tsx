import { cleanup, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Role } from '../lib/api';

// Controls what useAuth() returns for each test.
const auth = vi.hoisted(() => ({
  state: { status: 'authenticated', user: null as unknown, notice: null },
}));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => auth.state }));

import { MustChangePasswordGate, RequireAuth, RequireRole } from '../auth/guards';

function signedIn(role: Role, mustChange = false) {
  auth.state = {
    status: 'authenticated',
    notice: null,
    user: {
      id: 1,
      name: 'مستخدم',
      phone: '07700000001',
      role,
      permissions: [],
      must_change_password: mustChange,
    },
  };
}

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <p>login-page</p> },
      { path: '/change-password', element: <p>change-password-page</p> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <MustChangePasswordGate />,
            children: [
              {
                element: <RequireRole roles={['marketer']} />,
                children: [
                  { path: '/', element: <p>marketer-home</p> },
                  { path: '/requests', element: <p>marketer-requests</p> },
                ],
              },
              {
                element: <RequireRole roles={['super_admin', 'admin']} />,
                children: [
                  { path: '/admin', element: <p>admin-home</p> },
                  { path: '/admin/settings', element: <p>admin-settings</p> },
                ],
              },
            ],
          },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
}

afterEach(cleanup);

describe('route guards', () => {
  it.each(['/', '/requests', '/admin', '/admin/settings'])(
    'a flagged user is sent from %s to /change-password',
    (path) => {
      signedIn(path.startsWith('/admin') ? 'admin' : 'marketer', true);
      renderAt(path);
      expect(screen.getByText('change-password-page')).toBeTruthy();
    },
  );

  it('sends a marketer from /admin to /', () => {
    signedIn('marketer');
    renderAt('/admin');
    expect(screen.getByText('marketer-home')).toBeTruthy();
  });

  it.each<Role>(['admin', 'super_admin'])('sends %s from / to /admin', (role) => {
    signedIn(role);
    renderAt('/');
    expect(screen.getByText('admin-home')).toBeTruthy();
  });

  it('sends signed-out visitors to /login', () => {
    auth.state = { status: 'anonymous', user: null, notice: null };
    renderAt('/admin/settings');
    expect(screen.getByText('login-page')).toBeTruthy();
  });
});
