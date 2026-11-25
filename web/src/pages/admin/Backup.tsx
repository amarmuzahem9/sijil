/**
 * «النسخ الاحتياطي» — main admin only (docs/system.md §10 item 10, §15; specs/016 US3: FR-016,
 * FR-017). Shows what the `backup` service recorded: the last backup, the kept ones, the last
 * weekly copy to the external drive, the last restore drill, the server's disk, and the last
 * deploys, with the warnings. «نسخة يدوية الآن» asks the service for a backup. Restore is a server
 * operation (deploy/backup.md) and is never offered here. No subscriber data.
 */
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useState, type ReactNode } from 'react';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../../lib/api';
import {
  ERROR_TEXTS,
  KIND_LABELS,
  WARNING_TEXTS,
  formatBytes,
  getBackupPage,
  requestBackup,
  type BackupRun,
} from '../../lib/backup';
import { formatNumber } from '../../lib/money';
import { formatBaghdad } from '../../lib/time';

const QUERY_KEY = ['admin', 'backup'] as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <Paper component="section" aria-labelledby={id} variant="outlined" sx={{ p: 2 }}>
      <Typography id={id} variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 1 }}>
        {title}
      </Typography>
      {children}
    </Paper>
  );
}

function when(iso: string | null | undefined): string {
  return iso ? formatBaghdad(iso) : '—';
}

function RunStatus({ run }: { run: BackupRun }) {
  return run.status === 'succeeded' ? (
    <Chip size="small" color="success" label="ناجحة" />
  ) : (
    <Chip size="small" color="error" label="فشلت" />
  );
}

function Counts({ counts }: { counts: Record<string, number> | null }) {
  if (!counts) return null;
  const parts: [string, string][] = [
    ['requests', 'طلبات'],
    ['legacy_subscribers', 'قدامى'],
    ['sas_subscribers', 'SAS'],
    ['users', 'حسابات'],
  ];
  return (
    <Typography variant="body2" color="text.secondary">
      {parts
        .filter(([key]) => key in counts)
        .map(([key, label]) => `${label} ${formatNumber(counts[key])}`)
        .join(' · ')}
    </Typography>
  );
}

function RunLine({ run }: { run: BackupRun }) {
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
      <RunStatus run={run} />
      <Typography variant="body2">{KIND_LABELS[run.kind] ?? run.kind}</Typography>
      <Typography variant="body2" color="text.secondary">
        {when(run.finished_at ?? run.started_at)}
      </Typography>
      {run.status === 'succeeded' ? (
        <Typography variant="body2" color="text.secondary">
          {formatBytes(run.total_size)}
          {run.image_count !== null ? ` · ${formatNumber(run.image_count)} صورة` : ''}
        </Typography>
      ) : (
        <Typography variant="body2" color="error">
          {ERROR_TEXTS[run.error_code ?? ''] ?? run.error_code}
        </Typography>
      )}
    </Stack>
  );
}

export default function Backup() {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: getBackupPage,
    // Follow a running backup every 5 s, otherwise every minute.
    refetchInterval: (q) => (q.state.data?.running ? 5000 : 60000),
  });
  const start = useMutation({
    mutationFn: requestBackup,
    onSuccess: async () => {
      setNotice(null);
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: (err) => setNotice(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE),
  });

  const data = query.data;
  const running = Boolean(data?.running) || start.isPending;
  const last = data?.runs[0];

  return (
    <Stack spacing={2}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <div>
          <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
            النسخ الاحتياطي
          </Typography>
          <Typography variant="body2" color="text.secondary">
            الأوقات بتوقيت بغداد. الاسترجاع من السيرفر فقط.
          </Typography>
        </div>
        <Button
          variant="contained"
          disabled={!data || running}
          onClick={() => start.mutate()}
          startIcon={running ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          نسخة يدوية الآن
        </Button>
      </Box>

      {notice && <Alert severity="warning">{notice}</Alert>}
      {data?.running && <Alert severity="info">جارٍ النسخ…</Alert>}
      {data?.warnings.map((code) => (
        <Alert key={code} severity="error">
          {WARNING_TEXTS[code] ?? code}
        </Alert>
      ))}

      {query.isPending && <Skeleton variant="rounded" height={240} />}
      {query.isError && <Alert severity="error">{query.error.message}</Alert>}

      {data && (
        <>
          <Section title="آخر نسخة">
            {last ? (
              <Stack spacing={0.5}>
                <RunLine run={last} />
                <Counts counts={last.counts} />
              </Stack>
            ) : (
              <Typography color="text.secondary">لا توجد نسخة بعد</Typography>
            )}
          </Section>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
              gap: 2,
            }}
          >
            <Section title="الهارد الخارجي">
              <Typography variant="body2">
                آخر نسخة: {when(data.last_external?.at)}
                {data.last_external && data.last_external.result !== 'succeeded' ? ' (فشلت)' : ''}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ direction: 'ltr' }}>
                {data.status.external_dir || '—'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                مسار الهارد يُضبط على السيرفر فقط
              </Typography>
            </Section>
            <Section title="تجربة الاسترجاع">
              {data.last_drill ? (
                <Typography variant="body2">
                  {data.last_drill.result === 'passed' ? 'نجحت' : 'فشلت'} ·{' '}
                  {when(data.last_drill.at)}
                </Typography>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  لم تُجرَّب بعد
                </Typography>
              )}
            </Section>
            <Section title="السيرفر">
              <Typography variant="body2">
                المساحة الفارغة: {formatBytes(data.status.free_bytes)} من{' '}
                {formatBytes(data.status.total_bytes)}
              </Typography>
              <Typography variant="body2">
                حجم النسخ: {formatBytes(data.status.backup_dir_bytes)}
              </Typography>
              <Typography variant="body2">
                النسخة الليلية: {data.status.nightly_at ?? '—'}
              </Typography>
            </Section>
          </Box>

          <Section title="النسخ المحفوظة">
            {data.runs.length === 0 ? (
              <Typography color="text.secondary">لا توجد نسخ محفوظة</Typography>
            ) : (
              <Stack component="ul" spacing={1} sx={{ listStyle: 'none', p: 0, m: 0 }}>
                {data.runs.map((run) => (
                  <li key={run.id}>
                    <RunLine run={run} />
                  </li>
                ))}
              </Stack>
            )}
          </Section>

          <Section title="آخر عمليات النشر">
            {data.deploys.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                لا يوجد
              </Typography>
            ) : (
              <Stack spacing={0.5}>
                {data.deploys.map((d) => (
                  <Typography key={d.at} variant="body2">
                    {when(d.at)} · {d.mode ?? '—'} · {d.result === 'succeeded' ? 'نجح' : 'فشل'}
                    {d.commit ? ` · ${d.commit}` : ''}
                  </Typography>
                ))}
              </Stack>
            )}
          </Section>
        </>
      )}
    </Stack>
  );
}
