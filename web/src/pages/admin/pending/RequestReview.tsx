/**
 * The review file of one request (docs/system.md §6.4, specs/010 US1: FR-003, FR-004, FR-012):
 * البطاقة، الموقع، الاشتراك، الهاتف، الأسباب، and the decision area (US2). Every value sits in a
 * read-only box like the form's inputs; two columns on a computer, one on a phone.
 */
import ArrowForward from '@mui/icons-material/ArrowForward';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useId, type ReactNode } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';

import { ReadOnlyField, ReadOnlyFields } from '../../../components/ReadOnlyField';
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
      <Typography id={id} variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
        {title}
      </Typography>
      {children}
    </Paper>
  );
}

/** «لم تقرأه البطاقة» or «القراءة: …» when the stored name differs from the card reading. */
function nameNote(file: RequestFile, name: string): string | undefined {
  const value = file.names[name];
  const read = file.names_reading[name];
  if (!read) return 'لم تقرأه البطاقة';
  if (read !== value) return `القراءة: ${read}`;
  return undefined;
}

function CardSection({ file }: { file: RequestFile }) {
  return (
    <Section title="البطاقة">
      <Stack spacing={2.5}>
        <ReadOnlyFields>
          <ReadOnlyField label="الاسم الكامل" value={file.full_name} wide />
          {Object.keys(NAME_LABELS).map((name) =>
            file.names[name] ? (
              <ReadOnlyField
                key={name}
                label={NAME_LABELS[name]}
                value={file.names[name]}
                note={nameNote(file, name)}
              />
            ) : null,
          )}
          <ReadOnlyField label="الرقم الوطني" value={file.national_id} ltr />
          <ReadOnlyField label="الرقم العائلي" value={file.family_number} ltr />
          <ReadOnlyField label="تاريخ الولادة" value={file.birth_date} ltr />
          <ReadOnlyField label="محل الولادة" value={file.birth_place} />
          <ReadOnlyField label="تاريخ الإصدار" value={file.issue_date} ltr />
          <ReadOnlyField label="تاريخ النفاذ" value={file.expiry_date} ltr />
          <ReadOnlyField label="جهة الإصدار" value={file.issuing_authority} wide />
        </ReadOnlyFields>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            gap: 2,
          }}
        >
          {file.images.map((image) => (
            <RequestImage
              key={image.id}
              imageId={image.id}
              alt={image.side === 'front' ? 'وجه البطاقة' : 'ظهر البطاقة'}
              height={240}
            />
          ))}
        </Box>
      </Stack>
    </Section>
  );
}

function LocationSection({ file }: { file: RequestFile }) {
  const { lat, lng } = file.location;
  return (
    <Section title="الموقع">
      <ReadOnlyFields>
        <ReadOnlyField label="العنوان" value={file.address} />
        <ReadOnlyField label="أقرب نقطة دالّة" value={file.landmark} />
        <ReadOnlyField
          label="الإحداثيات"
          value={`${lat}, ${lng}`}
          ltr
          note={
            <Link
              href={`https://maps.google.com/?q=${lat},${lng}`}
              target="_blank"
              rel="noopener"
              color="primary"
            >
              فتح على الخريطة
            </Link>
          }
        />
      </ReadOnlyFields>
    </Section>
  );
}

function SubscriptionSection({ file }: { file: RequestFile }) {
  return (
    <Section title="الاشتراك">
      <ReadOnlyFields>
        <ReadOnlyField label="المنطقة" value={file.area_name} />
        <ReadOnlyField label="البرج" value={`${file.tower_name} (${file.tower_code})`} />
        <ReadOnlyField
          label="الفئة"
          value={`${file.plan_name} | التجريبي ${formatMoney(file.trial_price)} | الثاني ${formatMoney(file.second_price)}`}
          wide
        />
        <ReadOnlyField label="اليوزر" value={file.username} ltr />
        <ReadOnlyField label="المسوّق" value={file.marketer_name} />
      </ReadOnlyFields>
    </Section>
  );
}

function PhoneSection({ file }: { file: RequestFile }) {
  return (
    <Section title="الهاتف">
      <ReadOnlyFields>
        <ReadOnlyField label="هاتف الاشتراك" value={file.phone} ltr />
        <ReadOnlyField label="وقت التحقق" value={formatBaghdad(file.otp_verified_at)} />
      </ReadOnlyFields>
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
