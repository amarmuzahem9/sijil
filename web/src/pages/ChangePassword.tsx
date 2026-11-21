import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';
import { landingPath } from '../auth/roles';
import { BrandMark } from '../components/BrandMark';
import { ApiError, apiFetch, NETWORK_ERROR_MESSAGE } from '../lib/api';
import type { TokenResponse } from '../lib/api';

const MIN_LENGTH = 8;

export default function ChangePassword() {
  const { user, setSession, logout } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const forced = Boolean(user?.must_change_password);

  function validate(): string | null {
    if (!current) return 'أدخل كلمة السر الحالية';
    if (next.length < MIN_LENGTH) return 'كلمة السر يجب أن تكون 8 أحرف على الأقل';
    if (next === current) return 'كلمة السر الجديدة يجب أن تختلف عن الحالية';
    if (next !== confirm) return 'تأكيد كلمة السر غير مطابق';
    return null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const problem = validate();
    setError(problem);
    if (problem) return;
    setBusy(true);
    try {
      const tokens = await apiFetch<TokenResponse>('/api/auth/change-password', {
        method: 'POST',
        body: { current_password: current, new_password: next },
      });
      setSession(tokens);
      navigate(landingPath(tokens.user), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', px: 2 }}>
      <Paper component="main" elevation={2} sx={{ width: '100%', maxWidth: 420, p: { xs: 3, sm: 4 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <BrandMark size={40} />
        </Box>
        <Typography component="h1" variant="h6" align="center" sx={{ mb: 1 }}>
          تغيير كلمة السر
        </Typography>
        {forced && (
          <Alert severity="info" sx={{ mb: 2 }}>
            مرحباً {user?.name}، يجب تغيير كلمة السر قبل المتابعة.
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} role="alert">
            {error}
          </Alert>
        )}
        <Box component="form" onSubmit={onSubmit} noValidate sx={{ display: 'grid', gap: 2 }}>
          <TextField
            label="كلمة السر الحالية"
            name="current_password"
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            required
          />
          <TextField
            label="كلمة السر الجديدة"
            name="new_password"
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            helperText="8 أحرف على الأقل"
            autoComplete="new-password"
            required
          />
          <TextField
            label="تأكيد كلمة السر الجديدة"
            name="confirm_password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            required
          />
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={busy}
            startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}
          >
            حفظ
          </Button>
          {forced && (
            <Button variant="text" color="inherit" onClick={() => logout()}>
              تسجيل الخروج
            </Button>
          )}
        </Box>
      </Paper>
    </Box>
  );
}
