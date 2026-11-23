/**
 * «تحقّق» next to the subscriber phone (docs/system.md §5.4, §8.3; specs/007 contracts/api.md).
 *
 * Shows the server's `otp` state: the button, the code box with the 60 s resend countdown, and
 * ✓ «تم التحقق» or «يحتاج تحقق جديد». The page never knows the code: it only sends what the
 * marketer typed, and the server decides. Nothing is stored on the device.
 */
import CheckCircle from '@mui/icons-material/CheckCircle';
import WarningAmber from '@mui/icons-material/WarningAmber';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';

import { ApiError } from '../../../lib/api';
import type { OtpStatus } from '../../../lib/drafts';
import { CODE_LENGTH, normalizeCodeEntry, OTP_TEXT } from '../../../lib/otp';

function secondsUntil(iso: string | null | undefined, now: number): number {
  if (!iso) return 0;
  return Math.max(0, Math.ceil((Date.parse(iso) - now) / 1000));
}

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : 'حدث خطأ غير متوقع، حاول مرة أخرى';
}

/** Ticks once a second while `until` is set, so the countdown text stays current. */
function useNow(until: string | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!until) return undefined;
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0); // a new `until` is shown from the current time at once
    const timer = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [until]);
  return now;
}

/** The code box; remounted (empty) for each new code, see the `key` below. */
function CodeEntry({ busy, onConfirm }: { busy: boolean; onConfirm: (code: string) => void }) {
  const [code, setCode] = useState('');
  const ready = code.length === CODE_LENGTH && !busy;
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
      <TextField
        label={OTP_TEXT.codeLabel}
        value={code}
        onChange={(e) => setCode(normalizeCodeEntry(e.target.value))}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && ready) onConfirm(code);
        }}
        size="small"
        autoComplete="one-time-code"
        slotProps={{
          htmlInput: {
            inputMode: 'numeric',
            autoComplete: 'one-time-code',
            dir: 'ltr',
            'data-testid': 'otp-code',
            style: { letterSpacing: '0.3em', textAlign: 'center' },
          },
        }}
        sx={{ maxWidth: 180 }}
      />
      <Button
        variant="contained"
        onClick={() => onConfirm(code)}
        disabled={!ready}
        data-testid="otp-confirm"
      >
        {OTP_TEXT.confirm}
      </Button>
    </Stack>
  );
}

export interface OtpControlProps {
  otp: OtpStatus | undefined;
  /** The typed phone is valid per §8.1 (instant check; the server re-checks). */
  phoneValid: boolean;
  enabled: boolean;
  onSend: () => Promise<void>;
  onVerify: (code: string) => Promise<void>;
}

export function OtpControl({ otp, phoneValid, enabled, onSend, onVerify }: OtpControlProps) {
  const status = otp?.status ?? 'none';
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A server-side wait (429 retry_after_s) when the status itself carries no resend time.
  const [waitUntil, setWaitUntil] = useState<string | null>(null);
  const resendAt = otp?.resend_at ?? waitUntil;
  const now = useNow(resendAt);
  const wait = secondsUntil(resendAt, now);

  if (!enabled) {
    return (
      <Alert severity="info" data-testid="otp-not-configured">
        {OTP_TEXT.notConfigured}
      </Alert>
    );
  }

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(messageOf(err));
      const retry = err instanceof ApiError ? err.extra.retry_after_s : undefined;
      if (typeof retry === 'number')
        setWaitUntil(new Date(Date.now() + retry * 1000).toISOString());
    } finally {
      setBusy(false);
    }
  };

  const send = () =>
    void run(async () => {
      setWaitUntil(null);
      await onSend();
    });
  const confirm = (code: string) => void run(() => onVerify(code));

  if (status === 'verified') {
    return (
      <Chip
        color="success"
        icon={<CheckCircle />}
        label={OTP_TEXT.verified}
        data-testid="otp-verified"
        sx={{ alignSelf: 'flex-start' }}
      />
    );
  }

  const sendButton = (label: string) => (
    <Button
      variant={status === 'sent' ? 'text' : 'contained'}
      onClick={send}
      disabled={busy || !phoneValid || wait > 0}
      data-testid="otp-send"
      sx={{ alignSelf: 'flex-start' }}
    >
      {wait > 0 ? OTP_TEXT.resendIn(wait) : label}
    </Button>
  );

  return (
    <Stack spacing={1} data-testid="otp-control">
      {status === 'needs_reverify' && (
        <Chip
          color="warning"
          icon={<WarningAmber />}
          label={OTP_TEXT.needsReverify}
          data-testid="otp-needs-reverify"
          sx={{ alignSelf: 'flex-start' }}
        />
      )}

      {status === 'sent' ? (
        <>
          <Typography variant="body2" color="text.secondary" data-testid="otp-sent-to">
            {OTP_TEXT.sentTo(otp?.phone ?? '')}
          </Typography>
          <CodeEntry key={otp?.expires_at ?? ''} busy={busy} onConfirm={confirm} />
          {sendButton(OTP_TEXT.resend)}
        </>
      ) : (
        sendButton(OTP_TEXT.verify)
      )}

      {error && (
        <Alert severity="error" data-testid="otp-error">
          {error}
        </Alert>
      )}
    </Stack>
  );
}
