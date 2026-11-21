import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import { useState } from 'react';
import type { FormEvent } from 'react';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../lib/api';
import type { Permission } from '../lib/labels';
import { normalizePhone } from '../lib/phone';
import { PasswordField } from './PasswordField';
import { PermissionSwitches } from './PermissionSwitches';

export interface AccountFormValues {
  name: string;
  phone: string;
  temporary_password: string;
  permissions: Permission[];
}

interface AccountDialogProps {
  open: boolean;
  title: string;
  /** Create mode asks for a temporary password; edit mode does not. */
  mode: 'create' | 'edit';
  withPermissions: boolean;
  initial?: Partial<AccountFormValues>;
  onSubmit: (values: AccountFormValues) => Promise<void>;
  onClose: () => void;
}

const MIN_PASSWORD = 8;

/** Add or edit an admin or a marketer (specs/002 contracts/ui-routes.md). */
export function AccountDialog(props: AccountDialogProps) {
  // Mounted only while open, so no previous value (or password) lingers between uses.
  if (!props.open) return null;
  return <AccountForm {...props} />;
}

function AccountForm({
  title,
  mode,
  withPermissions,
  initial,
  onSubmit,
  onClose,
}: AccountDialogProps) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const [name, setName] = useState(initial?.name ?? '');
  const [phone, setPhone] = useState(initial?.phone ?? '');
  const [password, setPassword] = useState('');
  const [permissions, setPermissions] = useState<Permission[]>(initial?.permissions ?? []);
  const [touched, setTouched] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const trimmed = name.trim();
  const nameError =
    trimmed.length < 2 || trimmed.length > 100 ? 'الاسم يجب أن يكون بين 2 و100 حرف' : null;
  const phoneError = normalizePhone(phone) ? null : 'رقم غير صالح';
  const passwordError =
    mode === 'create' && password.length < MIN_PASSWORD
      ? 'كلمة السر يجب أن تكون 8 أحرف على الأقل'
      : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (nameError || phoneError || passwordError) return;
    setBusy(true);
    setServerError(null);
    try {
      await onSubmit({ name: trimmed, phone, temporary_password: password, permissions });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      onClose={busy ? undefined : onClose}
      fullScreen={fullScreen}
      fullWidth
      maxWidth="sm"
    >
      <form onSubmit={submit} noValidate>
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {serverError && <Alert severity="error">{serverError}</Alert>}
            <TextField
              label="الاسم"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={touched && Boolean(nameError)}
              helperText={touched ? nameError : null}
              required
              fullWidth
              autoFocus
            />
            <TextField
              label="رقم الهاتف"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              error={touched && Boolean(phoneError)}
              helperText={touched ? phoneError : null}
              required
              fullWidth
              slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'tel' } }}
            />
            {mode === 'create' && (
              <PasswordField
                label="كلمة السر المؤقتة"
                value={password}
                onChange={setPassword}
                error={touched ? passwordError : null}
              />
            )}
            {withPermissions && (
              <PermissionSwitches value={permissions} onChange={setPermissions} disabled={busy} />
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={busy}>
            إلغاء
          </Button>
          <Button type="submit" variant="contained" disabled={busy}>
            حفظ
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
