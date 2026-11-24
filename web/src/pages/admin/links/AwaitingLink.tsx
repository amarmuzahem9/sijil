/**
 * «بانتظار الربط» (docs/system.md v1.18 §6.5, §10 item 3; specs/013 US1, US3). Two lists: the
 * accepted requests waiting for «تم الربط», oldest acceptance first, and «المربوطة مؤخراً», newest
 * link first. One search box for both: request number, phone or username (the server decides).
 * Rows hold only what SAS checking needs; no identity number, card field or image.
 */
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import InputAdornment from '@mui/material/InputAdornment';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';

import { ApiError } from '../../../lib/api';
import {
  type LinkList,
  type LinkRow,
  linkRequest,
  listAwaiting,
  listRecent,
  unlinkRequest,
} from '../../../lib/links';
import type { UnlinkReason } from '../../../lib/labels';
import { isSearchable } from '../../../lib/requestSearch';
import { formatBaghdad } from '../../../lib/time';
import { LinkConfirmDialog } from './LinkConfirmDialog';
import { UnlinkDialog } from './UnlinkDialog';

type ListKind = 'awaiting' | 'recent';

const LISTS: Record<ListKind, { label: string; empty: string; fetch: typeof listAwaiting }> = {
  awaiting: { label: 'بانتظار الربط', empty: 'لا توجد طلبات بانتظار الربط', fetch: listAwaiting },
  recent: { label: 'المربوطة مؤخراً', empty: 'لا توجد طلبات مربوطة', fetch: listRecent },
};

function Row({ row, action }: { row: LinkRow; action?: ReactNode }) {
  return (
    <Card variant="outlined" data-testid="link-row">
      <CardContent>
        <Stack spacing={0.5}>
          <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography sx={{ fontWeight: 700 }} dir="ltr">
              {row.number_label}
            </Typography>
            {action}
          </Stack>
          <Typography>{row.full_name}</Typography>
          <Typography variant="body2" dir="ltr" sx={{ textAlign: 'right' }}>
            {row.username}
          </Typography>
          <Typography variant="body2" dir="ltr" sx={{ textAlign: 'right' }}>
            {row.phone}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {row.tower_name} ({row.tower_code}) · الفئة: {row.plan_name} · المسوّق:{' '}
            {row.marketer_name}
          </Typography>
          {row.approved_at && (
            <Typography variant="caption" color="text.secondary">
              تاريخ القبول: {formatBaghdad(row.approved_at)}
            </Typography>
          )}
          {row.linked_at && (
            <Typography variant="caption" color="text.secondary">
              تاريخ الربط: {formatBaghdad(row.linked_at)}
              {row.linked_by_name ? ` · ربطه: ${row.linked_by_name}` : ''}
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

function loaded(pages: LinkList[]): number {
  return pages.reduce((n, p) => n + p.items.length, 0);
}

export default function AwaitingLink() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<ListKind>('awaiting');
  const [text, setText] = useState('');
  const [search, setSearch] = useState('');
  const [confirming, setConfirming] = useState<LinkRow | null>(null);
  const [undoing, setUndoing] = useState<LinkRow | null>(null);
  const [message, setMessage] = useState<{ severity: 'success' | 'error'; text: string } | null>(
    null,
  );
  // Ask once typing pauses, not on every key.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(isSearchable(text) ? text.trim() : ''), 300);
    return () => clearTimeout(timer);
  }, [text]);

  const list = useInfiniteQuery({
    queryKey: ['links', kind, search],
    queryFn: ({ pageParam }) => LISTS[kind].fetch(search || undefined, pageParam),
    initialPageParam: 0,
    getNextPageParam: (last, all) => (loaded(all) < last.total ? loaded(all) : undefined),
  });
  const pages = list.data?.pages ?? [];
  const rows = pages.flatMap((p) => p.items);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['links'] });
  const failed = (err: Error) =>
    setMessage({
      severity: 'error',
      text: err instanceof ApiError ? err.message : 'حدث خطأ غير متوقع، حاول مرة أخرى',
    });
  const link = useMutation({
    mutationFn: (row: LinkRow) => linkRequest(row.id),
    onSuccess: (row) => setMessage({ severity: 'success', text: `تم ربط ${row.number_label}` }),
    onError: failed,
    onSettled: () => {
      setConfirming(null);
      void refresh();
    },
  });
  // The page sends back the link it showed; a newer link answers `already_unlinked` (R2).
  const unlink = useMutation({
    mutationFn: ({ row, reason }: { row: LinkRow; reason: UnlinkReason }) =>
      unlinkRequest(row.id, { reason, link_id: row.link_id ?? 0 }),
    onSuccess: (row) =>
      setMessage({ severity: 'success', text: `تم التراجع عن ربط ${row.number_label}` }),
    onError: failed,
    onSettled: () => {
      setUndoing(null);
      void refresh();
    },
  });

  return (
    <Stack spacing={2} sx={{ maxWidth: 720 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        بانتظار الربط
      </Typography>
      <TextField
        type="search"
        size="small"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="بحث برقم الطلب أو الهاتف أو اليوزر"
        slotProps={{
          htmlInput: { 'aria-label': 'بحث برقم الطلب أو الهاتف أو اليوزر' },
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined />
              </InputAdornment>
            ),
          },
        }}
      />
      <Tabs value={kind} onChange={(_, value: ListKind) => setKind(value)}>
        {(Object.keys(LISTS) as ListKind[]).map((k) => (
          <Tab key={k} value={k} label={LISTS[k].label} />
        ))}
      </Tabs>
      {message && (
        <Alert severity={message.severity} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {list.isPending && <Skeleton height={120} />}
      {list.isError && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => list.refetch()}>
              إعادة المحاولة
            </Button>
          }
        >
          {list.error.message}
        </Alert>
      )}
      {list.isSuccess && (
        <>
          <Typography variant="body2" color="text.secondary">
            العدد: {pages[0]?.total ?? 0}
          </Typography>
          {rows.length === 0 && <Typography>{LISTS[kind].empty}</Typography>}
          {rows.map((row) => (
            <Row
              key={row.id}
              row={row}
              action={
                kind === 'awaiting' ? (
                  <Button variant="contained" color="success" onClick={() => setConfirming(row)}>
                    تم الربط
                  </Button>
                ) : (
                  <Button variant="outlined" color="warning" onClick={() => setUndoing(row)}>
                    التراجع عن الربط
                  </Button>
                )
              }
            />
          ))}
          {list.hasNextPage && (
            <Button onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
              تحميل المزيد
            </Button>
          )}
        </>
      )}

      <LinkConfirmDialog
        row={confirming}
        busy={link.isPending}
        onConfirm={() => confirming && link.mutate(confirming)}
        onClose={() => setConfirming(null)}
      />
      <UnlinkDialog
        key={undoing?.id ?? 'none'}
        row={undoing}
        busy={unlink.isPending}
        onConfirm={(reason) => undoing && unlink.mutate({ row: undoing, reason })}
        onClose={() => setUndoing(null)}
      />
    </Stack>
  );
}
