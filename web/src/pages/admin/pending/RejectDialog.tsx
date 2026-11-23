/**
 * «رفض» (docs/system.md v1.14 §6.4, specs/010 FR-008, FR-019): one of the fixed reasons, or
 * «سبب آخر» with the admin's own note (3 to 300 characters). The marketer reads the reason as
 * written, so the note carries a privacy hint.
 */
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import { useState } from 'react';

import type { RejectBody, RejectionReason } from '../../../lib/adminRequests';
import {
  REJECTION_NOTE_MAX,
  REJECTION_NOTE_MIN,
  REJECTION_REASON_LABELS,
} from '../../../lib/labels';

const REASONS = Object.keys(REJECTION_REASON_LABELS) as RejectionReason[];

export function RejectDialog({
  open,
  numberLabel,
  busy = false,
  onSubmit,
  onClose,
}: {
  open: boolean;
  numberLabel: string;
  busy?: boolean;
  onSubmit: (body: RejectBody) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState<RejectionReason | null>(null);
  const [note, setNote] = useState('');
  const trimmed = note.trim();
  const ready =
    reason !== null &&
    (reason !== 'other' ||
      (trimmed.length >= REJECTION_NOTE_MIN && trimmed.length <= REJECTION_NOTE_MAX));

  function send() {
    if (!reason || !ready) return;
    onSubmit(reason === 'other' ? { reason, note: trimmed } : { reason });
  }

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>رفض الطلب {numberLabel}</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          <RadioGroup
            aria-label="اختر سبب الرفض"
            value={reason ?? ''}
            onChange={(e) => setReason(e.target.value as RejectionReason)}
          >
            {REASONS.map((code) => (
              <FormControlLabel
                key={code}
                value={code}
                control={<Radio />}
                label={REJECTION_REASON_LABELS[code]}
              />
            ))}
          </RadioGroup>
          {reason === 'other' && (
            <TextField
              label="سبب الرفض"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              required
              multiline
              minRows={2}
              fullWidth
              helperText="لا تكتب أي معلومة عن مشترك آخر"
              slotProps={{ htmlInput: { maxLength: REJECTION_NOTE_MAX } }}
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          إلغاء
        </Button>
        <Button color="error" variant="contained" onClick={send} disabled={!ready || busy}>
          تأكيد الرفض
        </Button>
      </DialogActions>
    </Dialog>
  );
}
