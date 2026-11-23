/**
 * /requests/:id — the screen after «إرسال», and a submitted request reopened from «الطلبات»
 * (specs/008 FR-018, FR-019, research R11). Approved: «تمت الموافقة», the number and the
 * username with a small «نسخ اليوزر». Pending: «بانتظار موافقة المسؤول» or «طلبك بانتظار التدقيق».
 * «نسخ التفاصيل» copies the ordered text of system.md v1.11 §5.5 in both cases.
 * The link message and its share button come with feature 011.
 */
import CancelOutlined from '@mui/icons-material/CancelOutlined';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import ContentCopyOutlined from '@mui/icons-material/ContentCopyOutlined';
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

import { formatMoney } from '../../lib/money';
import {
  getRequest,
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

export function RequestResultView({ request }: { request: SubmittedRequest }) {
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
          <Row label="الاسم" value={request.full_name} />
          <Row label="البرج" value={`${request.tower_name} (${request.tower_code})`} />
          <Row
            label="الفئة"
            value={`${request.plan_name} | التجريبي ${formatMoney(request.trial_price)} | الثاني ${formatMoney(request.second_price)}`}
          />
          <Row label="الهاتف" value={request.phone} />
          <Row label="تاريخ الإرسال" value={formatBaghdad(request.submitted_at)} />
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

      <Stack spacing={0.5}>
        <Button
          variant="contained"
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

      <Stack direction="row" spacing={1}>
        <Button component={RouterLink} to="/drafts/new" variant="outlined" fullWidth>
          إضافة مشترك جديد
        </Button>
        <Button component={RouterLink} to="/requests" variant="text" fullWidth>
          الطلبات
        </Button>
      </Stack>
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
