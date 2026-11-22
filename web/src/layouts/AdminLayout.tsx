import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';
import AdminPanelSettingsOutlined from '@mui/icons-material/AdminPanelSettingsOutlined';
import BackupOutlined from '@mui/icons-material/BackupOutlined';
import BadgeOutlined from '@mui/icons-material/BadgeOutlined';
import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import FactCheckOutlined from '@mui/icons-material/FactCheckOutlined';
import FileUploadOutlined from '@mui/icons-material/FileUploadOutlined';
import HistoryOutlined from '@mui/icons-material/HistoryOutlined';
import HourglassTopOutlined from '@mui/icons-material/HourglassTopOutlined';
import Inventory2Outlined from '@mui/icons-material/Inventory2Outlined';
import LinkOutlined from '@mui/icons-material/LinkOutlined';
import PeopleAltOutlined from '@mui/icons-material/PeopleAltOutlined';
import SettingsOutlined from '@mui/icons-material/SettingsOutlined';

import Snackbar from '@mui/material/Snackbar';
import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { canAccess } from '../auth/access';
import type { PageKey } from '../auth/access';
import { useAuth } from '../auth/AuthProvider';
import { AppShell } from './AppShell';
import type { NavItem } from './AppShell';

/** The 12 admin pages of docs/system.md §10, in order. */
const ADMIN_PAGES: (NavItem & { page: PageKey })[] = [
  { label: 'الرئيسية', page: 'home', path: '/admin', icon: <DashboardOutlined />, exact: true },
  {
    label: 'طلبات بالانتظار',
    page: 'pending',
    path: '/admin/pending',
    icon: <HourglassTopOutlined />,
  },
  {
    label: 'بانتظار الربط',
    page: 'awaiting_link',
    path: '/admin/awaiting-link',
    icon: <LinkOutlined />,
  },
  {
    label: 'المشتركون',
    page: 'subscribers',
    path: '/admin/subscribers',
    icon: <PeopleAltOutlined />,
  },
  { label: 'المسوّقون', page: 'marketers', path: '/admin/marketers', icon: <BadgeOutlined /> },
  { label: 'الإعدادات', page: 'settings', path: '/admin/settings', icon: <SettingsOutlined /> },
  {
    page: 'admins',
    label: 'الأدمنية والصلاحيات',
    path: '/admin/admins',
    icon: <AdminPanelSettingsOutlined />,
  },
  {
    label: 'التقارير والتصدير',
    page: 'reports',
    path: '/admin/reports',
    icon: <FactCheckOutlined />,
  },
  { label: 'الاستيراد', page: 'import', path: '/admin/import', icon: <FileUploadOutlined /> },
  { label: 'النسخ الاحتياطي', page: 'backup', path: '/admin/backup', icon: <BackupOutlined /> },
  { label: 'سجل العمليات', page: 'audit', path: '/admin/audit', icon: <HistoryOutlined /> },
  {
    label: 'أرشيف الحسابات',
    page: 'archive',
    path: '/admin/archive',
    icon: <Inventory2Outlined />,
  },
];

const ACCOUNT_ITEM: NavItem = {
  label: 'حسابي',
  path: '/admin/account',
  icon: <AccountCircleOutlined />,
};

/** Menu entries this user may open (the server enforces the same map). */
function visibleAdminPages(user: Parameters<typeof canAccess>[0]) {
  return ADMIN_PAGES.filter((p) => canAccess(user, p.page));
}

export default function AdminLayout() {
  const { user, refreshUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  // Set by <RequirePage> when this user opened a page they may not see.
  const denied = Boolean((location.state as { denied?: boolean } | null)?.denied);

  // Permission changes show on the next navigation, without signing out (SC-007).
  useEffect(() => {
    void refreshUser();
  }, [location.pathname, refreshUser]);

  return (
    <>
      <AppShell items={visibleAdminPages(user)} footerItems={[ACCOUNT_ITEM]} mobileNav="menu" />
      <Snackbar
        open={denied}
        autoHideDuration={4000}
        onClose={() => navigate(location.pathname, { replace: true, state: null })}
        message="ليست لديك صلاحية"
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </>
  );
}
