import { createBrowserRouter, Navigate } from 'react-router-dom';

import {
  MustChangePasswordGate,
  RequireAnonymous,
  RequireAuth,
  RequireRole,
} from './auth/guards';
import { ADMIN_ROLES } from './auth/roles';
import AdminLayout from './layouts/AdminLayout';
import MarketerLayout from './layouts/MarketerLayout';
import AccountPanel from './pages/AccountPanel';
import {
  AdminAdmins,
  AdminAudit,
  AdminAwaitingLink,
  AdminBackup,
  AdminHome,
  AdminImport,
  AdminMarketers,
  AdminPending,
  AdminReports,
  AdminSettings,
  AdminSubscribers,
} from './pages/admin/placeholders';
import ChangePassword from './pages/ChangePassword';
import Login from './pages/Login';
import Dashboard from './pages/marketer/Dashboard';
import { MarketerNotifications, MarketerRequests } from './pages/marketer/placeholders';

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
                  { path: '/requests', element: <MarketerRequests /> },
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
                  { index: true, element: <AdminHome /> },
                  { path: 'pending', element: <AdminPending /> },
                  { path: 'awaiting-link', element: <AdminAwaitingLink /> },
                  { path: 'subscribers', element: <AdminSubscribers /> },
                  { path: 'marketers', element: <AdminMarketers /> },
                  { path: 'settings', element: <AdminSettings /> },
                  {
                    element: <RequireRole roles={['super_admin']} />,
                    children: [{ path: 'admins', element: <AdminAdmins /> }],
                  },
                  { path: 'reports', element: <AdminReports /> },
                  { path: 'import', element: <AdminImport /> },
                  { path: 'backup', element: <AdminBackup /> },
                  { path: 'audit', element: <AdminAudit /> },
                  { path: 'account', element: <AccountPanel /> },
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
