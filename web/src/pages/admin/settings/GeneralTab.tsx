import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import InputAdornment from '@mui/material/InputAdornment';
import Paper from '@mui/material/Paper';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../../../lib/api';
import { parseMoney } from '../../../lib/money';
import { generalApi } from '../../../lib/settings';

const MIN = 5;
const MAX = 1440;
const RANGE_ERROR = 'المدة يجب أن تكون من 5 إلى 1,440 دقيقة';

function GeneralForm({ initial }: { initial: number }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState(String(initial));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const value = parseMoney(text);
  const localError = value === null || value < MIN || value > MAX ? RANGE_ERROR : null;

  async function save() {
    if (localError || value === null) {
      setError(localError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await generalApi.update(value);
      setText(String(saved.otp_validity_minutes));
      setNotice('تم الحفظ');
      await queryClient.invalidateQueries({ queryKey: ['settings', 'general'] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, maxWidth: 480 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <TextField
        label="مدة صلاحية رمز التحقق"
        value={text}
        onChange={(e) => setText(e.target.value)}
        error={localError !== null}
        helperText={localError ?? 'من 5 إلى 1,440 دقيقة (24 ساعة). الافتراضي 60.'}
        fullWidth
        slotProps={{
          htmlInput: { dir: 'ltr', inputMode: 'numeric' },
          input: { endAdornment: <InputAdornment position="end">دقيقة</InputAdornment> },
        }}
      />
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
        <Button variant="contained" onClick={save} disabled={busy}>
          حفظ
        </Button>
      </Box>
      <Snackbar
        open={notice !== null}
        autoHideDuration={3000}
        onClose={() => setNotice(null)}
        message={notice}
      />
    </Paper>
  );
}

/** «عام» (specs/004 US4): OTP validity in minutes. */
export default function GeneralTab() {
  const general = useQuery({ queryKey: ['settings', 'general'], queryFn: generalApi.get });
  if (general.isPending) return <CircularProgress aria-label="جارٍ التحميل" />;
  if (general.isError) return <Alert severity="error">{general.error.message}</Alert>;
  return <GeneralForm initial={general.data.otp_validity_minutes} />;
}
