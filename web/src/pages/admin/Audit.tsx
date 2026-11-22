import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CircularProgress from '@mui/material/CircularProgress';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { auditApi, SYSTEM_ACTOR } from '../../lib/audit';
import type { AuditEntry, AuditFilters } from '../../lib/audit';
import { actionLabel, entryTargetLabel, formatAuditValue } from '../../lib/auditFormat';
import { AUDIT_FIELD_LABELS } from '../../lib/labels';
import { formatBaghdad } from '../../lib/time';

function Values({ title, values }: { title: string; values: Record<string, unknown> | null }) {
  if (!values || Object.keys(values).length === 0) return null;
  return (
    <Box sx={{ flex: '1 1 200px', minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
        {title}
      </Typography>
      {Object.entries(values).map(([field, value]) => (
        <Typography key={field} variant="body2" sx={{ overflowWrap: 'anywhere' }}>
          <Typography component="span" variant="body2" color="text.secondary">
            {AUDIT_FIELD_LABELS[field] ?? field}:{' '}
          </Typography>
          {field === 'phone' ? (
            <bdi dir="ltr">{formatAuditValue(field, value)}</bdi>
          ) : (
            formatAuditValue(field, value)
          )}
        </Typography>
      ))}
    </Box>
  );
}

function EntryCard({ entry }: { entry: AuditEntry }) {
  const target = entryTargetLabel(entry);
  return (
    <Card variant="outlined" data-testid="audit-entry">
      <CardContent>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'baseline' }}>
          <Typography sx={{ fontWeight: 700 }}>{actionLabel(entry)}</Typography>
          {target && <Typography color="text.secondary">— {target}</Typography>}
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {formatBaghdad(entry.created_at)} · {entry.actor ? entry.actor.name : 'النظام'}
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          <Values title="قبل" values={entry.before} />
          <Values title="بعد" values={entry.after} />
        </Box>
      </CardContent>
    </Card>
  );
}

/** «سجل العمليات»: main admin only, read-only, newest first (specs/002 US5). */
export default function Audit() {
  const [filters, setFilters] = useState<AuditFilters>({});
  const actors = useQuery({ queryKey: ['audit', 'actors'], queryFn: auditApi.actors });
  const entries = useInfiniteQuery({
    queryKey: ['audit', 'entries', filters],
    queryFn: ({ pageParam }) => auditApi.page(filters, pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => (last.has_more ? (last.next_before_id ?? undefined) : undefined),
  });
  const items = entries.data?.pages.flatMap((p) => p.items) ?? [];
  const set = (patch: Partial<AuditFilters>) => setFilters((f) => ({ ...f, ...patch }));

  return (
    <>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        سجل العمليات
      </Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            label="من تاريخ"
            type="date"
            size="small"
            value={filters.from ?? ''}
            onChange={(e) => set({ from: e.target.value || undefined })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            label="إلى تاريخ"
            type="date"
            size="small"
            value={filters.to ?? ''}
            onChange={(e) => set({ to: e.target.value || undefined })}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            select
            label="المنفّذ"
            size="small"
            value={filters.actorId ?? ''}
            onChange={(e) => set({ actorId: e.target.value || undefined })}
            sx={{ minWidth: 180 }}
          >
            <MenuItem value="">الكل</MenuItem>
            <MenuItem value={SYSTEM_ACTOR}>النظام</MenuItem>
            {(actors.data ?? []).map((a) => (
              <MenuItem key={a.id} value={String(a.id)}>
                {a.name}
              </MenuItem>
            ))}
          </TextField>
          <Button onClick={() => setFilters({})}>مسح الفلاتر</Button>
        </Box>
      </Paper>

      {entries.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {entries.isError && <Alert severity="error">{entries.error.message}</Alert>}
      {entries.isSuccess && items.length === 0 && (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">لا توجد عمليات</Typography>
        </Paper>
      )}
      <Stack spacing={1.5}>
        {items.map((entry) => (
          <EntryCard key={entry.id} entry={entry} />
        ))}
      </Stack>
      {entries.hasNextPage && (
        <Box sx={{ textAlign: 'center', mt: 2 }}>
          <Button
            variant="outlined"
            onClick={() => entries.fetchNextPage()}
            disabled={entries.isFetchingNextPage}
          >
            تحميل المزيد
          </Button>
        </Box>
      )}
    </>
  );
}
