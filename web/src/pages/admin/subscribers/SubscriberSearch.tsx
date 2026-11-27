import SearchOutlined from '@mui/icons-material/SearchOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import { SUBSCRIBER_SOURCE_LABELS } from '../../../lib/labels';
import { STATUS_COLORS, STATUS_LABELS, type RequestStatus } from '../../../lib/requestStatus';
import { SEARCH_PAGE_SIZE, searchSubscribers, type ResultRow } from '../../../lib/subscribers';
import { formatBaghdad } from '../../../lib/time';

function StatusText({ row }: { row: ResultRow }) {
  if (row.status === null) return null;
  if (row.source === 'sijil') {
    const status = row.status as RequestStatus;
    const color = STATUS_COLORS[status];
    return (
      <Chip
        size="small"
        label={STATUS_LABELS[status] ?? row.status}
        sx={color ? { bgcolor: color.bg, color: color.fg, fontWeight: 600 } : undefined}
      />
    );
  }
  if (row.source === 'sas') {
    return (
      <Typography variant="body2" color="text.secondary">
        {`ينتهي ${row.status} حسب آخر استيراد`}
      </Typography>
    );
  }
  return (
    <Typography variant="body2" color="text.secondary">
      {row.status}
    </Typography>
  );
}

function tower(row: ResultRow): string | null {
  if (row.tower_name && row.tower_code) return `${row.tower_name} (${row.tower_code})`;
  return row.tower_code ?? row.tower_name;
}

function Row({ row }: { row: ResultRow }) {
  const number = row.number_label ?? row.legacy_number;
  return (
    <Card variant="outlined" data-testid="subscriber-row">
      <CardActionArea component={RouterLink} to={`/admin/subscribers/${row.source}/${row.ref}`}>
        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Stack
            direction="row"
            sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}
          >
            <Stack spacing={0.25} sx={{ minWidth: 0 }}>
              <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip
                  size="small"
                  variant="outlined"
                  label={SUBSCRIBER_SOURCE_LABELS[row.source]}
                />
                {number && (
                  <Typography variant="body2" dir="ltr" component="span">
                    {number}
                  </Typography>
                )}
              </Stack>
              {row.deleted ? (
                <Typography color="text.secondary">سجل محذوف</Typography>
              ) : (
                <>
                  <Typography sx={{ fontWeight: 700 }}>{row.full_name ?? '—'}</Typography>
                  <Stack
                    direction="row"
                    divider={<span aria-hidden>·</span>}
                    sx={{ gap: 0.75, color: 'text.secondary', flexWrap: 'wrap' }}
                  >
                    {[tower(row), row.phone, row.registered_at && formatBaghdad(row.registered_at)]
                      .filter((part): part is string => Boolean(part))
                      .map((part) => (
                        <Typography key={part} variant="body2" component="span" dir="auto">
                          {part}
                        </Typography>
                      ))}
                  </Stack>
                </>
              )}
            </Stack>
            <StatusText row={row} />
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

/**
 * «المشتركون» (docs/system.md v1.24 §10 item 4; specs/018 US1): one search across Sijil requests,
 * legacy and SAS subscribers. The server decides the kind of what was typed and who may search by
 * a national ID or family number; this page only shows its answer.
 */
export default function SubscriberSearch() {
  const [text, setText] = useState('');
  const [asked, setAsked] = useState<{ q: string; offset: number } | null>(null);
  const query = useQuery({
    queryKey: ['subscriber-search', asked?.q, asked?.offset],
    queryFn: () => searchSubscribers(asked!.q, asked!.offset),
    enabled: asked !== null,
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (text.trim()) setAsked({ q: text.trim(), offset: 0 });
  }

  const data = query.data;
  const offset = asked?.offset ?? 0;
  return (
    <Stack spacing={2} sx={{ maxWidth: 760 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        المشتركون
      </Typography>
      <Stack component="form" direction="row" sx={{ gap: 1 }} onSubmit={submit}>
        <TextField
          label="بحث في المشتركين"
          value={text}
          onChange={(e) => setText(e.target.value)}
          size="small"
          fullWidth
          slotProps={{ htmlInput: { maxLength: 100 } }}
        />
        <Button type="submit" variant="contained" startIcon={<SearchOutlined />}>
          بحث
        </Button>
      </Stack>
      {asked === null && (
        <Typography variant="body2" color="text.secondary">
          اكتب اسم أو هاتف أو يوزر أو رقم طلب. البحث في طلبات سِجلّ والمشتركين القدامى ومشتركي SAS
          معاً.
        </Typography>
      )}
      {query.isFetching && <Skeleton height={96} />}
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}
      {data && !query.isFetching && (
        <>
          <Typography variant="body2" color="text.secondary" data-testid="search-total">
            {`النتائج: ${data.total}`}
          </Typography>
          {data.items.length === 0 ? (
            <Typography color="text.secondary">لا توجد نتائج</Typography>
          ) : (
            data.items.map((row) => <Row key={`${row.source}-${row.ref}`} row={row} />)
          )}
          {data.total > SEARCH_PAGE_SIZE && (
            <Stack direction="row" sx={{ gap: 1 }}>
              <Button
                disabled={offset === 0}
                onClick={() => setAsked({ q: asked!.q, offset: offset - SEARCH_PAGE_SIZE })}
              >
                السابق
              </Button>
              <Button
                disabled={offset + SEARCH_PAGE_SIZE >= data.total}
                onClick={() => setAsked({ q: asked!.q, offset: offset + SEARCH_PAGE_SIZE })}
              >
                التالي
              </Button>
            </Stack>
          )}
        </>
      )}
    </Stack>
  );
}
