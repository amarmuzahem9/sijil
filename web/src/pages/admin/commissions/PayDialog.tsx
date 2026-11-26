import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { amountText, payMonth, type ReportRow } from '../../../lib/commissions';

interface Props {
  month: string;
  row: ReportRow;
  onClose: () => void;
}

/**
 * «تم الدفع» (docs/system.md v1.23 §9; specs/017 FR-011, FR-012): shows the figures that will be
 * locked and sends exactly those; the server refuses when they changed. After success or a
 * refusal the month is reloaded, so the row shows what is true now.
 */
export default function PayDialog({ month, row, onClose }: Props) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => payMonth(month, row.marketer_id, row.count, row.amount),
    onSuccess: () => onClose(),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['commission-report', month] }),
  });

  return (
    <Dialog open onClose={mutation.isPending ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        {row.marketer_name} — {month}
      </DialogTitle>
      <DialogContent>
        <Stack spacing={1.5}>
          <Typography>تسجيل دفع عمولة هذا الشهر بهذه الأرقام:</Typography>
          <Typography sx={{ fontWeight: 700 }} data-testid="pay-figures">
            {amountText(row.count, row.rate, row.amount)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            بعد التأكيد تُقفل أرقام هذا الشهر ولا يمكن التراجع عن الدفع.
          </Typography>
          {mutation.isError && <Alert severity="error">{mutation.error.message}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={mutation.isPending}>
          إلغاء
        </Button>
        <Button
          variant="contained"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || mutation.isError}
        >
          تأكيد الدفع
        </Button>
      </DialogActions>
    </Dialog>
  );
}
