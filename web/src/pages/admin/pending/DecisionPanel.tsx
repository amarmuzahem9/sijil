/**
 * The decision area of the review file (docs/system.md v1.14 §6.4, specs/010 US2): «قبول» with a
 * confirmation (and «هل تُحتسب عمولة للمسوّق؟» on a return), «رفض» through RejectDialog. A request
 * decided by someone else gives «تم البت في هذا الطلب مسبقاً» and the file reloads. A decided
 * request is shown read-only.
 *
 * Warnings (FR-019a) show as a red alert, and «قبول» then asks «القبول رغم التحذير؟» and sends the
 * kinds it showed. If the server finds a different set (409 `warnings_unconfirmed`), the file
 * reloads and the confirmation asks again with the new kinds (research R7).
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormLabel from '@mui/material/FormLabel';
import Paper from '@mui/material/Paper';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useId, useState } from 'react';

import { ReadOnlyField, ReadOnlyFields } from '../../../components/ReadOnlyField';
import {
  accept,
  reject,
  type AcceptBody,
  type RejectBody,
  type RequestFile,
  type ReviewWarning,
} from '../../../lib/adminRequests';
import { ApiError } from '../../../lib/api';
import { WARNING_ALERT_LABELS } from '../../../lib/labels';
import { formatBaghdad } from '../../../lib/time';
import { RejectDialog } from './RejectDialog';

/** The rule reminders next to the buttons (system.md §6.4, specs/010 US4: FR-016). The admin
 * applies the 15-day rule by hand; the SAS expiry exists only after 014. */
/** A left-to-right value isolated inside an Arabic line (LRI … PDI). */
const LRI = String.fromCodePoint(0x2066);
const PDI = String.fromCodePoint(0x2069);
const ltr = (value: string) => `${LRI}${value}${PDI}`;

function Reminders({ file }: { file: RequestFile }) {
  const family = file.reasons.filter((r) => r.reason === 'family_exists' && r.state === 'open');
  const isReturn = file.type === 'return';
  if (family.length === 0 && !isReturn) return null;
  return (
    // A standing note, not an alert: screen readers should not announce it as one.
    <Alert severity="info" variant="outlined" role="note" sx={{ mb: 2 }}>
      <Stack spacing={0.5}>
        {family.length > 0 && (
          <>
            <span>إذا كان للاشتراك الأول 15 يوماً أو أكثر متبقية: قبول. أقل من ذلك: رفض.</span>
            {family.map((r, i) =>
              r.record?.expiry ? (
                <span key={i}>
                  {`تاريخ انتهاء الاشتراك الأول: ${ltr(r.record.expiry)} (حسب آخر استيراد)`}
                </span>
              ) : (
                <span key={i}>تاريخ الانتهاء غير متوفر</span>
              ),
            )}
          </>
        )}
        {isReturn && <span>سيُطلب تحديد احتساب العمولة</span>}
      </Stack>
    </Alert>
  );
}

function DecidedView({ file }: { file: RequestFile }) {
  const d = file.decision;
  if (!d) return null;
  const approved = d.status === 'approved';
  return (
    <Stack spacing={2}>
      <Typography sx={{ fontWeight: 700 }} color={approved ? 'primary' : 'error'}>
        {approved ? 'تم القبول' : 'تم رفض الطلب'}
      </Typography>
      <ReadOnlyFields>
        <ReadOnlyField label="بواسطة" value={d.by ?? 'قبول تلقائي'} />
        <ReadOnlyField label="الوقت" value={formatBaghdad(d.at)} />
        {approved && file.type === 'return' && (
          <ReadOnlyField label="احتساب العمولة" value={d.counts_commission ? 'نعم' : 'لا'} />
        )}
        {!approved && <ReadOnlyField label="سبب الرفض" value={d.label} wide />}
      </ReadOnlyFields>
    </Stack>
  );
}

export function DecisionPanel({
  file,
  onDecided,
  onRefresh,
}: {
  file: RequestFile;
  onDecided: (file: RequestFile) => void;
  /** Reload the file (another admin decided first). */
  onRefresh: () => void;
}) {
  const titleId = useId();
  const [dialog, setDialog] = useState<'accept' | 'reject' | null>(null);
  const [commission, setCommission] = useState<'yes' | 'no' | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The kinds the server reported on a refused accept; the file's own list otherwise.
  const [serverWarnings, setServerWarnings] = useState<ReviewWarning[] | null>(null);
  const isReturn = file.type === 'return';
  const warnings = serverWarnings ?? file.warnings;
  const warned = warnings.length > 0;

  async function run(call: () => Promise<RequestFile>) {
    setBusy(true);
    setError(null);
    try {
      const updated = await call();
      setDialog(null);
      onDecided(updated);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'warnings_unconfirmed') {
        // Keep the dialog open and ask again with what the server found now.
        setServerWarnings((err.extra.warnings as ReviewWarning[] | undefined) ?? []);
        onRefresh();
        return;
      }
      setDialog(null);
      if (err instanceof ApiError && err.code === 'already_decided') onRefresh();
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function confirmAccept() {
    const body: AcceptBody = {};
    if (isReturn) body.counts_commission = commission === 'yes';
    if (warned) body.confirm_warnings = [...warnings];
    void run(() => accept(file.id, body));
  }

  function confirmReject(body: RejectBody) {
    void run(() => reject(file.id, body));
  }

  return (
    <Paper component="section" aria-labelledby={titleId} variant="outlined" sx={{ p: 2 }}>
      <Typography id={titleId} variant="subtitle1" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
        القرار
      </Typography>
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {file.status === 'pending_review' && warned && (
        <Alert severity="error" variant="outlined" sx={{ mb: 2 }}>
          <Stack component="ul" spacing={0.5} sx={{ m: 0, pr: 2, pl: 0 }}>
            {warnings.map((w) => (
              <li key={w}>{WARNING_ALERT_LABELS[w]}</li>
            ))}
          </Stack>
        </Alert>
      )}
      {file.status === 'pending_review' && <Reminders file={file} />}
      {file.status !== 'pending_review' ? (
        <DecidedView file={file} />
      ) : (
        <Stack direction="row" spacing={1.5}>
          <Button
            variant="contained"
            onClick={() => {
              setCommission(null);
              setServerWarnings(null);
              setDialog('accept');
            }}
            disabled={busy}
          >
            قبول
          </Button>
          <Button
            variant="outlined"
            color="error"
            onClick={() => setDialog('reject')}
            disabled={busy}
          >
            رفض
          </Button>
        </Stack>
      )}

      <Dialog
        open={dialog === 'accept'}
        onClose={busy ? undefined : () => setDialog(null)}
        maxWidth="xs"
        fullWidth
        aria-labelledby={`${titleId}-accept`}
      >
        <DialogTitle id={`${titleId}-accept`} color={warned ? 'error' : undefined}>
          {warned ? 'القبول رغم التحذير؟' : `قبول الطلب ${file.number_label}`}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            {warned && (
              <Alert severity="error" variant="outlined">
                <Stack component="ul" spacing={0.5} sx={{ m: 0, pr: 2, pl: 0 }}>
                  {warnings.map((w) => (
                    <li key={w}>{WARNING_ALERT_LABELS[w]}</li>
                  ))}
                </Stack>
                القبول رغم التحذير يُسجَّل بسجل العمليات.
              </Alert>
            )}
            <DialogContentText>
              سيصير الطلب {file.number_label} مقبولاً (بانتظار الربط).
            </DialogContentText>
            {isReturn && (
              <FormControl>
                <FormLabel id={`${titleId}-commission`}>هل تُحتسب عمولة للمسوّق؟</FormLabel>
                <RadioGroup
                  row
                  aria-labelledby={`${titleId}-commission`}
                  value={commission ?? ''}
                  onChange={(e) => setCommission(e.target.value as 'yes' | 'no')}
                >
                  <FormControlLabel value="yes" control={<Radio />} label="نعم" />
                  <FormControlLabel value="no" control={<Radio />} label="لا" />
                </RadioGroup>
              </FormControl>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(null)} disabled={busy}>
            إلغاء
          </Button>
          <Button
            variant="contained"
            color={warned ? 'error' : 'primary'}
            onClick={confirmAccept}
            disabled={busy || (isReturn && commission === null)}
          >
            {warned ? 'القبول رغم التحذير' : 'تأكيد القبول'}
          </Button>
        </DialogActions>
      </Dialog>

      <RejectDialog
        open={dialog === 'reject'}
        numberLabel={file.number_label}
        busy={busy}
        onSubmit={confirmReject}
        onClose={() => setDialog(null)}
      />
    </Paper>
  );
}
