import LockResetOutlined from '@mui/icons-material/LockResetOutlined';
import LogoutOutlined from '@mui/icons-material/LogoutOutlined';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { ROLE_LABELS } from '../auth/roles';

/** «حسابي» for both marketers and admins. */
export default function AccountPanel() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;

  return (
    <>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        حسابي
      </Typography>
      <Paper variant="outlined" sx={{ p: 3, maxWidth: 480 }}>
        <Stack spacing={1.5} sx={{ mb: 3 }}>
          <Typography>
            <Typography component="span" color="text.secondary">
              الاسم:{' '}
            </Typography>
            {user.name}
          </Typography>
          <Typography>
            <Typography component="span" color="text.secondary">
              الهاتف:{' '}
            </Typography>
            <bdi dir="ltr">{user.phone}</bdi>
          </Typography>
          <Typography>
            <Typography component="span" color="text.secondary">
              الدور:{' '}
            </Typography>
            {ROLE_LABELS[user.role]}
          </Typography>
        </Stack>
        <Stack spacing={1.5}>
          <Button
            component={Link}
            to="/change-password"
            variant="outlined"
            startIcon={<LockResetOutlined />}
          >
            تغيير كلمة السر
          </Button>
          <Button
            color="error"
            variant="contained"
            startIcon={<LogoutOutlined />}
            onClick={async () => {
              await logout();
              navigate('/login', { replace: true });
            }}
          >
            تسجيل الخروج
          </Button>
        </Stack>
      </Paper>
    </>
  );
}
