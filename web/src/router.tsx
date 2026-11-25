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
import RouteError from './components/RouteError';
import AdminLayout from './layouts/AdminLayout';
import MarketerLayout from './layouts/MarketerLayout';
import AccountPanel from './pages/AccountPanel';
import { AdminReports, AdminSubscribers } from './pages/admin/placeholders';
import Backup from './pages/admin/Backup';
import Admins from './pages/admin/Admins';
import ImportPage from './pages/admin/import/ImportPage';
import AwaitingLink from './pages/admin/links/AwaitingLink';
import AdminHome from './pages/admin/Home';
import PendingList from './pages/admin/pending/PendingList';
import RequestReview from './pages/admin/pending/RequestReview';
import Archive from './pages/admin/Archive';
import Audit from './pages/admin/Audit';
import Settings from './pages/admin/settings/Settings';
import Marketers from './pages/admin/Marketers';
import ChangePassword from './pages/ChangePassword';
import Login from './pages/Login';
import Dashboard from './pages/marketer/Dashboard';
import Notifications from './pages/marketer/Notifications';
import RequestResult from './pages/marketer/RequestResult';
import Requests from './pages/marketer/Requests';
import SubscriberForm from './pages/marketer/subscriber/SubscriberForm';

/** Wrap one admin route in its §10 permission guard (specs/002 contracts/ui-routes.md). */
function page(key: PageKey, route: RouteObject): RouteObject {
  return { element: <RequirePage page={key} />, children: [route] };
}

// contracts/ui-routes.md
export const routes: RouteObject[] = [
  {
    // Any error thrown while rendering a page lands here (Arabic message, not the default screen).
    errorElement: <RouteError />,
    children: [
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
                      // specs/008: the result after «إرسال», and a reopened request.
                      { path: '/requests/:requestId', element: <RequestResult /> },
                      // specs/005: new-subscriber form. One route for /drafts/new and /drafts/{id}, so
                      // the form stays mounted when the URL is replaced after the first save.
                      { path: '/drafts/:draftId', element: <SubscriberForm /> },
                      { path: '/notifications', element: <Notifications /> },
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
                      page('pending', { path: 'pending', element: <PendingList /> }),
                      page('pending', { path: 'pending/:requestId', element: <RequestReview /> }),
                      page('awaiting_link', {
                        path: 'awaiting-link',
                        element: <AwaitingLink />,
                      }),
                      page('subscribers', { path: 'subscribers', element: <AdminSubscribers /> }),
                      page('marketers', { path: 'marketers', element: <Marketers /> }),
                      page('settings', { path: 'settings', element: <Settings /> }),
                      page('admins', { path: 'admins', element: <Admins /> }),
                      page('reports', { path: 'reports', element: <AdminReports /> }),
                      page('import', { path: 'import', element: <ImportPage /> }),
                      page('backup', { path: 'backup', element: <Backup /> }),
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
    ],
  },
];

export const router = createBrowserRouter(routes);
