/**
 * «الرئيسية» for every admin (docs/system.md v1.13 §10 item 1, specs/010 US5: FR-021): today's and
 * this month's counts in Baghdad time. Each count goes by the time of its own step; «بالانتظار» is
 * the current number. Counts only.
 */
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useId } from 'react';

import { getHome, type HomeCounts } from '../../lib/adminRequests';
import { formatNumber } from '../../lib/money';

const TILES: [keyof HomeCounts, string][] = [
  ['submitted', 'مرفوعة'],
  ['approved', 'مقبولة'],
  ['pending', 'بالانتظار'],
  ['linked', 'تم الربط'],
  ['rejected', 'مرفوضة'],
];

function Tile({ label, value }: { label: string; value: number }) {
  const id = useId();
  return (
    <Paper variant="outlined" role="group" aria-labelledby={id} sx={{ p: 2 }}>
      <Typography id={id} variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h5" component="p" sx={{ fontWeight: 700, mt: 0.5 }}>
        {formatNumber(value)}
      </Typography>
    </Paper>
  );
}

function Row({ title, counts }: { title: string; counts: HomeCounts }) {
  const id = useId();
  return (
    <Box component="section" aria-labelledby={id}>
      <Typography id={id} variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 1.5 }}>
        {title}
      </Typography>
      <Box
        sx={{
          display: 'grid',
          // Two tiles a row on a phone, all five on a computer.
          gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(5, 1fr)' },
          gap: 1.5,
        }}
      >
        {TILES.map(([key, label]) => (
          <Tile key={key} label={label} value={counts[key]} />
        ))}
      </Box>
    </Box>
  );
}

export default function AdminHome() {
  const query = useQuery({ queryKey: ['admin', 'home'], queryFn: getHome });
  return (
    <Stack spacing={3}>
      <div>
        <Typography variant="h6" component="h1" sx={{ fontWeight: 700 }}>
          الرئيسية
        </Typography>
        <Typography variant="body2" color="text.secondary">
          الأيام والأشهر بتوقيت بغداد
        </Typography>
      </div>
      {query.isPending && <Skeleton variant="rounded" height={200} />}
      {query.isError && <Paper sx={{ p: 2 }}>{query.error.message}</Paper>}
      {query.data && (
        <>
          <Row title="اليوم" counts={query.data.today} />
          <Row title="هذا الشهر" counts={query.data.month} />
        </>
      )}
    </Stack>
  );
}
