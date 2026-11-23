/**
 * «هاتف المشترك» (docs/system.md §5.4): the subscriber's own phone, normalized per §8.1, and its
 * WhatsApp OTP verification (feature 007, OtpControl).
 */
import Stack from '@mui/material/Stack';
import { useCallback } from 'react';

import { ApiError } from '../../../lib/api';
import { useClientConfig } from '../../../lib/clientConfig';
import { getDraft, sendOtp, verifyOtp } from '../../../lib/drafts';
import { normalizePhone } from '../../../lib/phone';
import type { DraftAutosave, TextField } from '../../../lib/useDraftAutosave';
import { DraftTextField } from './DraftTextField';
import { OtpControl } from './OtpControl';

// Errors after which the server's otp state changed (attempt used, code cancelled or gone).
const REFRESH_AFTER = new Set(['otp_wrong', 'otp_cancelled', 'otp_expired', 'otp_no_active']);

export function PhoneSection({
  autosave,
  onCommit,
  error,
}: {
  autosave: Pick<
    DraftAutosave,
    'values' | 'setText' | 'serverDraft' | 'saveAll' | 'applyServerDraft' | 'draftId'
  >;
  onCommit: (field: TextField) => void;
  error?: string | null;
}) {
  const { values, setText, serverDraft, saveAll, applyServerDraft, draftId } = autosave;
  const config = useClientConfig();
  const normalized = normalizePhone(values.phone_input);
  const hint =
    normalized && normalized !== values.phone_input.trim() ? `سيُحفظ كـ ${normalized}` : ' ';

  const refreshAfter = useCallback(
    async (err: unknown): Promise<never> => {
      if (draftId && err instanceof ApiError && REFRESH_AFTER.has(err.code)) {
        try {
          applyServerDraft(await getDraft(draftId));
        } catch {
          // The original error is the one to show.
        }
      }
      throw err;
    },
    [applyServerDraft, draftId],
  );

  const onSend = useCallback(async () => {
    // The server sends to the stored phone: save what was typed first.
    const id = await saveAll();
    applyServerDraft(await sendOtp(id));
  }, [applyServerDraft, saveAll]);

  const onVerify = useCallback(
    async (code: string) => {
      if (!draftId) return () => {};
      try {
        const verified = await verifyOtp(draftId, code);
        // Applied once the green boxes have shown (OtpControl).
        return () => applyServerDraft(verified);
      } catch (err) {
        return refreshAfter(err);
      }
    },
    [applyServerDraft, draftId, refreshAfter],
  );

  return (
    <Stack spacing={1}>
      <DraftTextField
        field="phone_input"
        label="هاتف المشترك"
        value={values.phone_input}
        onText={setText}
        onCommit={onCommit}
        error={error}
        helperText={hint}
        ltr
        inputMode="tel"
        autoComplete="off"
      />
      <OtpControl
        otp={serverDraft?.otp}
        phoneValid={normalized !== null}
        enabled={config.data?.otp_enabled !== false}
        onSend={onSend}
        onVerify={onVerify}
      />
    </Stack>
  );
}
