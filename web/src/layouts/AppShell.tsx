import MenuIcon from '@mui/icons-material/Menu';
import AppBar from '@mui/material/AppBar';
import BottomNavigation from '@mui/material/BottomNavigation';
import BottomNavigationAction from '@mui/material/BottomNavigationAction';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Paper from '@mui/material/Paper';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { ROLE_LABELS } from '../auth/roles';
import { BrandMark } from '../components/BrandMark';

export interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
  /** Match only the exact path (for index routes like "/" and "/admin"). */
  exact?: boolean;
}

interface AppShellProps {
  items: NavItem[];
  /** Phone-width navigation: bottom bar (marketer) or slide-in menu (admin). */
  mobileNav: 'bottom' | 'menu';
  /** Extra items shown under the main list (e.g. the account page). */
  footerItems?: NavItem[];
}

const SIDEBAR_WIDTH = 264;
const BOTTOM_BAR_HEIGHT = 64;

function isActive(item: NavItem, pathname: string): boolean {
  return item.exact ? pathname === item.path : pathname.startsWith(item.path);
}

function NavList({
  items,
  footerItems,
  onNavigate,
}: {
  items: NavItem[];
  footerItems?: NavItem[];
  onNavigate?: () => void;
}) {
  const { pathname } = useLocation();
  const render = (item: NavItem) => (
    <ListItemButton
      key={item.path}
      component={Link}
      to={item.path}
      selected={isActive(item, pathname)}
      onClick={onNavigate}
      sx={{ borderRadius: 2, mx: 1, mb: 0.5 }}
    >
      <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
      <ListItemText primary={item.label} />
    </ListItemButton>
  );
  return (
    <>
      <List aria-label="صفحات التطبيق">{items.map(render)}</List>
      {footerItems && footerItems.length > 0 && (
        <List sx={{ mt: 'auto', borderTop: 1, borderColor: 'divider', pt: 1 }}>
          {footerItems.map(render)}
        </List>
      )}
    </>
  );
}

export function AppShell({ items, mobileNav, footerItems = [] }: AppShellProps) {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up('md'), { noSsr: true });
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const roleLabel = user ? ROLE_LABELS[user.role] : '';

  const identity = (
    <Box data-testid="user-identity" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography sx={{ fontWeight: 600 }} noWrap>
        {user?.name}
      </Typography>
      <Chip size="small" color="primary" variant="outlined" label={roleLabel} />
    </Box>
  );

  if (desktop) {
    // Large screens: permanent sidebar. In RTL the first flex child sits on the right.
    return (
      <Box sx={{ display: 'flex', minHeight: '100dvh', bgcolor: 'background.default' }}>
        <Box
          component="nav"
          aria-label="القائمة الرئيسية"
          data-testid="sidebar"
          sx={{
            width: SIDEBAR_WIDTH,
            flexShrink: 0,
            position: 'sticky',
            top: 0,
            height: '100dvh',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: 'background.paper',
            // Written as "Right": the RTL style plugin flips it to the side facing the content.
            borderRight: 1,
            borderColor: 'divider',
            overflowY: 'auto',
          }}
        >
          <Toolbar>
            <BrandMark size={36} />
          </Toolbar>
          <NavList items={items} footerItems={footerItems} />
        </Box>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <AppBar
            position="sticky"
            color="inherit"
            elevation={0}
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Toolbar>{identity}</Toolbar>
          </AppBar>
          <Box component="main" sx={{ p: 3, maxWidth: 1100 }}>
            <Outlet />
          </Box>
        </Box>
      </Box>
    );
  }

  const bottomItems = [...items, ...footerItems];
  const bottomIndex = bottomItems.findIndex((item) => isActive(item, pathname));

  return (
    <Box sx={{ minHeight: '100dvh', bgcolor: 'background.default' }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 1 }}>
          {mobileNav === 'menu' && (
            <IconButton edge="start" aria-label="فتح القائمة" onClick={() => setMenuOpen(true)}>
              <MenuIcon />
            </IconButton>
          )}
          <BrandMark size={30} />
          <Box sx={{ flexGrow: 1 }} />
          <Typography variant="body2" color="text.secondary" noWrap>
            {user?.name}
          </Typography>
        </Toolbar>
      </AppBar>

      {mobileNav === 'menu' && (
        <Drawer anchor="right" open={menuOpen} onClose={() => setMenuOpen(false)}>
          <Box
            component="nav"
            aria-label="القائمة الرئيسية"
            sx={{ width: SIDEBAR_WIDTH, height: '100%', display: 'flex', flexDirection: 'column' }}
          >
            <Toolbar>{identity}</Toolbar>
            <NavList items={items} footerItems={footerItems} onNavigate={() => setMenuOpen(false)} />
          </Box>
        </Drawer>
      )}

      <Box
        component="main"
        sx={{ p: 2, pb: mobileNav === 'bottom' ? `${BOTTOM_BAR_HEIGHT + 24}px` : 2 }}
      >
        <Outlet />
      </Box>

      {mobileNav === 'bottom' && (
        <Paper
          component="nav"
          aria-label="القائمة السفلية"
          data-testid="bottom-nav"
          elevation={8}
          sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: (t) => t.zIndex.appBar }}
        >
          <BottomNavigation showLabels value={bottomIndex} sx={{ height: BOTTOM_BAR_HEIGHT }}>
            {bottomItems.map((item) => (
              <BottomNavigationAction
                key={item.path}
                label={item.label}
                icon={item.icon}
                component={Link}
                to={item.path}
              />
            ))}
          </BottomNavigation>
        </Paper>
      )}
    </Box>
  );
}
