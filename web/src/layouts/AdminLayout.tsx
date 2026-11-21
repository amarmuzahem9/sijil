import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';
import AdminPanelSettingsOutlined from '@mui/icons-material/AdminPanelSettingsOutlined';
import BackupOutlined from '@mui/icons-material/BackupOutlined';
import BadgeOutlined from '@mui/icons-material/BadgeOutlined';
import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import FactCheckOutlined from '@mui/icons-material/FactCheckOutlined';
import FileUploadOutlined from '@mui/icons-material/FileUploadOutlined';
import HistoryOutlined from '@mui/icons-material/HistoryOutlined';
import HourglassTopOutlined from '@mui/icons-material/HourglassTopOutlined';
import LinkOutlined from '@mui/icons-material/LinkOutlined';
import PeopleAltOutlined from '@mui/icons-material/PeopleAltOutlined';
import SettingsOutlined from '@mui/icons-material/SettingsOutlined';

import { useAuth } from '../auth/AuthProvider';
import { AppShell } from './AppShell';
import type { NavItem } from './AppShell';

/** The 11 admin pages of docs/system.md §10, in order. */
const ADMIN_PAGES: (NavItem & { superAdminOnly?: boolean })[] = [
  { label: 'الرئيسية', path: '/admin', icon: <DashboardOutlined />, exact: true },
  { label: 'طلبات بالانتظار', path: '/admin/pending', icon: <HourglassTopOutlined /> },
  { label: 'بانتظار الربط', path: '/admin/awaiting-link', icon: <LinkOutlined /> },
  { label: 'المشتركون', path: '/admin/subscribers', icon: <PeopleAltOutlined /> },
  { label: 'المسوّقون', path: '/admin/marketers', icon: <BadgeOutlined /> },
  { label: 'الإعدادات', path: '/admin/settings', icon: <SettingsOutlined /> },
  {
    label: 'الأدمنية والصلاحيات',
    path: '/admin/admins',
    icon: <AdminPanelSettingsOutlined />,
    superAdminOnly: true,
  },
  { label: 'التقارير والتصدير', path: '/admin/reports', icon: <FactCheckOutlined /> },
  { label: 'الاستيراد', path: '/admin/import', icon: <FileUploadOutlined /> },
  { label: 'النسخ الاحتياطي', path: '/admin/backup', icon: <BackupOutlined /> },
  { label: 'سجل العمليات', path: '/admin/audit', icon: <HistoryOutlined /> },
];

const ACCOUNT_ITEM: NavItem = {
  label: 'حسابي',
  path: '/admin/account',
  icon: <AccountCircleOutlined />,
};

export default function AdminLayout() {
  const { user } = useAuth();
  const items = ADMIN_PAGES.filter((p) => !p.superAdminOnly || user?.role === 'super_admin');
  return <AppShell items={items} footerItems={[ACCOUNT_ITEM]} mobileNav="menu" />;
}
