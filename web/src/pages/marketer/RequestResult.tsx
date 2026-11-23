/**
 * /requests/:id — the screen after «إرسال», and a submitted request reopened from «الطلبات»
 * (specs/008 FR-018, FR-019, research R11). Approved: «تمت الموافقة», the number and the
 * username with «نسخ اليوزر». Pending: «بانتظار موافقة المسؤول» (family) or «طلبك بانتظار التدقيق».
 * The link message and its share button come with feature 011.
 */
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
import { getRequest, RESULT_TEXT, type SubmittedRequest } from '../../lib/requests';
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
  const [copied, setCopied] = useState(false);
  const approved = request.result === 'approved' || request.result === 'linked';
  const colors = STATUS_COLORS[request.status];

  const copy = async () => {
    if (!request.username) return;
    try {
      await navigator.clipboard.writeText(request.username);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }} data-testid="request-result">
      <Alert
        severity={approved ? 'success' : 'warning'}
        icon={approved ? <CheckCircleOutlined /> : <HourglassTopOutlined />}
        sx={{ fontSize: '1.15rem', fontWeight: 700, alignItems: 'center' }}
      >
        {RESULT_TEXT[request.result]}
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
          <Row label="البرج" value={`${request.tower_code} (${request.area_name})`} />
          <Row
            label="الفئة"
            value={`${request.plan_name} | التجريبي ${formatMoney(request.trial_price)} | الثاني ${formatMoney(request.second_price)}`}
          />
          <Row label="الهاتف" value={request.phone} />
          <Row label="تاريخ الإرسال" value={formatBaghdad(request.submitted_at)} />
        </Stack>
      </Paper>

      {approved && request.username && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1}>
            <Typography color="text.secondary">اليوزر</Typography>
            <Typography
              data-testid="request-username"
              dir="ltr"
              sx={{ fontFamily: 'monospace', fontSize: '1.1rem', fontWeight: 700 }}
            >
              {request.username}
            </Typography>
            <Button
              variant="contained"
              startIcon={<ContentCopyOutlined />}
              onClick={() => void copy()}
            >
              نسخ اليوزر
            </Button>
            {copied && (
              <Typography variant="caption" color="success.main">
                تم النسخ
              </Typography>
            )}
          </Stack>
        </Paper>
      )}

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
