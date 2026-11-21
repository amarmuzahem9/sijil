import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';
import HomeOutlined from '@mui/icons-material/HomeOutlined';
import ListAltOutlined from '@mui/icons-material/ListAltOutlined';
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';

import { AppShell } from './AppShell';
import type { NavItem } from './AppShell';

/** docs/system.md §4.1: الرئيسية، الطلبات، الإشعارات، حسابي. */
const MARKETER_ITEMS: NavItem[] = [
  { label: 'الرئيسية', path: '/', icon: <HomeOutlined />, exact: true },
  { label: 'الطلبات', path: '/requests', icon: <ListAltOutlined /> },
  { label: 'الإشعارات', path: '/notifications', icon: <NotificationsOutlined /> },
  { label: 'حسابي', path: '/account', icon: <AccountCircleOutlined /> },
];

export default function MarketerLayout() {
  return <AppShell items={MARKETER_ITEMS} mobileNav="bottom" />;
}
