import AddOutlined from '@mui/icons-material/AddOutlined';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Paper from '@mui/material/Paper';
import Snackbar from '@mui/material/Snackbar';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { MoneyField } from '../../../components/MoneyField';
import { ApiError, NETWORK_ERROR_MESSAGE } from '../../../lib/api';
import { moneyText, parseMoney } from '../../../lib/money';
import { tierRanges, tiersApi } from '../../../lib/settings';
import type { Tier } from '../../../lib/settings';

interface Row {
  key: number;
  countText: string;
  rateText: string;
  rate: number | null;
}

let nextKey = 0;
const toRows = (tiers: Tier[]): Row[] =>
  tiers.map((t) => ({
    key: nextKey++,
    countText: String(t.min_count),
    rateText: moneyText(t.rate),
    rate: t.rate,
  }));

function TiersEditor({ initial }: { initial: Tier[] }) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<Row[]>(() => toRows(initial));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const counts = rows.map((r) => parseMoney(r.countText));
  const ranges = tierRanges(counts);
  const update = (key: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  async function save() {
    if (counts.some((c) => c === null) || rows.some((r) => r.rate === null)) {
      setError('أكمل كل الشرائح بأعداد صحيحة');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const items = rows.map((r, i) => ({ min_count: counts[i]!, rate: r.rate! }));
      const saved = await tiersApi.replace(items);
      setRows(toRows(saved));
      setNotice('تم الحفظ');
      await queryClient.invalidateQueries({ queryKey: ['settings', 'tiers'] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Paper variant="outlined" sx={{ p: 2, maxWidth: 720 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        سعر الشريحة يُطبَّق على كل مشتركي الشهر، وعلى كل شهر لم يُدفع بعد (القسم 9).
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Stack spacing={2}>
        {rows.map((row, i) => (
          <Box
            key={row.key}
            data-testid="tier-row"
            sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', flexWrap: 'wrap' }}
          >
            <TextField
              label="أقل عدد مشتركين"
              value={row.countText}
              onChange={(e) => update(row.key, { countText: e.target.value })}
              error={counts[i] === null}
              sx={{ width: 160 }}
              slotProps={{ htmlInput: { dir: 'ltr', inputMode: 'numeric' } }}
            />
            <Box sx={{ flex: '1 1 200px', minWidth: 180 }}>
              <MoneyField
                label="سعر المشترك"
                text={row.rateText}
                onChange={(text, value) => update(row.key, { rateText: text, rate: value })}
                error={row.rate === null || row.rate < 1 ? 'مبلغ غير صالح' : null}
              />
            </Box>
            <Typography sx={{ alignSelf: 'center', minWidth: 110 }} color="text.secondary">
              {ranges[i]}
            </Typography>
            <IconButton
              aria-label="حذف الشريحة"
              onClick={() => setRows((rs) => rs.filter((r) => r.key !== row.key))}
              disabled={rows.length <= 1}
              sx={{ alignSelf: 'center' }}
            >
              <DeleteOutlined />
            </IconButton>
          </Box>
        ))}
      </Stack>
      <Box sx={{ display: 'flex', gap: 1.5, mt: 3, flexWrap: 'wrap' }}>
        <Button
          startIcon={<AddOutlined />}
          onClick={() =>
            setRows((rs) => [...rs, { key: nextKey++, countText: '', rateText: '', rate: null }])
          }
          disabled={rows.length >= 20}
        >
          إضافة شريحة
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" onClick={save} disabled={busy}>
          حفظ
        </Button>
      </Box>
      <Snackbar
        open={notice !== null}
        autoHideDuration={3000}
        onClose={() => setNotice(null)}
        message={notice}
      />
    </Paper>
  );
}

/** «الشرائح» (specs/004 US3): the whole list is edited and saved at once. */
export default function TiersTab() {
  const tiers = useQuery({ queryKey: ['settings', 'tiers'], queryFn: tiersApi.get });
  if (tiers.isPending) return <CircularProgress aria-label="جارٍ التحميل" />;
  if (tiers.isError) return <Alert severity="error">{tiers.error.message}</Alert>;
  return <TiersEditor initial={tiers.data} />;
}
