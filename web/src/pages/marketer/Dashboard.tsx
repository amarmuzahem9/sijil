import GroupAddOutlined from '@mui/icons-material/GroupAddOutlined';
import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';

import { apiFetch } from '../../lib/api';
import { STATUS_COLORS, STATUS_LABELS } from '../../lib/requestStatus';
import { formatBaghdad } from '../../lib/time';

/** The marketer home (system.md v1.18 §4.2, specs/013 contracts/api.md › dashboard). */
interface DashboardData {
  /** Links of this Baghdad month counted for commission. */
  linked_this_month: number;
  /** Returns accepted with «لا» for commission: «و M بلا عمولة». */
  linked_without_commission: number;
  month_label: string;
  /** Up to 10 of this month, newest link first. */
  recent_links: { id: number; number_label: string; full_name: string | null; linked_at: string }[];
}

const LINKED = STATUS_COLORS.linked;

export default function Dashboard() {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['marketer-dashboard'],
    queryFn: () => apiFetch<DashboardData>('/api/marketer/dashboard'),
  });

  return (
    <Stack spacing={2} sx={{ maxWidth: 560 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        الرئيسية
      </Typography>

      {/* Both open the single-page form (feature 005). For an existing subscriber the checks
          decide the path (specs/009 FR-005c): return to service or a second subscription. */}
      <Button
        variant="contained"
        size="large"
        component={RouterLink}
        to="/drafts/new"
        startIcon={<PersonAddAlt1Outlined />}
        sx={{ py: 2.5, fontSize: '1.15rem' }}
      >
        إضافة مشترك جديد
      </Button>
      <Button
        variant="outlined"
        size="large"
        component={RouterLink}
        to="/drafts/new"
        startIcon={<GroupAddOutlined />}
        sx={{ py: 1.5 }}
      >
        إضافة اشتراك لمشترك موجود
      </Button>

      <Card variant="outlined">
        <CardContent>
          {isPending && <Skeleton width="60%" height={36} />}
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
          {data && (
            <>
              <Typography variant="h6" data-testid="linked-counter">
                تم الربط هذا الشهر: {data.linked_this_month}
              </Typography>
              {data.linked_without_commission > 0 && (
                <Typography variant="body2" data-testid="linked-without-commission">
                  و {data.linked_without_commission} بلا عمولة
                </Typography>
              )}
              <Typography variant="body2" color="text.secondary">
                {data.month_label}
              </Typography>
            </>
          )}
        </CardContent>
      </Card>

      {data && (
        <Stack spacing={1}>
          <Typography component="h2" variant="subtitle1" sx={{ fontWeight: 700 }}>
            آخر المربوطين هذا الشهر
          </Typography>
          {data.recent_links.length === 0 ? (
            <Typography color="text.secondary">لا يوجد مشتركون مربوطون هذا الشهر</Typography>
          ) : (
            <Stack spacing={1} data-testid="recent-links">
              {data.recent_links.map((link) => (
                <Card key={link.id} variant="outlined">
                  <CardActionArea
                    component={RouterLink}
                    to={`/requests/${link.id}`}
                    sx={{ p: 1.5 }}
                  >
                    <Stack
                      direction="row"
                      sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}
                    >
                      <Stack spacing={0.25} sx={{ minWidth: 0 }}>
                        <Typography sx={{ fontWeight: 700 }} noWrap>
                          {link.full_name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          <span dir="ltr">{`#${link.number_label}`}</span> ·{' '}
                          {formatBaghdad(link.linked_at)}
                        </Typography>
                      </Stack>
                      <Chip
                        size="small"
                        label={STATUS_LABELS.linked}
                        sx={{ bgcolor: LINKED.bg, color: LINKED.fg, fontWeight: 600 }}
                      />
                    </Stack>
                  </CardActionArea>
                </Card>
              ))}
            </Stack>
          )}
        </Stack>
      )}
    </Stack>
  );
}
