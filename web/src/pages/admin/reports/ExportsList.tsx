import DownloadOutlined from '@mui/icons-material/DownloadOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useMutation, useQuery } from '@tanstack/react-query';

import { EXPORT_STATE_LABELS } from '../../../lib/labels';
import {
  EXPORTS_QUERY_KEY,
  EXPORT_POLL_MS,
  downloadTicket,
  listExports,
  startDownload,
  type ExportItem,
} from '../../../lib/reports';
import { formatBaghdad } from '../../../lib/time';

const STATE_COLORS: Record<ExportItem['state'], 'default' | 'info' | 'success' | 'error'> = {
  preparing: 'info',
  ready: 'success',
  failed: 'error',
  removed: 'default',
};

function Item({
  item,
  onDownload,
  busy,
}: {
  item: ExportItem;
  onDownload: () => void;
  busy: boolean;
}) {
  const parts = [
    item.row_count !== null ? `${item.row_count} طلب` : null,
    item.include_identity ? 'مع الأرقام والصور' : 'بدون الأرقام والصور',
    `طُلب ${formatBaghdad(item.created_at)}`,
    item.state === 'ready' && item.expires_at ? `يُمسح ${formatBaghdad(item.expires_at)}` : null,
    item.missing_images ? `صور غير متوفرة: ${item.missing_images}` : null,
  ].filter((part): part is string => Boolean(part));
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }} data-testid="export-item">
      <Stack
        direction="row"
        sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}
      >
        <Stack spacing={0.5} sx={{ minWidth: 0 }}>
          <Chip
            size="small"
            color={STATE_COLORS[item.state]}
            label={EXPORT_STATE_LABELS[item.state]}
            sx={{ alignSelf: 'flex-start' }}
          />
          <Typography variant="body2" color="text.secondary">
            {parts.join(' · ')}
          </Typography>
        </Stack>
        {item.state === 'ready' && (
          <Button
            variant="contained"
            size="small"
            startIcon={<DownloadOutlined />}
            onClick={onDownload}
            disabled={busy}
          >
            تنزيل
          </Button>
        )}
      </Stack>
    </Paper>
  );
}

/**
 * The admin's own exports of the last 7 days (specs/019 US2, FR-012, FR-013). «تنزيل» asks the
 * server for a one-use link and lets the browser download the file itself. The list is asked
 * again every few seconds while an export is preparing.
 */
export default function ExportsList() {
  const exports = useQuery({
    queryKey: EXPORTS_QUERY_KEY,
    queryFn: listExports,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => item.state === 'preparing') ? EXPORT_POLL_MS : false,
  });
  const download = useMutation({
    mutationFn: (id: string) => downloadTicket(id),
    onSuccess: (ticket) => startDownload(ticket.url),
    onSettled: () => exports.refetch(),
  });

  const items = exports.data?.items ?? [];
  if (items.length === 0 && !download.isError) return null;
  return (
    <Stack spacing={1} data-testid="exports-list">
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
        تصديراتي
      </Typography>
      {download.isError && <Alert severity="error">{download.error.message}</Alert>}
      {items.map((item) => (
        <Item
          key={item.id}
          item={item}
          busy={download.isPending}
          onDownload={() => download.mutate(item.id)}
        />
      ))}
    </Stack>
  );
}
