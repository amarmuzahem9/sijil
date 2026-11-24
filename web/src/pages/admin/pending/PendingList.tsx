/**
 * «طلبات بالانتظار» (docs/system.md §10 item 2, specs/010 US1, FR-002): every pending request,
 * oldest first, filterable by reason, each opening its review file. «فتح طلب برقمه» on top opens
 * any request, rejected ones included (specs/011 FR-022).
 */
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import { listPending, type PendingItem, type ReasonCode } from '../../../lib/adminRequests';
import { REASON_LABELS, REQUEST_TYPE_LABELS } from '../../../lib/labels';
import { formatBaghdad } from '../../../lib/time';
import { OpenByNumber } from './OpenByNumber';

const FILTERS: (ReasonCode | null)[] = [
  null,
  'family_exists',
  'return',
  'numbers_edited',
  'numbers_conflict',
];

function Row({ item }: { item: PendingItem }) {
  return (
    <Card variant="outlined">
      <CardActionArea component={RouterLink} to={`/admin/pending/${item.id}`} sx={{ p: 2 }}>
        <Stack spacing={0.75}>
          <Stack
            direction="row"
            spacing={1}
            sx={{ alignItems: 'center', flexWrap: 'wrap', gap: 1 }}
          >
            <Typography sx={{ fontWeight: 700 }} dir="ltr">
              {item.number_label}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              النوع: {REQUEST_TYPE_LABELS[item.type]}
            </Typography>
            {item.reasons.map((r) => (
              <Chip key={r} size="small" color="warning" label={REASON_LABELS[r]} />
            ))}
          </Stack>
          <Typography>{item.full_name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {item.tower_name} ({item.tower_code}) · المسوّق: {item.marketer_name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formatBaghdad(item.submitted_at)}
          </Typography>
        </Stack>
      </CardActionArea>
    </Card>
  );
}

export default function PendingListPage() {
  const [reason, setReason] = useState<ReasonCode | null>(null);
  const query = useQuery({
    queryKey: ['admin', 'pending', reason],
    queryFn: () => listPending(reason ?? undefined),
  });

  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ alignItems: 'baseline', justifyContent: 'space-between' }}>
        <Typography variant="h6" component="h1" sx={{ fontWeight: 700 }}>
          طلبات بالانتظار
        </Typography>
        {query.data && <Typography color="text.secondary">العدد: {query.data.total}</Typography>}
      </Stack>
      <OpenByNumber />
      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
        {FILTERS.map((code) => (
          <Chip
            key={code ?? 'all'}
            component="button"
            label={code ? REASON_LABELS[code] : 'الكل'}
            color={reason === code ? 'primary' : 'default'}
            variant={reason === code ? 'filled' : 'outlined'}
            onClick={() => setReason(code)}
          />
        ))}
      </Stack>
      {query.isPending && (
        <Stack spacing={1}>
          <Skeleton variant="rounded" height={96} />
          <Skeleton variant="rounded" height={96} />
        </Stack>
      )}
      {query.isError && <Paper sx={{ p: 2 }}>{query.error.message}</Paper>}
      {query.data && query.data.items.length === 0 && (
        <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
          لا توجد طلبات بالانتظار
        </Paper>
      )}
      {query.data && query.data.items.length > 0 && (
        <Stack spacing={1}>
          {query.data.items.map((item) => (
            <Row key={item.id} item={item} />
          ))}
        </Stack>
      )}
    </Stack>
  );
}
