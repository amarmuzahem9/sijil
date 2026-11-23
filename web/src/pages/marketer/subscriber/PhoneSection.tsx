/**
 * «هاتف المشترك» (docs/system.md §5.4): the subscriber's own phone, normalized per §8.1, and its
 * WhatsApp OTP verification (feature 007, OtpControl).
 *
 * A used phone (§6.1 v1.10 row 1, specs/009 US2): when the phone's owner is the return target,
 * «طلب العودة للخدمة» and «الاتصال بالإدارة»; otherwise (another person's phone) the message and
 * «الاتصال بالإدارة» only. Nothing about the owner is shown.
 */
import Stack from '@mui/material/Stack';
import { useCallback } from 'react';

import { useAuth } from '../../../auth/AuthProvider';

import { ApiError } from '../../../lib/api';
import { useClientConfig } from '../../../lib/clientConfig';
import { reportContactAdmin } from '../../../lib/contactAdmin';
import { getDraft, sendOtp, verifyOtp } from '../../../lib/drafts';
import { normalizePhone } from '../../../lib/phone';
import type { DraftAutosave, TextField } from '../../../lib/useDraftAutosave';
import { DraftTextField } from './DraftTextField';
import { ContactAdminButton } from './ContactAdminButton';
import { PhoneUsedNotice } from './FamilyMatchNotice';
import { OtpControl } from './OtpControl';
import { ReturnNotice } from './ReturnNotice';

// Errors after which the server's otp state changed (attempt used, code cancelled or gone).
const REFRESH_AFTER = new Set(['otp_wrong', 'otp_cancelled', 'otp_expired', 'otp_no_active']);

export function PhoneSection({
  autosave,
  onCommit,
  error,
}: {
  autosave: Pick<
    DraftAutosave,
    'values' | 'setText' | 'serverDraft' | 'saveAll' | 'applyServerDraft' | 'draftId' | 'saveNow'
  >;
  onCommit: (field: TextField) => void;
  error?: string | null;
}) {
  const { values, setText, serverDraft, saveAll, applyServerDraft, draftId, saveNow } = autosave;
  const config = useClientConfig();
  const { user } = useAuth();
  const checks = serverDraft?.checks;
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

  const contact = (
    <ContactAdminButton
      number={config.data?.admin_whatsapp}
      marketerName={user?.name ?? ''}
      onOpen={() => {
        // Audit only; WhatsApp opens from the link itself (research R8).
        if (draftId) void reportContactAdmin(draftId).catch(() => {});
      }}
    />
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
      <ReturnNotice
        basis="phone"
        checks={checks}
        onChoose={() => saveNow({ return_chosen: true })}
        onWithdraw={() => saveNow({ return_chosen: false })}
      >
        {contact}
      </ReturnNotice>
      {checks?.return_basis !== 'phone' && (
        <PhoneUsedNotice checks={checks}>{contact}</PhoneUsedNotice>
      )}
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
