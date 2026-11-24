/**
 * «تم الربط» confirmation (specs/013 FR-005): the admin checks the number and the username against
 * SAS before confirming.
 */
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Typography from '@mui/material/Typography';

import type { LinkRow } from '../../../lib/links';

export function LinkConfirmDialog({
  row,
  busy = false,
  onConfirm,
  onClose,
}: {
  row: LinkRow | null;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog open={row !== null} onClose={busy ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>تأكيد الربط؟</DialogTitle>
      <DialogContent>
        {row && (
          <>
            <Typography dir="ltr" sx={{ fontWeight: 700, textAlign: 'right' }}>
              {row.number_label}
            </Typography>
            <Typography>{row.full_name}</Typography>
            <Typography dir="ltr" sx={{ textAlign: 'right' }}>
              {row.username}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              تأكد أن المشترك مربوط فعلياً في SAS قبل التأكيد.
            </Typography>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          إلغاء
        </Button>
        <Button variant="contained" color="success" onClick={onConfirm} disabled={busy}>
          تأكيد الربط
        </Button>
      </DialogActions>
    </Dialog>
  );
}
