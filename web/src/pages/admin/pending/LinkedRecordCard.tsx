/**
 * One record a pending request is linked to (docs/system.md §6.4, specs/010 FR-004): source, why it
 * is linked, and the record's details. Shown to review admins only; never to the marketer.
 */
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { ReadOnlyField, ReadOnlyFields } from '../../../components/ReadOnlyField';
import type { ReviewReason } from '../../../lib/adminRequests';
import { REASON_STATE_LABELS, SOURCE_LABELS, linkBasisLabel } from '../../../lib/labels';
import { STATUS_COLORS, STATUS_LABELS, type RequestStatus } from '../../../lib/requestStatus';
import { formatBaghdad } from '../../../lib/time';
import { RequestImage } from './RequestImage';

export function LinkedRecordCard({ reason }: { reason: ReviewReason }) {
  const record = reason.record;
  if (!record) return null;
  const stateLabel = REASON_STATE_LABELS[reason.state];
  const status = record.status as RequestStatus | null;
  return (
    <Card variant="outlined" sx={{ p: 1.5, opacity: reason.state === 'not_applicable' ? 0.7 : 1 }}>
      <Stack spacing={2}>
        <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
          <Typography sx={{ fontWeight: 700 }}>
            {linkBasisLabel(reason.reason, reason.basis)}
          </Typography>
          <Chip
            size="small"
            variant="outlined"
            label={SOURCE_LABELS[record.source] ?? record.source}
          />
          {status && STATUS_LABELS[status] && (
            <Chip
              size="small"
              label={STATUS_LABELS[status]}
              sx={{ bgcolor: STATUS_COLORS[status].bg, color: STATUS_COLORS[status].fg }}
            />
          )}
          {stateLabel && <Chip size="small" label={stateLabel} />}
          {reason.added_at_review && <Chip size="small" label="أُضيف بعد التثبيت" />}
        </Stack>
        {!record.available ? (
          <Typography variant="body2" color="text.secondary">
            سجل غير متوفر
          </Typography>
        ) : (
          <>
            <ReadOnlyFields>
              <ReadOnlyField label="الاسم" value={record.full_name} />
              <ReadOnlyField label="اليوزر" value={record.username} ltr />
              <ReadOnlyField label="الهاتف" value={record.phone} ltr />
              <ReadOnlyField
                label="البرج"
                value={
                  record.tower_name
                    ? `${record.tower_name} (${record.tower_code})`
                    : record.tower_code
                }
              />
              <ReadOnlyField
                label="تاريخ التسجيل"
                value={record.registered_at ? formatBaghdad(record.registered_at) : null}
              />
            </ReadOnlyFields>
            {record.image_ids.length > 0 && (
              <Grid container spacing={1}>
                {record.image_ids.map((id, i) => (
                  <Grid key={id} size={{ xs: 6, sm: 4 }}>
                    <RequestImage imageId={id} alt={`صورة السجل ${i + 1}`} height={110} />
                  </Grid>
                ))}
              </Grid>
            )}
          </>
        )}
      </Stack>
    </Card>
  );
}
