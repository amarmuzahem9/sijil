/**
 * Sign-in over the form when the session ends mid-form (specs/005 research.md R3, analysis U2).
 * The form stays mounted, so unsaved values are kept. Signing in as the same account resumes
 * the saves; another account discards the form (one marketer's data never reaches another).
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { useState } from 'react';
import type { FormEvent } from 'react';

import { useAuth } from '../../../auth/AuthProvider';
import { ApiError, NETWORK_ERROR_MESSAGE } from '../../../lib/api';
import { normalizePhone } from '../../../lib/phone';

export const SESSION_ENDED_TITLE = 'انتهت الجلسة، سجّل الدخول للمتابعة';

export function SignInDialog({
  open,
  expectedUserId,
  onSameUser,
  onOtherUser,
}: {
  open: boolean;
  expectedUserId: number | null;
  onSameUser: () => void;
  onOtherUser: () => void;
}) {
  const { login } = useAuth();
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (normalizePhone(phone) === null) {
      setError('رقم غير صالح');
      return;
    }
    if (!password) {
      setError('أدخل كلمة السر');
      return;
    }
    setBusy(true);
    try {
      const user = await login(phone, password);
      setPassword('');
      if (expectedUserId !== null && user.id === expectedUserId) onSameUser();
      else onOtherUser();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} fullWidth maxWidth="xs" aria-labelledby="session-ended-title">
      <form onSubmit={onSubmit} noValidate>
        <DialogTitle id="session-ended-title">{SESSION_ENDED_TITLE}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Alert severity="info">
              البيانات التي أدخلتها ما زالت على الشاشة وستُحفظ بعد الدخول.
            </Alert>
            <TextField
              label="رقم الهاتف"
              name="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="username"
              slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'tel' } }}
            />
            <TextField
              label="كلمة السر"
              name="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              slotProps={{ htmlInput: { dir: 'ltr' } }}
            />
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button type="submit" variant="contained" disabled={busy}>
            دخول
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
