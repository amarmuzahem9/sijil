import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import { Navigate, Outlet } from 'react-router-dom';

import type { Role } from '../lib/api';
import { canAccess } from './access';
import type { PageKey } from './access';
import { useAuth } from './AuthProvider';
import { landingPath } from './roles';

function FullScreenSpinner() {
  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center' }}>
      <CircularProgress aria-label="جارٍ التحميل" />
    </Box>
  );
}

/** Signed-in users only; others go to /login. */
export function RequireAuth() {
  const { status } = useAuth();
  if (status === 'loading') return <FullScreenSpinner />;
  if (status === 'anonymous') return <Navigate to="/login" replace />;
  return <Outlet />;
}

/** Signed-out users only (the login page); signed-in users go to their landing page. */
export function RequireAnonymous() {
  const { status, user } = useAuth();
  if (status === 'loading') return <FullScreenSpinner />;
  if (status === 'authenticated' && user) return <Navigate to={landingPath(user)} replace />;
  return <Outlet />;
}

/** While a password change is pending, every page redirects to /change-password (FR-011). */
export function MustChangePasswordGate() {
  const { user } = useAuth();
  if (user?.must_change_password) return <Navigate to="/change-password" replace />;
  return <Outlet />;
}

/** Wrong role → that user's own landing page (a marketer never sees admin pages). */
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={landingPath(user)} replace />;
  return <Outlet />;
}

/** Admin page the caller may not open → /admin, with a «ليست لديك صلاحية» notice (002). */
export function RequirePage({ page }: { page: PageKey }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!canAccess(user, page)) return <Navigate to="/admin" replace state={{ denied: true }} />;
  return <Outlet />;
}
