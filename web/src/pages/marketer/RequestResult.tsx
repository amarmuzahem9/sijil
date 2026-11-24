/**
 * /requests/:id — the screen after «إرسال», and a submitted request reopened from «الطلبات»
 * (specs/008 FR-018, FR-019, research R11). Approved: «تمت الموافقة», the number and the
 * username with a small «نسخ اليوزر». Pending: «بانتظار موافقة المسؤول» or «طلبك بانتظار التدقيق».
 * «نسخ التفاصيل» copies the ordered text of system.md v1.11 §5.5 in both cases.
 * Accepted or linked: «رسالة الربط» with copy and WhatsApp share (specs/012 US1). A deleted request (specs/011 R11)
 * shows «تم حذف الطلب», the reason, the number, the tower and the dates, with no copy button.
 */
import CancelOutlined from '@mui/icons-material/CancelOutlined';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import ContentCopyOutlined from '@mui/icons-material/ContentCopyOutlined';
import DeleteIcon from '@mui/icons-material/Delete';
import HourglassTopOutlined from '@mui/icons-material/HourglassTopOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';

import LinkMessageCard from '../../components/LinkMessageCard';
import {
  DELETED_TAG,
  getRequest,
  planLine,
  requestDetailsText,
  RESULT_TEXT,
  type SubmittedRequest,
} from '../../lib/requests';
import { STATUS_COLORS, STATUS_LABELS } from '../../lib/requestStatus';
import { formatBaghdad } from '../../lib/time';

function Row({ label, value }: { label: string; value: string }) {
  return (
    <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
      <Typography color="text.secondary">{label}</Typography>
      <Typography sx={{ fontWeight: 600, textAlign: 'end' }}>{value}</Typography>
    </Stack>
  );
}

function BackButtons() {
  return (
    <Stack direction="row" spacing={1}>
      <Button component={RouterLink} to="/drafts/new" variant="outlined" fullWidth>
        إضافة مشترك جديد
      </Button>
      <Button component={RouterLink} to="/requests" variant="text" fullWidth>
        الطلبات
      </Button>
    </Stack>
  );
}

/** «تم حذف الطلب»: the kept fields only, nothing to copy or share (specs/011 FR-021). */
function DeletedResultView({ request }: { request: SubmittedRequest }) {
  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }} data-testid="request-result">
      <Alert
        severity="info"
        icon={<DeleteIcon />}
        sx={{ fontSize: '1.15rem', fontWeight: 700, alignItems: 'center' }}
      >
        {RESULT_TEXT.deleted}
        <Typography sx={{ mt: 0.5, fontWeight: 400 }}>
          سبب الحذف: {request.deletion_label}
        </Typography>
      </Alert>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.25}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 700 }} dir="ltr">
              {`#${request.number_label}`}
            </Typography>
            <Chip
              label={DELETED_TAG.label}
              data-testid="request-status"
              sx={{ bgcolor: DELETED_TAG.bg, color: DELETED_TAG.fg, fontWeight: 600 }}
            />
          </Stack>
          <Row label="البرج" value={`${request.tower_name} (${request.tower_code})`} />
          <Row label="تاريخ الإرسال" value={formatBaghdad(request.submitted_at)} />
          {request.deleted_at && (
            <Row label="تاريخ الحذف" value={formatBaghdad(request.deleted_at)} />
          )}
        </Stack>
      </Paper>
      <BackButtons />
    </Stack>
  );
}

export function RequestResultView({ request }: { request: SubmittedRequest }) {
  if (request.result === 'deleted') return <DeletedResultView request={request} />;
  return <LiveResultView request={request} />;
}

function LiveResultView({ request }: { request: SubmittedRequest }) {
  const [copied, setCopied] = useState<'details' | 'username' | null>(null);
  const approved = request.result === 'approved' || request.result === 'linked';
  const rejected = request.result === 'rejected';
  const colors = STATUS_COLORS[request.status];

  const copy = async (what: 'details' | 'username') => {
    const text = what === 'details' ? requestDetailsText(request) : request.username;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
    } catch {
      setCopied(null);
    }
  };

  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }} data-testid="request-result">
      <Alert
        severity={approved ? 'success' : rejected ? 'error' : 'warning'}
        icon={
          approved ? (
            <CheckCircleOutlined />
          ) : rejected ? (
            <CancelOutlined />
          ) : (
            <HourglassTopOutlined />
          )
        }
        sx={{ fontSize: '1.15rem', fontWeight: 700, alignItems: 'center' }}
      >
        {RESULT_TEXT[request.result]}
        {rejected && request.rejection_label && (
          <Typography sx={{ mt: 0.5, fontWeight: 400 }}>
            سبب الرفض: <span data-testid="rejection-label">{request.rejection_label}</span>
          </Typography>
        )}
      </Alert>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.25}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6" sx={{ fontWeight: 700 }} dir="ltr">
              {`#${request.number_label}`}
            </Typography>
            <Chip
              label={STATUS_LABELS[request.status]}
              data-testid="request-status"
              sx={{ bgcolor: colors.bg, color: colors.fg, fontWeight: 600 }}
            />
          </Stack>
          <Row label="الاسم" value={request.full_name ?? '—'} />
          <Row label="البرج" value={`${request.tower_name} (${request.tower_code})`} />
          <Row label="الفئة" value={planLine(request)} />
          <Row label="الهاتف" value={request.phone ?? '—'} />
          <Row label="تاريخ الإرسال" value={formatBaghdad(request.submitted_at)} />
          {request.status === 'linked' && request.linked_at && (
            <Row label="تاريخ الربط" value={formatBaghdad(request.linked_at)} />
          )}
          <Stack
            direction="row"
            spacing={1}
            sx={{ justifyContent: 'space-between', alignItems: 'center' }}
          >
            <Typography color="text.secondary">اسم المستخدم</Typography>
            {request.username ? (
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Typography
                  data-testid="request-username"
                  dir="ltr"
                  sx={{ fontFamily: 'monospace', fontWeight: 700 }}
                >
                  {request.username}
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<ContentCopyOutlined fontSize="small" />}
                  onClick={() => void copy('username')}
                >
                  نسخ اليوزر
                </Button>
              </Stack>
            ) : (
              <Typography sx={{ fontWeight: 600 }}>بانتظار الموافقة</Typography>
            )}
          </Stack>
        </Stack>
      </Paper>

      {request.link_message && <LinkMessageCard text={request.link_message} />}

      <Stack spacing={0.5}>
        <Button
          variant={request.link_message ? 'outlined' : 'contained'}
          startIcon={<ContentCopyOutlined />}
          onClick={() => void copy('details')}
        >
          نسخ التفاصيل
        </Button>
        {copied && (
          <Typography variant="caption" color="success.main" sx={{ textAlign: 'center' }}>
            تم النسخ
          </Typography>
        )}
      </Stack>

      <BackButtons />
    </Stack>
  );
}

export default function RequestResult() {
  const { requestId = '' } = useParams<{ requestId: string }>();
  const query = useQuery({
    queryKey: ['requests', 'one', requestId],
    queryFn: () => getRequest(requestId),
    retry: false,
  });
  if (query.isPending) return <CircularProgress aria-label="جارٍ التحميل" />;
  if (query.isError)
    return (
      <Stack spacing={2} sx={{ maxWidth: 640 }}>
        <Alert severity="warning">{query.error.message || 'الطلب غير موجود'}</Alert>
        <Button component={RouterLink} to="/requests" variant="outlined">
          العودة إلى الطلبات
        </Button>
      </Stack>
    );
  return <RequestResultView request={query.data} />;
}
