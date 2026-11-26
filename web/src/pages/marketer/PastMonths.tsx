import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';

import { amountText, listPastMonths } from '../../lib/commissions';
import { formatNumber } from '../../lib/money';

/**
 * «الأشهر السابقة» (docs/system.md v1.23 §4.2; specs/017 FR-007): one card per finished month,
 * newest first. A paid month shows its locked figures; an unpaid one today's tiers.
 */
export default function PastMonths() {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['marketer-past-months'],
    queryFn: listPastMonths,
  });

  return (
    <Stack spacing={2} sx={{ maxWidth: 560 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        الأشهر السابقة
      </Typography>
      {isPending && <Skeleton height={96} />}
      {isError && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => refetch()}>
              إعادة المحاولة
            </Button>
          }
        >
          {error.message}
        </Alert>
      )}
      {data && data.items.length === 0 && (
        <Typography color="text.secondary">لا توجد أشهر سابقة</Typography>
      )}
      {data?.items.map((m) => (
        <Card key={m.month} variant="outlined" data-testid="past-month">
          <CardContent>
            <Stack
              direction="row"
              sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1, mb: 1 }}
            >
              <Typography sx={{ fontWeight: 700 }}>{m.month_label}</Typography>
              <Chip
                size="small"
                label={m.paid ? 'تم الدفع' : 'غير مدفوع'}
                color={m.paid ? 'success' : 'default'}
                variant={m.paid ? 'filled' : 'outlined'}
              />
            </Stack>
            <Typography data-testid="past-month-count">
              تم الربط: {formatNumber(m.count)}
            </Typography>
            {m.without_commission > 0 && (
              <Typography variant="body2" color="text.secondary" data-testid="past-month-without">
                و {formatNumber(m.without_commission)} بلا عمولة
              </Typography>
            )}
            <Typography sx={{ mt: 0.5, fontWeight: 600 }} data-testid="past-month-amount">
              {amountText(m.count, m.rate, m.amount)}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
}
