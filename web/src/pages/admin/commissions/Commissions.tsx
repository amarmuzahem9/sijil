import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { amountText, getReport, listMonths, type ReportRow } from '../../../lib/commissions';
import { formatMoney, formatNumber } from '../../../lib/money';
import { formatBaghdad } from '../../../lib/time';
import CommissionDetailDialog from './CommissionDetail';
import PayDialog from './PayDialog';

function extraText(row: ReportRow): string | null {
  if (row.without_commission + row.paid_before === 0) return null;
  return `بلا عمولة: ${formatNumber(row.without_commission)} · مدفوع سابقاً: ${formatNumber(row.paid_before)}`;
}

function RowCard({
  row,
  onDetail,
  onPay,
}: {
  row: ReportRow;
  onDetail: () => void;
  onPay: () => void;
}) {
  const extra = extraText(row);
  return (
    <Card variant="outlined" data-testid="commission-row">
      <CardContent>
        <Stack
          direction="row"
          sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1, mb: 1 }}
        >
          <Typography sx={{ fontWeight: 700 }}>{row.marketer_name}</Typography>
          <Chip
            size="small"
            label={row.payment ? 'تم الدفع' : 'غير مدفوع'}
            color={row.payment ? 'success' : 'default'}
            variant={row.payment ? 'filled' : 'outlined'}
          />
        </Stack>
        <Typography sx={{ fontWeight: 600 }} data-testid="row-amount">
          {amountText(row.count, row.rate, row.amount)}
        </Typography>
        {extra && (
          <Typography variant="body2" color="text.secondary" data-testid="row-extra">
            {extra}
          </Typography>
        )}
        {row.payment && (
          <Typography variant="body2" color="text.secondary" data-testid="row-paid">
            تم الدفع بواسطة {row.payment.paid_by_name ?? '—'} · {formatBaghdad(row.payment.paid_at)}
          </Typography>
        )}
        <Stack direction="row" sx={{ mt: 1, gap: 1 }}>
          <Button size="small" onClick={onDetail}>
            التفاصيل
          </Button>
          {/* A finished, unpaid month with a count above 0 (FR-011). */}
          {row.payable && (
            <Button size="small" variant="contained" onClick={onPay}>
              تم الدفع
            </Button>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

/**
 * «العمولات» (docs/system.md v1.23 §9, §10 item 13; specs/017 US2): pick a month, one row per
 * marketer with links or a payment in it, the month total, and the requests behind each row.
 * Every number comes from the server.
 */
export default function Commissions() {
  const months = useQuery({ queryKey: ['commission-months'], queryFn: listMonths });
  const [picked, setPicked] = useState<string | null>(null);
  const month = picked ?? months.data?.current ?? null;
  const report = useQuery({
    queryKey: ['commission-report', month],
    queryFn: () => getReport(month!),
    enabled: month !== null,
  });
  const [detail, setDetail] = useState<ReportRow | null>(null);
  const [paying, setPaying] = useState<ReportRow | null>(null);
  const error = months.error ?? report.error;

  return (
    <Stack spacing={2} sx={{ maxWidth: 720 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        العمولات
      </Typography>
      {months.data && month && (
        <TextField
          select
          label="الشهر"
          value={month}
          onChange={(e) => setPicked(e.target.value)}
          sx={{ maxWidth: 220 }}
          size="small"
        >
          {months.data.items.map((m) => (
            <MenuItem key={m} value={m}>
              {m}
            </MenuItem>
          ))}
        </TextField>
      )}
      {error && <Alert severity="error">{error.message}</Alert>}
      {(months.isPending || report.isPending) && !error && <Skeleton height={96} />}
      {report.data && (
        <>
          <Typography variant="body2" color="text.secondary">
            {report.data.month_label}
            {report.data.finished ? '' : ' · الشهر الجاري، يُسجَّل الدفع بعد نهايته'}
          </Typography>
          <Typography sx={{ fontWeight: 700 }} data-testid="commission-total">
            مجموع الشهر: {formatMoney(report.data.total_amount)}
          </Typography>
          {report.data.rows.length === 0 ? (
            <Typography color="text.secondary">لا يوجد ربط في هذا الشهر</Typography>
          ) : (
            report.data.rows.map((row) => (
              <RowCard
                key={row.marketer_id}
                row={row}
                onDetail={() => setDetail(row)}
                onPay={() => setPaying(row)}
              />
            ))
          )}
        </>
      )}
      {paying && month && <PayDialog month={month} row={paying} onClose={() => setPaying(null)} />}
      {detail && month && (
        <CommissionDetailDialog
          month={month}
          marketerId={detail.marketer_id}
          marketerName={detail.marketer_name}
          onClose={() => setDetail(null)}
        />
      )}
    </Stack>
  );
}
