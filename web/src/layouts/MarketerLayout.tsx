import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';
import HomeOutlined from '@mui/icons-material/HomeOutlined';
import ListAltOutlined from '@mui/icons-material/ListAltOutlined';
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';
import Badge from '@mui/material/Badge';
import { useQuery } from '@tanstack/react-query';

import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { notificationKeys, UNREAD_POLL_MS, unreadCount } from '../lib/notifications';
import { AppShell } from './AppShell';
import type { NavItem } from './AppShell';

/** The bell with the unread count (specs/012 FR-020): nothing at 0. */
function NotificationsIcon({ count }: { count: number }) {
  return (
    <Badge
      color="error"
      badgeContent={count > 0 ? <span data-testid="unread-badge">{count}</span> : null}
      max={99}
      invisible={count === 0}
      overlap="circular"
    >
      <NotificationsOutlined />
    </Badge>
  );
}

export default function MarketerLayout() {
  const { refreshUser } = useAuth();
  const { pathname } = useLocation();
  // Each navigation reaches the server, so a deactivation or reset ends the session on the
  // marketer's next tap (specs/002 FR-015), even on pages that load no data yet.
  useEffect(() => {
    void refreshUser();
  }, [pathname, refreshUser]);

  // Asked every 15 s while the app is visible, and again on focus (research R6).
  const unread = useQuery({
    queryKey: notificationKeys.unread,
    queryFn: unreadCount,
    refetchInterval: UNREAD_POLL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
  const count = unread.data?.count ?? 0;

  /** docs/system.md §4.1: الرئيسية، الطلبات، الإشعارات، حسابي. */
  const items: NavItem[] = [
    { label: 'الرئيسية', path: '/', icon: <HomeOutlined />, exact: true },
    { label: 'الطلبات', path: '/requests', icon: <ListAltOutlined /> },
    { label: 'الإشعارات', path: '/notifications', icon: <NotificationsIcon count={count} /> },
    { label: 'حسابي', path: '/account', icon: <AccountCircleOutlined /> },
  ];

  return <AppShell items={items} mobileNav="bottom" />;
}
