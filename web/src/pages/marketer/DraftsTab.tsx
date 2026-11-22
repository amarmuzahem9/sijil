/**
 * «الطلبات ← مسودات» (docs/system.md §4.3, specs/005 US4, FR-018): the marketer's own drafts,
 * newest change first, with search and «حذف» behind a confirmation (FR-019).
 */
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useDeferredValue, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import { ConfirmDialog } from '../../components/ConfirmDialog';
import { deleteDraft, listDrafts, type DraftListItem } from '../../lib/drafts';
import { STATUS_COLORS, STATUS_LABELS } from '../../lib/requestStatus';
import { formatBaghdad } from '../../lib/time';

const DRAFTS_QUERY_KEY = ['drafts'] as const;

function DraftCard({ draft, onDelete }: { draft: DraftListItem; onDelete: () => void }) {
  const colors = STATUS_COLORS.draft;
  return (
    <Card variant="outlined" data-testid="draft-card" sx={{ display: 'flex' }}>
      <CardActionArea component={RouterLink} to={`/drafts/${draft.id}`} sx={{ p: 1.5, flex: 1 }}>
        <Stack spacing={0.5}>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography sx={{ fontWeight: 600 }} data-testid="draft-name">
              {draft.subscriber_name ?? 'بدون اسم'}
            </Typography>
            <Chip
              size="small"
              label={STATUS_LABELS.draft}
              sx={{ bgcolor: colors.bg, color: colors.fg, fontWeight: 600 }}
            />
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {draft.tower_code && (
              <>
                <span dir="ltr">{draft.tower_code}</span> ·{' '}
              </>
            )}
            آخر حفظ: {formatBaghdad(draft.updated_at)}
          </Typography>
          <Typography
            variant="body2"
            color={draft.missing_count ? 'warning.main' : 'success.main'}
            data-testid="draft-missing"
          >
            {draft.missing_count ? `ناقص ${draft.missing_count}` : 'كل الحقول مكتملة'}
          </Typography>
        </Stack>
      </CardActionArea>
      <IconButton aria-label="حذف" onClick={onDelete} sx={{ alignSelf: 'center', mx: 0.5 }}>
        <DeleteOutlined />
      </IconButton>
    </Card>
  );
}

export default function DraftsTab() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const q = useDeferredValue(search.trim());
  const [toDelete, setToDelete] = useState<DraftListItem | null>(null);

  const drafts = useQuery({
    queryKey: [...DRAFTS_QUERY_KEY, q],
    queryFn: () => listDrafts(q),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteDraft(id),
    onSuccess: () => {
      setToDelete(null);
      void queryClient.invalidateQueries({ queryKey: DRAFTS_QUERY_KEY });
    },
  });

  return (
    <Stack spacing={1.5}>
      <TextField
        size="small"
        placeholder="بحث بالاسم أو الهاتف"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined />
              </InputAdornment>
            ),
          },
          htmlInput: { 'aria-label': 'بحث في المسودات' },
        }}
      />

      {drafts.isPending && <Skeleton height={96} />}
      {drafts.isError && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => drafts.refetch()}>
              إعادة المحاولة
            </Button>
          }
        >
          {drafts.error.message}
        </Alert>
      )}
      {drafts.data?.items.length === 0 && (
        <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
          {q ? 'لا توجد نتائج' : 'لا توجد مسودات'}
        </Paper>
      )}
      {drafts.data?.items.map((d) => (
        <DraftCard key={d.id} draft={d} onDelete={() => setToDelete(d)} />
      ))}

      <ConfirmDialog
        open={toDelete !== null}
        title="حذف المسودة نهائياً؟"
        message={`ستُحذف المسودة «${toDelete?.subscriber_name ?? 'بدون اسم'}» وصورها ولا يمكن استرجاعها.`}
        confirmLabel="حذف"
        busy={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete.id)}
        onClose={() => {
          setToDelete(null);
          remove.reset();
        }}
      />
      {remove.isError && <Alert severity="error">{remove.error.message}</Alert>}
    </Stack>
  );
}
