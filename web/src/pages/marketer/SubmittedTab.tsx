/**
 * «بالانتظار» and «مقبولة» in «الطلبات» (specs/008 T027, FR-019): the marketer's submitted
 * requests, newest first, each opening its result page. «مرفوضة» since 010, «تم الربط» since 012,
 * ordered by link time with its date since 013. With `q` it lists the search results across statuses (specs/012 US3). A deleted request (specs/011 R11) keeps its row under its
 * status with the grey tag «محذوف», the reason, the number, the tower and the date only.
 */
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';

import { DELETED_TAG, listRequests, type SubmittedStatus } from '../../lib/requests';
import { STATUS_COLORS, STATUS_LABELS } from '../../lib/requestStatus';
import { formatBaghdad } from '../../lib/time';

export function SubmittedTab({ statuses, q }: { statuses: SubmittedStatus[]; q?: string }) {
  const query = useQuery({
    queryKey: q === undefined ? ['requests', 'list', ...statuses] : ['requests', 'search', q],
    queryFn: () => listRequests(statuses, q),
  });
  if (query.isPending)
    return (
      <Stack spacing={1}>
        <Skeleton variant="rounded" height={72} />
        <Skeleton variant="rounded" height={72} />
      </Stack>
    );
  if (query.isError) return <Paper sx={{ p: 2 }}>{query.error.message}</Paper>;
  const items = query.data.items;
  if (items.length === 0)
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
        {q === undefined ? 'لا توجد طلبات بعد' : 'لا توجد نتائج'}
      </Paper>
    );
  return (
    <Stack spacing={1} data-testid="submitted-list">
      {items.map((item) => {
        const deleted = item.deleted_at !== null;
        const colors = deleted ? DELETED_TAG : STATUS_COLORS[item.status];
        return (
          <Card key={item.id} variant="outlined">
            <CardActionArea component={RouterLink} to={`/requests/${item.id}`} sx={{ p: 1.5 }}>
              <Stack
                direction="row"
                sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1 }}
              >
                <Stack spacing={0.25} sx={{ minWidth: 0 }}>
                  <Typography sx={{ fontWeight: 700 }} noWrap>
                    {deleted ? `${item.tower_name} (${item.tower_code})` : item.full_name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    <span dir="ltr">{`#${item.number_label}`}</span> ·{' '}
                    {formatBaghdad(item.submitted_at)}
                  </Typography>
                  {!deleted && item.status === 'linked' && item.linked_at && (
                    <Typography variant="body2" color="success.main">
                      تاريخ الربط: {formatBaghdad(item.linked_at)}
                    </Typography>
                  )}
                  {deleted && (
                    <Typography variant="body2" color="text.secondary">
                      سبب الحذف: {item.deletion_label}
                    </Typography>
                  )}
                  {!deleted && item.rejection_label && (
                    <Typography variant="body2" color="error.main">
                      سبب الرفض: {item.rejection_label}
                    </Typography>
                  )}
                </Stack>
                <Chip
                  size="small"
                  label={deleted ? DELETED_TAG.label : STATUS_LABELS[item.status]}
                  sx={{ bgcolor: colors.bg, color: colors.fg, fontWeight: 600 }}
                />
              </Stack>
            </CardActionArea>
          </Card>
        );
      })}
    </Stack>
  );
}
