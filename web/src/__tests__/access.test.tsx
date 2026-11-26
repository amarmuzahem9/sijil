import { cleanup, render, screen, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import fixture from './fixtures/page_access.json';
import { canAccess, PAGE_ACCESS, PAGE_PATHS, pageKeyForPath } from '../auth/access';
import type { PageKey } from '../auth/access';
import type { Role } from '../lib/api';

const auth = vi.hoisted(() => ({
  state: { user: null as unknown, refreshUser: () => Promise.resolve() },
}));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => auth.state }));

import AdminLayout from '../layouts/AdminLayout';
import { RequirePage } from '../auth/guards';

type Case = { role: Role; permissions: string[]; visible: string[] };
const cases = fixture.cases as Case[];
const label = (c: Case) => `${c.role}:[${c.permissions.join(',')}]`;

function user(c: Case) {
  return {
    id: 1,
    name: 'مستخدم',
    phone: '07700000001',
    role: c.role,
    permissions: c.permissions,
    must_change_password: false,
  };
}

afterEach(cleanup);

describe('access map (shared fixture with the API)', () => {
  it('has the same rules as the fixture', () => {
    const expected = Object.fromEntries(fixture.pages.map((p) => [p.key, p.access]));
    expect(JSON.parse(JSON.stringify(PAGE_ACCESS))).toEqual(expected);
    for (const p of fixture.pages) expect(PAGE_PATHS[p.key as PageKey]).toBe(p.path);
  });

  it.each(cases.map((c) => [label(c), c] as const))('visible pages for %s', (_, c) => {
    const visible = (Object.keys(PAGE_ACCESS) as PageKey[]).filter((k) => canAccess(user(c), k));
    expect(visible).toEqual(c.visible);
  });

  it('maps paths back to page keys', () => {
    expect(pageKeyForPath('/admin/settings')).toBe('settings');
    expect(pageKeyForPath('/nowhere')).toBeNull();
  });
});

function renderAdmin(c: Case, path = '/admin') {
  auth.state = { user: user(c), refreshUser: () => Promise.resolve() };
  const router = createMemoryRouter(
    [
      {
        path: '/admin',
        element: <AdminLayout />,
        children: [
          {
            element: <RequirePage page="home" />,
            children: [{ index: true, element: <p>home-page</p> }],
          },
          {
            element: <RequirePage page="settings" />,
            children: [{ path: 'settings', element: <p>settings-page</p> }],
          },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
}

describe('admin menu and page guard', () => {
  // Render the desktop layout (permanent sidebar): jsdom has no matchMedia of its own.
  beforeAll(() => {
    window.matchMedia = ((query: string) => ({
      matches: query.includes('min-width'),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as typeof window.matchMedia;
  });

  const pageLabels: Record<string, string> = {
    settings: 'الإعدادات',
    marketers: 'المسوّقون',
    admins: 'الأدمنية والصلاحيات',
    audit: 'سجل العمليات',
    commissions: 'العمولات',
  };

  it.each(cases.filter((c) => c.role !== 'marketer').map((c) => [label(c), c] as const))(
    'menu for %s follows the map',
    (_, c) => {
      renderAdmin(c);
      const nav = screen.getAllByRole('navigation', { name: 'القائمة الرئيسية' })[0];
      for (const [key, text] of Object.entries(pageLabels)) {
        const shown = within(nav).queryByText(text) !== null;
        expect(shown, `${key} in menu`).toBe(c.visible.includes(key));
      }
    },
  );

  it('a marketers-only admin opening settings by address lands on home', () => {
    renderAdmin({ role: 'admin', permissions: ['marketers'], visible: [] }, '/admin/settings');
    expect(screen.getByText('home-page')).toBeTruthy();
    expect(screen.queryByText('settings-page')).toBeNull();
  });
});
