/**
 * The review file of one request (docs/system.md §6.4, specs/010 US1: FR-003, FR-004, FR-012):
 * البطاقة، الموقع، الاشتراك، الهاتف، الأسباب، and the decision area (US2). RTL; stacks on a phone.
 */
import ArrowForward from '@mui/icons-material/ArrowForward';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useId, type ReactNode } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';

import { getRequestFile, type RequestFile } from '../../../lib/adminRequests';
import { REASON_LABELS, REASON_STATE_LABELS, REQUEST_TYPE_LABELS } from '../../../lib/labels';
import { formatMoney } from '../../../lib/money';
import { STATUS_COLORS, STATUS_LABELS } from '../../../lib/requestStatus';
import { formatBaghdad } from '../../../lib/time';
import { LinkedRecordCard } from './LinkedRecordCard';
import { RequestImage } from './RequestImage';

const NAME_LABELS: Record<string, string> = {
  first_name: 'الاسم الأول',
  father_name: 'اسم الأب',
  grandfather_name: 'اسم الجد',
  great_grandfather_name: 'اسم أب الجد',
  surname: 'اللقب',
  mother_first_name: 'اسم الأم',
  mother_second_name: 'اسم أب الأم',
  mother_third_name: 'اسم جد الأم',
  mother_surname: 'لقب الأم',
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <Paper component="section" aria-labelledby={id} variant="outlined" sx={{ p: 2 }}>
      <Typography id={id} variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 1.5 }}>
        {title}
      </Typography>
      {children}
    </Paper>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Stack spacing={0.25}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography component="div" dir="auto" sx={{ overflowWrap: 'anywhere' }}>
        {children}
      </Typography>
    </Stack>
  );
}

function NameField({ file, name }: { file: RequestFile; name: string }) {
  const value = file.names[name];
  if (!value) return null;
  const read = file.names_reading[name];
  const note = !read ? 'لم تقرأه البطاقة' : read !== value ? `القراءة: ${read}` : null;
  return (
    <Field label={NAME_LABELS[name] ?? name}>
      {value}
      {note && (
        <Typography component="span" variant="caption" color="warning.main" sx={{ mx: 1 }}>
          ({note})
        </Typography>
      )}
    </Field>
  );
}

function CardSection({ file }: { file: RequestFile }) {
  return (
    <Section title="البطاقة">
      <Stack spacing={2}>
        <Field label="الاسم الكامل">{file.full_name}</Field>
        <Grid container spacing={1.5}>
          {Object.keys(NAME_LABELS).map((name) =>
            file.names[name] ? (
              <Grid key={name} size={{ xs: 6, sm: 4 }}>
                <NameField file={file} name={name} />
              </Grid>
            ) : null,
          )}
        </Grid>
        <Grid container spacing={1.5}>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Field label="الرقم الوطني">
              <span dir="ltr">{file.national_id}</span>
            </Field>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Field label="الرقم العائلي">
              <span dir="ltr">{file.family_number}</span>
            </Field>
          </Grid>
          <Grid size={{ xs: 6, sm: 4 }}>
            <Field label="تاريخ الولادة">{file.birth_date}</Field>
          </Grid>
          <Grid size={{ xs: 6, sm: 4 }}>
            <Field label="محل الولادة">{file.birth_place}</Field>
          </Grid>
          <Grid size={{ xs: 6, sm: 4 }}>
            <Field label="تاريخ الإصدار">{file.issue_date}</Field>
          </Grid>
          <Grid size={{ xs: 6, sm: 4 }}>
            <Field label="تاريخ النفاذ">{file.expiry_date}</Field>
          </Grid>
          <Grid size={{ xs: 12, sm: 8 }}>
            <Field label="جهة الإصدار">{file.issuing_authority}</Field>
          </Grid>
        </Grid>
        <Grid container spacing={1.5}>
          {file.images.map((image) => (
            <Grid key={image.id} size={{ xs: 12, sm: 6 }}>
              <RequestImage
                imageId={image.id}
                alt={image.side === 'front' ? 'وجه البطاقة' : 'ظهر البطاقة'}
                height={240}
              />
            </Grid>
          ))}
        </Grid>
      </Stack>
    </Section>
  );
}

function LocationSection({ file }: { file: RequestFile }) {
  const { lat, lng } = file.location;
  return (
    <Section title="الموقع">
      <Stack spacing={1.5}>
        <Field label="العنوان">{file.address}</Field>
        <Field label="أقرب نقطة دالّة">{file.landmark}</Field>
        <Field label="الإحداثيات">
          <span dir="ltr">
            {lat}, {lng}
          </span>{' '}
          <Link href={`https://maps.google.com/?q=${lat},${lng}`} target="_blank" rel="noopener">
            فتح على الخريطة
          </Link>
        </Field>
      </Stack>
    </Section>
  );
}

function SubscriptionSection({ file }: { file: RequestFile }) {
  return (
    <Section title="الاشتراك">
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Field label="المنطقة والبرج">
            {file.area_name} · {file.tower_name} ({file.tower_code})
          </Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Field label="الفئة">
            {file.plan_name} | التجريبي {formatMoney(file.trial_price)} | الثاني{' '}
            {formatMoney(file.second_price)}
          </Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Field label="اليوزر">
            <span dir="ltr">{file.username}</span>
          </Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Field label="المسوّق">{file.marketer_name}</Field>
        </Grid>
      </Grid>
    </Section>
  );
}

function PhoneSection({ file }: { file: RequestFile }) {
  return (
    <Section title="الهاتف">
      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Field label="هاتف الاشتراك">
            <span dir="ltr">{file.phone}</span>
          </Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Field label="وقت التحقق">{formatBaghdad(file.otp_verified_at)}</Field>
        </Grid>
      </Grid>
    </Section>
  );
}

function ReasonsSection({ file }: { file: RequestFile }) {
  if (file.reasons.length === 0) return null;
  return (
    <Section title="الأسباب">
      <Stack spacing={1.5}>
        {file.reasons.map((reason, i) => {
          const state = REASON_STATE_LABELS[reason.state];
          return (
            <Stack key={i} spacing={1}>
              {!reason.record && (
                <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Typography sx={{ fontWeight: 700 }}>{REASON_LABELS[reason.reason]}</Typography>
                  {state && <Chip size="small" label={state} />}
                </Stack>
              )}
              <LinkedRecordCard reason={reason} />
            </Stack>
          );
        })}
      </Stack>
    </Section>
  );
}

export function RequestReviewView({
  file,
  decision,
}: {
  file: RequestFile;
  /** The decision area (US2); rendered under the file. */
  decision?: ReactNode;
}) {
  const color = STATUS_COLORS[file.status];
  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography variant="h6" component="h1" sx={{ fontWeight: 700 }}>
          الطلب <span dir="ltr">{file.number_label}</span>
        </Typography>
        <Chip
          size="small"
          label={STATUS_LABELS[file.status]}
          sx={{ bgcolor: color.bg, color: color.fg }}
        />
        <Typography color="text.secondary">النوع: {REQUEST_TYPE_LABELS[file.type]}</Typography>
        <Typography variant="body2" color="text.secondary">
          أُرسل {formatBaghdad(file.submitted_at)}
        </Typography>
      </Stack>
      <ReasonsSection file={file} />
      <CardSection file={file} />
      <LocationSection file={file} />
      <SubscriptionSection file={file} />
      <PhoneSection file={file} />
      {decision}
    </Stack>
  );
}

export default function RequestReview() {
  const { requestId = '' } = useParams<{ requestId: string }>();
  const query = useQuery({
    queryKey: ['admin', 'request', requestId],
    queryFn: () => getRequestFile(requestId),
  });
  return (
    <Stack spacing={2}>
      <div>
        <Button component={RouterLink} to="/admin/pending" startIcon={<ArrowForward />}>
          طلبات بالانتظار
        </Button>
      </div>
      {query.isPending && <Skeleton variant="rounded" height={320} />}
      {query.isError && <Paper sx={{ p: 2 }}>{query.error.message}</Paper>}
      {query.data && <RequestReviewView file={query.data} />}
    </Stack>
  );
}
