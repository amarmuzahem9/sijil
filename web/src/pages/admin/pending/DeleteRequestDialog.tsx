/**
 * «حذف» (docs/system.md v1.15 §7.4, specs/011 FR-004 to FR-006): a fixed reason (no free text)
 * and the request number typed back, in Western or Arabic-Indic digits. The final button stays
 * disabled until both are right; the server checks the number again.
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormLabel from '@mui/material/FormLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { useId, useState } from 'react';

import type { DeleteBody } from '../../../lib/adminRequests';
import { DELETION_REASON_LABELS, type DeletionReason } from '../../../lib/labels';
import { parseRequestNumber } from '../../../lib/requestNumber';

const REASONS = Object.keys(DELETION_REASON_LABELS) as DeletionReason[];

export function DeleteRequestDialog({
  open,
  numberLabel,
  busy = false,
  error = null,
  onSubmit,
  onClose,
}: {
  open: boolean;
  numberLabel: string;
  busy?: boolean;
  /** The server's Arabic message, if the deletion was refused. */
  error?: string | null;
  onSubmit: (body: DeleteBody) => void;
  onClose: () => void;
}) {
  const reasonsId = useId();
  const [reason, setReason] = useState<DeletionReason | null>(null);
  const [typed, setTyped] = useState('');
  const expected = parseRequestNumber(numberLabel);
  const ready = reason !== null && expected !== null && parseRequestNumber(typed) === expected;

  function send() {
    if (!reason || !ready) return;
    onSubmit({ reason, confirm_number: typed });
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        حذف الطلب <span dir="ltr">{numberLabel}</span>
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <Alert severity="warning">
            ستُمسح البيانات الشخصية وصور البطاقة نهائياً ولا يمكن التراجع
          </Alert>
          <div>
            <FormLabel id={reasonsId}>سبب الحذف</FormLabel>
            <RadioGroup
              aria-labelledby={reasonsId}
              value={reason ?? ''}
              onChange={(e) => setReason(e.target.value as DeletionReason)}
            >
              {REASONS.map((code) => (
                <FormControlLabel
                  key={code}
                  value={code}
                  control={<Radio />}
                  label={DELETION_REASON_LABELS[code]}
                />
              ))}
            </RadioGroup>
          </div>
          <TextField
            label="اكتب رقم الطلب للتأكيد"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            helperText={`اكتب ${numberLabel} أو الرقم فقط`}
            autoComplete="off"
            fullWidth
            slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'numeric', maxLength: 40 } }}
          />
          {error && (
            <Alert severity="error" variant="outlined">
              {error}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          إلغاء
        </Button>
        <Button color="error" variant="contained" onClick={send} disabled={!ready || busy}>
          حذف نهائي
        </Button>
      </DialogActions>
    </Dialog>
  );
}
