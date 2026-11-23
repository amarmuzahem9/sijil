/**
 * The decision area of the review file (docs/system.md v1.14 §6.4, specs/010 US2): «قبول» with a
 * confirmation (and «هل تُحتسب عمولة للمسوّق؟» on a return), «رفض» through RejectDialog. A request
 * decided by someone else gives «تم البت في هذا الطلب مسبقاً» and the file reloads. A decided
 * request is shown read-only.
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
} from '../../../lib/adminRequests';
import { ApiError } from '../../../lib/api';
import { formatBaghdad } from '../../../lib/time';
import { RejectDialog } from './RejectDialog';

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
  const isReturn = file.type === 'return';

  async function run(call: () => Promise<RequestFile>) {
    setBusy(true);
    setError(null);
    try {
      const updated = await call();
      setDialog(null);
      onDecided(updated);
    } catch (err) {
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
      {file.status !== 'pending_review' ? (
        <DecidedView file={file} />
      ) : (
        <Stack direction="row" spacing={1.5}>
          <Button
            variant="contained"
            onClick={() => {
              setCommission(null);
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
      >
        <DialogTitle>قبول الطلب {file.number_label}</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
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
            onClick={confirmAccept}
            disabled={busy || (isReturn && commission === null)}
          >
            تأكيد القبول
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
