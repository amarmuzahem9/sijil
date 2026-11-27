import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import MuiLink from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';

import {
  DELETION_REASON_LABELS,
  HISTORY_KIND_LABELS,
  LINK_REASON_LABELS,
  PIN_FIELD_LABELS,
  REJECTION_REASON_LABELS,
  REQUEST_TYPE_LABELS,
  SUBSCRIBER_SOURCE_LABELS,
  UNLINK_REASON_LABELS,
  type SubscriberSource,
} from '../../../lib/labels';
import { STATUS_COLORS, STATUS_LABELS, type RequestStatus } from '../../../lib/requestStatus';
import {
  getSubscriberFile,
  type HistoryEvent,
  type LinkedRecord,
  type SubscriberRecord,
} from '../../../lib/subscribers';
import { formatBaghdad } from '../../../lib/time';
import { RequestImage } from '../pending/RequestImage';

const CARD_FIELD_LABELS: Record<string, string> = {
  birth_date: 'تاريخ الميلاد',
  issue_date: 'تاريخ الإصدار',
  expiry_date: 'تاريخ النفاذ',
  birth_place: 'محل الولادة',
  issuing_authority: 'جهة الإصدار',
};
const EXTRA_LABELS: Record<string, string> = {
  mother_name: 'اسم الأم',
  mother_father_name: 'اسم أب الأم',
  birth_date: 'تاريخ الميلاد',
};

function label<T extends Record<string, string>>(map: T, key: string | null | undefined) {
  if (!key) return null;
  return (map as Record<string, string>)[key] ?? key;
}

function Field({ name, children }: { name: string; children: ReactNode }) {
  return (
    <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 110 }}>
        {name}
      </Typography>
      <Typography variant="body2" component="div" dir="auto">
        {children}
      </Typography>
    </Stack>
  );
}

function StatusChip({ source, status }: { source: SubscriberSource; status: string | null }) {
  if (!status) return null;
  if (source === 'sijil') {
    const color = STATUS_COLORS[status as RequestStatus];
    return (
      <Chip
        size="small"
        label={STATUS_LABELS[status as RequestStatus] ?? status}
        sx={color ? { bgcolor: color.bg, color: color.fg, fontWeight: 600 } : undefined}
      />
    );
  }
  return null;
}

function Header({ record }: { record: SubscriberRecord }) {
  const number = record.number_label ?? record.legacy_number;
  return (
    <Stack spacing={1}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Chip size="small" variant="outlined" label={SUBSCRIBER_SOURCE_LABELS[record.source]} />
        {number && (
          <Typography dir="ltr" component="span">
            {number}
          </Typography>
        )}
        <StatusChip source={record.source} status={record.status} />
        {record.incomplete && <Chip size="small" color="warning" label="غير مكتمل" />}
        {record.no_documents && (
          <Chip size="small" variant="outlined" label="بلا مستمسكات في سِجلّ" />
        )}
      </Stack>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        {record.deleted ? 'سجل محذوف' : (record.full_name ?? '—')}
      </Typography>
    </Stack>
  );
}

function Details({ record }: { record: SubscriberRecord }) {
  const tower =
    record.tower_name && record.tower_code
      ? `${record.tower_name} (${record.tower_code})`
      : (record.tower_code ?? record.tower_name);
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={0.75}>
        {record.phone && <Field name="الهاتف">{record.phone}</Field>}
        {record.username_phone && record.username_phone !== record.phone && (
          <Field name="هاتف اليوزر">{record.username_phone}</Field>
        )}
        {record.username && <Field name="اليوزر">{record.username}</Field>}
        {tower && <Field name="البرج">{tower}</Field>}
        {record.type && <Field name="النوع">{label(REQUEST_TYPE_LABELS, record.type)}</Field>}
        {record.marketer_name && <Field name="المسوّق">{record.marketer_name}</Field>}
        {record.registered_at && (
          <Field name="تاريخ التسجيل">{formatBaghdad(record.registered_at)}</Field>
        )}
        {record.status_text && <Field name="الحالة في الملف">{record.status_text}</Field>}
        {record.extra &&
          Object.entries(record.extra)
            .filter(([, v]) => v)
            .map(([k, v]) => (
              <Field key={k} name={EXTRA_LABELS[k] ?? k}>
                {v}
              </Field>
            ))}
        {record.source === 'sas' && (
          <>
            <Field name="الانتهاء">
              {record.expires_at
                ? `${record.expires_at.slice(0, 10)} حسب آخر استيراد`
                : 'غير معروف حسب آخر استيراد'}
            </Field>
            {record.group_name && <Field name="الباقة">{record.group_name}</Field>}
            {record.last_online_at && (
              <Field name="آخر اتصال">{formatBaghdad(record.last_online_at)}</Field>
            )}
            {record.missing_since && (
              <Field name="ملاحظة">
                {`غير موجود في آخر ملف منذ ${formatBaghdad(record.missing_since)}`}
              </Field>
            )}
          </>
        )}
      </Stack>
    </Paper>
  );
}

/** National ID, family number, card fields and images: present only for `review` (owner Q2). */
function Identity({ record }: { record: SubscriberRecord }) {
  const hasNumbers = 'national_id' in record || 'family_number' in record;
  const fields = record.card_fields ? Object.entries(record.card_fields).filter(([, v]) => v) : [];
  const images = record.images ?? [];
  if (!hasNumbers && fields.length === 0 && images.length === 0) return null;
  const kind = record.source === 'legacy' ? 'legacy' : 'request';
  return (
    <Paper variant="outlined" sx={{ p: 2 }} data-testid="identity-block">
      <Stack spacing={0.75}>
        <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 700 }}>
          المستمسكات
        </Typography>
        {record.national_id && (
          <Field name="الرقم الوطني">
            <span dir="ltr">{record.national_id}</span>
          </Field>
        )}
        {record.family_number && (
          <Field name="الرقم العائلي">
            <span dir="ltr">{record.family_number}</span>
          </Field>
        )}
        {fields.map(([k, v]) => (
          <Field key={k} name={CARD_FIELD_LABELS[k] ?? k}>
            {v}
          </Field>
        ))}
        {images.length > 0 && (
          <Box
            sx={{
              display: 'grid',
              gap: 1,
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            }}
          >
            {images.map((image) => (
              <RequestImage
                key={image.id}
                imageId={image.id}
                kind={kind}
                alt={image.side === 'front' ? 'وجه البطاقة' : 'ظهر البطاقة'}
              />
            ))}
          </Box>
        )}
      </Stack>
    </Paper>
  );
}

function historyText(event: HistoryEvent): string {
  const parts: string[] = [];
  if (event.kind === 'approved' && event.by_name === null) parts.push('قُبل تلقائياً');
  else parts.push(HISTORY_KIND_LABELS[event.kind] ?? event.kind);
  if (event.by_name) parts.push(event.by_name);
  if (event.kind === 'pinned' && event.field) parts.push(label(PIN_FIELD_LABELS, event.field)!);
  if (event.reason) {
    const map =
      event.kind === 'rejected'
        ? REJECTION_REASON_LABELS
        : event.kind === 'deleted'
          ? DELETION_REASON_LABELS
          : UNLINK_REASON_LABELS;
    parts.push(label(map, event.reason)!);
  }
  parts.push(formatBaghdad(event.at));
  return parts.join(' · ');
}

function History({ events }: { events: HistoryEvent[] }) {
  if (events.length === 0) return null;
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 1 }}>
        سجل الطلب
      </Typography>
      <Stack component="ol" spacing={0.5} sx={{ m: 0, ps: 2.5 }}>
        {events.map((e, i) => (
          <Typography key={i} component="li" variant="body2" data-testid="history-line">
            {historyText(e)}
          </Typography>
        ))}
      </Stack>
    </Paper>
  );
}

function Linked({ items, more }: { items: LinkedRecord[]; more: number }) {
  return (
    <Stack spacing={1}>
      <Typography variant="subtitle1" component="h2" sx={{ fontWeight: 700 }}>
        السجلات المرتبطة
      </Typography>
      {items.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          لا توجد سجلات مرتبطة
        </Typography>
      )}
      {items.map(({ reason, row }) => (
        <Card key={`${row.source}-${row.ref}`} variant="outlined" data-testid="linked-record">
          <CardActionArea component={RouterLink} to={`/admin/subscribers/${row.source}/${row.ref}`}>
            <CardContent sx={{ py: 1.25, '&:last-child': { pb: 1.25 } }}>
              <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Chip size="small" color="primary" label={LINK_REASON_LABELS[reason]} />
                <Chip
                  size="small"
                  variant="outlined"
                  label={SUBSCRIBER_SOURCE_LABELS[row.source]}
                />
                <Typography sx={{ fontWeight: 600 }}>{row.full_name ?? '—'}</Typography>
                {(row.number_label ?? row.legacy_number) && (
                  <Typography variant="body2" dir="ltr" component="span">
                    {row.number_label ?? row.legacy_number}
                  </Typography>
                )}
                {row.phone && (
                  <Typography variant="body2" color="text.secondary" component="span">
                    {row.phone}
                  </Typography>
                )}
              </Stack>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
      {more > 0 && (
        <Typography variant="body2" color="text.secondary">{`و ${more} سجلات أخرى`}</Typography>
      )}
    </Stack>
  );
}

/**
 * The subscriber's file (docs/system.md v1.24 §10 item 4; specs/018 US2): one record, its linked
 * records with the reason of each, and a request's history. Read-only (owner Q3). What it shows
 * of identity documents is exactly what the server sent for this admin (owner Q2).
 */
export default function SubscriberFile() {
  const { source, ref } = useParams() as { source: SubscriberSource; ref: string };
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['subscriber-file', source, ref],
    queryFn: () => getSubscriberFile(source, ref),
  });

  return (
    <Stack spacing={2} sx={{ maxWidth: 760 }}>
      <MuiLink component={RouterLink} to="/admin/subscribers" variant="body2">
        رجوع إلى البحث
      </MuiLink>
      {isPending && <Skeleton height={160} />}
      {isError && <Alert severity="error">{error.message}</Alert>}
      {data && (
        <>
          <Header record={data.record} />
          {!data.record.deleted && <Details record={data.record} />}
          {!data.record.deleted && <Identity record={data.record} />}
          <History events={data.history} />
          {!data.record.deleted && <Linked items={data.linked} more={data.more_linked} />}
        </>
      )}
    </Stack>
  );
}
