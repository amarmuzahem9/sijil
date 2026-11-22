import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { landingPath } from '../auth/roles';
import { BrandMark } from '../components/BrandMark';
import { ApiError, NETWORK_ERROR_MESSAGE } from '../lib/api';
import { normalizePhone } from '../lib/phone';

export default function Login() {
  const { login, notice } = useAuth();
  const navigate = useNavigate();
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Lockout (423) / per-IP limit (429): keep the button disabled until the wait is over.
  const [blockedUntil, setBlockedUntil] = useState<number | null>(null);

  useEffect(() => {
    if (blockedUntil === null) return;
    const timer = setTimeout(() => setBlockedUntil(null), Math.max(0, blockedUntil - Date.now()));
    return () => clearTimeout(timer);
  }, [blockedUntil]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (normalizePhone(phone) === null) {
      setPhoneError('رقم غير صالح');
      return;
    }
    setPhoneError(null);
    if (!password) {
      setError('أدخل كلمة السر');
      return;
    }
    setBusy(true);
    try {
      const user = await login(phone, password);
      navigate(landingPath(user), { replace: true });
    } catch (err) {
      // Server messages are already Arabic and never echo the input.
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
      const wait = err instanceof ApiError ? Number(err.extra.retry_after_seconds) : NaN;
      if (Number.isFinite(wait) && wait > 0) setBlockedUntil(Date.now() + wait * 1000);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100dvh',
        display: 'grid',
        placeItems: 'center',
        px: 2,
        bgcolor: 'background.default',
      }}
    >
      <Paper
        component="main"
        elevation={2}
        sx={{ width: '100%', maxWidth: 400, p: { xs: 3, sm: 4 } }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <BrandMark size={48} />
        </Box>
        <Typography component="h1" variant="h6" align="center" sx={{ mb: 3 }}>
          تسجيل الدخول
        </Typography>

        {notice && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {notice}
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} role="alert">
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={onSubmit} noValidate sx={{ display: 'grid', gap: 2 }}>
          <TextField
            label="رقم الهاتف"
            name="phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            error={Boolean(phoneError)}
            helperText={phoneError ?? 'مثال: 07801234567'}
            autoComplete="username"
            required
            fullWidth
            slotProps={{
              htmlInput: { inputMode: 'tel', dir: 'ltr', style: { textAlign: 'right' } },
            }}
          />
          <TextField
            label="كلمة السر"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            fullWidth
          />
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={busy || blockedUntil !== null}
            startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}
          >
            دخول
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
