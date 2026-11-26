import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { getDetail, type DetailLine } from '../../../lib/commissions';
import { REQUEST_TYPE_LABELS } from '../../../lib/labels';
import { formatBaghdad } from '../../../lib/time';

interface Props {
  month: string;
  marketerId: number;
  marketerName: string;
  onClose: () => void;
}

function Line({ line, extra }: { line: DetailLine; extra?: string }) {
  const type = REQUEST_TYPE_LABELS[line.type as keyof typeof REQUEST_TYPE_LABELS] ?? line.type;
  return (
    <Stack spacing={0.25} sx={{ py: 0.75 }} data-testid="detail-line">
      <Typography sx={{ fontWeight: 600 }}>
        <span dir="ltr">{line.number_label}</span>
        {' · '}
        {line.full_name ?? '—'}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {type} · {line.tower_name} ({line.tower_code}) ·{' '}
        {line.linked_at ? `ربط ${formatBaghdad(line.linked_at)}` : 'تم التراجع عن الربط'}
      </Typography>
      {extra && (
        <Typography variant="body2" color="text.secondary">
          {extra}
        </Typography>
      )}
    </Stack>
  );
}

function Section({ title, children }: { title: string; children: ReactNode[] }) {
  return (
    <Stack>
      <Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700, mt: 1 }}>
        {`${title} (${children.length})`}
      </Typography>
      {children.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          لا يوجد
        </Typography>
      ) : (
        <Stack divider={<Divider flexItem />}>{children}</Stack>
      )}
    </Stack>
  );
}

/**
 * The requests behind one row of «العمولات» (specs/017 FR-010): counted, «بلا عمولة», and those
 * already paid in an earlier month. Only number, name, type, tower and link date.
 */
export default function CommissionDetailDialog({
  month,
  marketerId,
  marketerName,
  onClose,
}: Props) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['commission-detail', month, marketerId],
    queryFn: () => getDetail(month, marketerId),
  });

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {marketerName} — {month}
      </DialogTitle>
      <DialogContent dividers>
        {isPending && <Skeleton height={120} />}
        {isError && <Alert severity="error">{error.message}</Alert>}
        {data && (
          <Stack spacing={1}>
            <Section title="المحسوبة">
              {data.counted.map((l) => (
                <Line key={l.id} line={l} />
              ))}
            </Section>
            <Section title="بلا عمولة">
              {data.without_commission.map((l) => (
                <Line key={l.id} line={l} />
              ))}
            </Section>
            <Section title="مدفوع سابقاً">
              {data.paid_before.map((l) => (
                <Line key={l.id} line={l} extra={`دُفع في ${l.paid_month}`} />
              ))}
            </Section>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>إغلاق</Button>
      </DialogActions>
    </Dialog>
  );
}
