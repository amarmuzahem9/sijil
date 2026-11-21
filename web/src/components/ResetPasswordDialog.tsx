import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Stack from '@mui/material/Stack';
import { useState } from 'react';
import type { FormEvent } from 'react';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../lib/api';
import { PasswordField } from './PasswordField';

interface ResetPasswordDialogProps {
  open: boolean;
  /** «المسوّق» or «الأدمن». */
  subject: string;
  name: string;
  onSubmit: (temporaryPassword: string) => Promise<void>;
  onClose: () => void;
}

/** This dialog is the confirmation for a reset (spec FR-021): there is no second step. */
export function ResetPasswordDialog(props: ResetPasswordDialogProps) {
  if (!props.open) return null;
  return <ResetForm {...props} />;
}

function ResetForm({ subject, name, onSubmit, onClose }: ResetPasswordDialogProps) {
  const [password, setPassword] = useState('');
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const localError = password.length < 8 ? 'كلمة السر يجب أن تكون 8 أحرف على الأقل' : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (localError) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onClose={busy ? undefined : onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit} noValidate>
        <DialogTitle>تصفير كلمة سر {name}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <DialogContentText>
              سيُطلب من {subject} تغييرها عند الدخول، وستنتهي جلساته الحالية.
            </DialogContentText>
            {error && <Alert severity="error">{error}</Alert>}
            <PasswordField
              label="كلمة السر المؤقتة الجديدة"
              value={password}
              onChange={setPassword}
              error={touched ? localError : null}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>
            إلغاء
          </Button>
          <Button type="submit" color="warning" variant="contained" disabled={busy}>
            تصفير كلمة السر
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
