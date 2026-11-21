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

import { ApiError, NETWORK_ERROR_MESSAGE } from '../lib/api';

interface NameDialogProps {
  open: boolean;
  initial: string;
  onSubmit: (name: string) => Promise<void>;
  onClose: () => void;
}

/** «تعديل الاسم» for the main admin in «حسابي» (docs/system.md §3.2). */
export function NameDialog(props: NameDialogProps) {
  if (!props.open) return null;
  return <NameForm {...props} />;
}

function NameForm({ initial, onSubmit, onClose }: NameDialogProps) {
  const [name, setName] = useState(initial);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const trimmed = name.trim();
  const localError =
    trimmed.length < 2 || trimmed.length > 100 ? 'الاسم يجب أن يكون بين 2 و100 حرف' : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (localError) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(trimmed);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onClose={busy ? undefined : onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit} noValidate>
        <DialogTitle>تعديل الاسم</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="الاسم"
              value={name}
              onChange={(e) => setName(e.target.value)}
              error={touched && Boolean(localError)}
              helperText={touched ? localError : null}
              required
              fullWidth
              autoFocus
            />
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
