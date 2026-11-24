/**
 * «التراجع عن الربط» (docs/system.md v1.18 §6.5, specs/013 FR-008, FR-016): a reason from the fixed
 * list, no free text, so nothing personal reaches the marketer's notification or the audit.
 */
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import { UNLINK_REASON_LABELS, type UnlinkReason } from '../../../lib/labels';
import type { LinkRow } from '../../../lib/links';

const REASONS = Object.keys(UNLINK_REASON_LABELS) as UnlinkReason[];

export function UnlinkDialog({
  row,
  busy = false,
  onConfirm,
  onClose,
}: {
  row: LinkRow | null;
  busy?: boolean;
  onConfirm: (reason: UnlinkReason) => void;
  onClose: () => void;
}) {
  // The parent keys the dialog by row, so a new row starts with no reason chosen.
  const [reason, setReason] = useState<UnlinkReason | null>(null);

  return (
    <Dialog open={row !== null} onClose={busy ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>التراجع عن الربط؟</DialogTitle>
      <DialogContent>
        {row && (
          <>
            <Typography dir="ltr" sx={{ fontWeight: 700, textAlign: 'right' }}>
              {row.number_label}
            </Typography>
            <Typography>{row.full_name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              يرجع الطلب «مقبول (بانتظار الربط)» ولا يُحتسب للمسوّق، ويصله إشعار بالسبب.
            </Typography>
          </>
        )}
        <RadioGroup
          aria-label="سبب التراجع"
          value={reason ?? ''}
          onChange={(e) => setReason(e.target.value as UnlinkReason)}
          sx={{ mt: 1 }}
        >
          {REASONS.map((code) => (
            <FormControlLabel
              key={code}
              value={code}
              control={<Radio />}
              label={UNLINK_REASON_LABELS[code]}
            />
          ))}
        </RadioGroup>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          إلغاء
        </Button>
        <Button
          variant="contained"
          color="warning"
          disabled={busy || reason === null}
          onClick={() => reason && onConfirm(reason)}
        >
          تأكيد التراجع
        </Button>
      </DialogActions>
    </Dialog>
  );
}
