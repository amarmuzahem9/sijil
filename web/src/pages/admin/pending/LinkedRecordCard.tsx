/**
 * One record a pending request is linked to (docs/system.md §6.4, specs/010 FR-004): source, why it
 * is linked, and the record's details. Shown to review admins only; never to the marketer.
 * A deleted request shows «سجل محذوف (#T3C-…)» and nothing else (specs/011 R10).
 */
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { ReadOnlyField, ReadOnlyFields } from '../../../components/ReadOnlyField';
import type { ImageKind, LinkedRecord, ReviewReason } from '../../../lib/adminRequests';
import { REASON_STATE_LABELS, SOURCE_LABELS, linkBasisLabel } from '../../../lib/labels';
import { STATUS_COLORS, STATUS_LABELS, type RequestStatus } from '../../../lib/requestStatus';
import { formatBaghdad } from '../../../lib/time';
import { RequestImage } from './RequestImage';

function Images({ ids, kind }: { ids: string[]; kind: ImageKind }) {
  if (ids.length === 0) return null;
  return (
    <Grid container spacing={1}>
      {ids.map((id, i) => (
        <Grid key={id} size={{ xs: 6, sm: 4 }}>
          <RequestImage imageId={id} kind={kind} alt={`صورة السجل ${i + 1}`} height={110} />
        </Grid>
      ))}
    </Grid>
  );
}

/** A legacy subscriber (specs/014 US3, research R12): its old number, the form date, «الحالة»
 * as written in the old file (not a request status), «غير مكتمل», and «بيانات إضافية». It has
 * no username or tower. */
function LegacyFields({ record }: { record: LinkedRecord }) {
  const extra = record.extra ?? {};
  return (
    <>
      <ReadOnlyFields>
        <ReadOnlyField label="الرقم القديم" value={record.legacy_number} ltr />
        <ReadOnlyField label="الاسم" value={record.full_name} />
        <ReadOnlyField label="الهاتف" value={record.phone} ltr />
        <ReadOnlyField
          label="تاريخ الاستمارة"
          value={record.registered_at ? formatBaghdad(record.registered_at) : null}
        />
        <ReadOnlyField label="الحالة في الملف القديم" value={record.status} />
      </ReadOnlyFields>
      <Typography variant="subtitle2">بيانات إضافية</Typography>
      <ReadOnlyFields>
        <ReadOnlyField label="اسم الأم" value={extra.mother_name} />
        <ReadOnlyField label="اسم أب الأم" value={extra.mother_father_name} />
        <ReadOnlyField label="تاريخ الميلاد" value={extra.birth_date} ltr />
      </ReadOnlyFields>
      <Images ids={record.image_ids} kind="legacy" />
    </>
  );
}

export function LinkedRecordCard({ reason }: { reason: ReviewReason }) {
  const record = reason.record;
  if (!record) return null;
  const stateLabel = REASON_STATE_LABELS[reason.state];
  const legacy = record.source === 'legacy';
  const status = legacy ? null : (record.status as RequestStatus | null);
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
          {legacy && record.available && record.incomplete && (
            <Chip size="small" color="warning" label="غير مكتمل" />
          )}
          {stateLabel && <Chip size="small" label={stateLabel} />}
          {reason.added_at_review && <Chip size="small" label="أُضيف بعد التثبيت" />}
        </Stack>
        {record.deleted ? (
          <Typography variant="body2" color="text.secondary">
            سجل محذوف (#{record.number_label})
          </Typography>
        ) : !record.available ? (
          <Typography variant="body2" color="text.secondary">
            سجل غير متوفر
          </Typography>
        ) : legacy ? (
          <LegacyFields record={record} />
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
            <Images ids={record.image_ids} kind="request" />
          </>
        )}
      </Stack>
    </Card>
  );
}
