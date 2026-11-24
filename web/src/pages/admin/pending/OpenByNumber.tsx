/**
 * «فتح طلب برقمه» (docs/system.md v1.15 §10 item 2, specs/011 FR-022, R8): opens the file of any
 * submitted request by its number, in any status. This is how a rejected request is reached until
 * the subscriber search (018). The number may be typed as «T3C-1005», «1005» or «١٠٠٥».
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { findByNumber } from '../../../lib/adminRequests';
import { parseRequestNumber } from '../../../lib/requestNumber';

export function OpenByNumber() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = parseRequestNumber(text) !== null;

  async function open(e?: FormEvent) {
    e?.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { id } = await findByNumber(text.trim());
      navigate(`/admin/pending/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <Stack spacing={1} component="form" onSubmit={(e) => void open(e)}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
        <TextField
          label="فتح طلب برقمه"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setError(null);
          }}
          size="small"
          autoComplete="off"
          placeholder="T3C-1005"
          sx={{ flex: '1 1 auto', maxWidth: 320 }}
          slotProps={{ htmlInput: { dir: 'ltr', maxLength: 40 } }}
        />
        <Button type="submit" variant="outlined" disabled={!ready || busy}>
          فتح
        </Button>
      </Stack>
      {error && (
        <Alert severity="warning" variant="outlined" sx={{ maxWidth: 400 }}>
          {error}
        </Alert>
      )}
    </Stack>
  );
}
