import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';
import HomeOutlined from '@mui/icons-material/HomeOutlined';
import ListAltOutlined from '@mui/icons-material/ListAltOutlined';
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';

import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
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
  const { refreshUser } = useAuth();
  const { pathname } = useLocation();
  // Each navigation reaches the server, so a deactivation or reset ends the session on the
  // marketer's next tap (specs/002 FR-015), even on pages that load no data yet.
  useEffect(() => {
    void refreshUser();
  }, [pathname, refreshUser]);

  return <AppShell items={MARKETER_ITEMS} mobileNav="bottom" />;
}
