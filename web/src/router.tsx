import { createBrowserRouter, Navigate } from 'react-router-dom';
import type { RouteObject } from 'react-router-dom';

import {
  MustChangePasswordGate,
  RequireAnonymous,
  RequireAuth,
  RequirePage,
  RequireRole,
} from './auth/guards';
import type { PageKey } from './auth/access';
import { ADMIN_ROLES } from './auth/roles';
import AdminLayout from './layouts/AdminLayout';
import MarketerLayout from './layouts/MarketerLayout';
import AccountPanel from './pages/AccountPanel';
import {
  AdminAwaitingLink,
  AdminBackup,
  AdminHome,
  AdminImport,
  AdminPending,
  AdminReports,
  AdminSubscribers,
} from './pages/admin/placeholders';
import Admins from './pages/admin/Admins';
import Archive from './pages/admin/Archive';
import Audit from './pages/admin/Audit';
import Settings from './pages/admin/settings/Settings';
import Marketers from './pages/admin/Marketers';
import ChangePassword from './pages/ChangePassword';
import Login from './pages/Login';
import Dashboard from './pages/marketer/Dashboard';
import { MarketerNotifications } from './pages/marketer/placeholders';
import Requests from './pages/marketer/Requests';
import SubscriberForm from './pages/marketer/subscriber/SubscriberForm';

/** Wrap one admin route in its §10 permission guard (specs/002 contracts/ui-routes.md). */
function page(key: PageKey, route: RouteObject): RouteObject {
  return { element: <RequirePage page={key} />, children: [route] };
}

// contracts/ui-routes.md
export const router = createBrowserRouter([
  {
    element: <RequireAnonymous />,
    children: [{ path: '/login', element: <Login /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      { path: '/change-password', element: <ChangePassword /> },
      {
        element: <MustChangePasswordGate />,
        children: [
          {
            element: <RequireRole roles={['marketer']} />,
            children: [
              {
                element: <MarketerLayout />,
                children: [
                  { path: '/', element: <Dashboard /> },
                  { path: '/requests', element: <Requests /> },
                  // specs/005: new-subscriber form. One route for /drafts/new and /drafts/{id}, so
                  // the form stays mounted when the URL is replaced after the first save.
                  { path: '/drafts/:draftId', element: <SubscriberForm /> },
                  { path: '/notifications', element: <MarketerNotifications /> },
                  { path: '/account', element: <AccountPanel /> },
                ],
              },
            ],
          },
          {
            element: <RequireRole roles={ADMIN_ROLES} />,
            children: [
              {
                path: '/admin',
                element: <AdminLayout />,
                children: [
                  page('home', { index: true, element: <AdminHome /> }),
                  page('pending', { path: 'pending', element: <AdminPending /> }),
                  page('awaiting_link', { path: 'awaiting-link', element: <AdminAwaitingLink /> }),
                  page('subscribers', { path: 'subscribers', element: <AdminSubscribers /> }),
                  page('marketers', { path: 'marketers', element: <Marketers /> }),
                  page('settings', { path: 'settings', element: <Settings /> }),
                  page('admins', { path: 'admins', element: <Admins /> }),
                  page('reports', { path: 'reports', element: <AdminReports /> }),
                  page('import', { path: 'import', element: <AdminImport /> }),
                  page('backup', { path: 'backup', element: <AdminBackup /> }),
                  page('audit', { path: 'audit', element: <Audit /> }),
                  page('archive', { path: 'archive', element: <Archive /> }),
                  page('account', { path: 'account', element: <AccountPanel /> }),
                ],
              },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
