/**
 * «النواقص» (specs/005 US5, FR-013, FR-014): every missing or invalid item, each a link to its
 * field, and «إرسال» (specs/008 FR-011): enabled only when nothing is missing and the phone is
 * verified (feature 007, listed as «التحقق من الهاتف» until then). A refusal from the server
 * shows its Arabic message under the button. The server decides; this only gates the press.
 */
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import {
  CODE_MESSAGES,
  FIELD_LABELS,
  type MissingField,
  type MissingItem,
} from '../../../lib/draftValidation';

/** Items the server adds from the duplicate check (specs/008 research R5); not in the mirror. */
export const SERVER_ITEMS = {
  national_id_exists: {
    target: 'field-national_id',
    label: 'المشترك لديه اشتراك سابق — اختر «طلب العودة للخدمة»',
  },
  return_pending: { target: 'field-national_id', label: 'يوجد طلب سابق بالانتظار لهذا المشترك' },
  family_exists_unconfirmed: {
    target: 'field-family_number',
    label: 'لهذه العائلة اشتراك سابق — اختر «طلب اشتراك إضافي»',
  },
  phone_used: { target: 'field-phone_input', label: 'المشترك موجود سابقاً، هل يود العودة للخدمة؟' },
} as const;
type ServerItem = keyof typeof SERVER_ITEMS;
const serverItem = (field: string) =>
  field in SERVER_ITEMS ? SERVER_ITEMS[field as ServerItem] : null;

/** Where each item's link goes: the input itself, or the block for images and the pin. */
const FIELD_TARGETS: Record<MissingField, string> = {
  image_front: 'image-slot-front',
  image_back: 'image-slot-back',
  first_name: 'field-first_name',
  father_name: 'field-father_name',
  grandfather_name: 'field-grandfather_name',
  great_grandfather_name: 'field-great_grandfather_name',
  surname: 'field-surname',
  mother_first_name: 'field-mother_first_name',
  mother_second_name: 'field-mother_second_name',
  national_id: 'field-national_id',
  national_id_unconfirmed: 'field-national_id',
  family_number: 'field-family_number',
  birth_date: 'field-birth_date',
  birth_place: 'field-birth_place',
  issue_date: 'field-issue_date',
  expiry_date: 'field-expiry_date',
  card_expired: 'field-expiry_date',
  issuing_authority: 'field-issuing_authority',
  location: 'section-location',
  address: 'field-address',
  landmark: 'field-landmark',
  area_id: 'field-area_id',
  tower_id: 'field-tower_id',
  plan_id: 'field-plan_id',
  phone: 'field-phone_input',
};

function goTo(field: MissingField) {
  const id = serverItem(field)?.target ?? FIELD_TARGETS[field];
  const target =
    document.getElementById(id) ?? document.querySelector<HTMLElement>(`[data-testid="${id}"]`);
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const focusable = target.matches('input, textarea, [tabindex]')
    ? target
    : target.querySelector<HTMLElement>('input:not([type=file]), textarea, button, [tabindex]');
  focusable?.focus({ preventScroll: true });
}

const PHONE_VERIFICATION_LABEL = 'التحقق من الهاتف';

export const SEND_TEXT = { send: 'إرسال', sending: 'جارٍ الإرسال…' } as const;

export function MissingSummary({
  missing,
  phoneVerified,
  onSubmit,
}: {
  missing: MissingItem[];
  phoneVerified: boolean;
  /** Saves pending changes, submits, and moves to the result; rejects with an ApiError. */
  onSubmit?: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const count = missing.length + (phoneVerified ? 0 : 1);
  const canSend = count === 0 && !!onSubmit && !busy;

  const send = async () => {
    if (!canSend || !onSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'حدث خطأ غير متوقع، حاول مرة أخرى');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Stack spacing={1.5} data-testid="missing-summary">
      {count === 0 ? (
        <Alert severity="success" icon={<CheckCircleOutlined />}>
          كل الحقول مكتملة
        </Alert>
      ) : (
        <Alert severity="warning">
          <AlertTitle>النواقص ({count})</AlertTitle>
          <Stack component="ul" spacing={0.5} sx={{ m: 0, ps: 2.5 }}>
            {missing.map((item) => (
              <li key={item.field} data-testid={`missing-${item.field}`}>
                <Link component="button" type="button" onClick={() => goTo(item.field)}>
                  {serverItem(item.field)?.label ?? FIELD_LABELS[item.field]}
                </Link>
                {item.code !== 'required' &&
                  !serverItem(item.field) &&
                  ` — ${CODE_MESSAGES[item.code]}`}
              </li>
            ))}
            {!phoneVerified && (
              <li data-testid="missing-phone_verification">
                <Link component="button" type="button" onClick={() => goTo('phone')}>
                  {PHONE_VERIFICATION_LABEL}
                </Link>
              </li>
            )}
          </Stack>
        </Alert>
      )}

      <Stack spacing={1}>
        <Button
          variant="contained"
          size="large"
          disabled={!canSend}
          onClick={() => void send()}
          sx={{ py: 1.5 }}
          data-testid="submit-button"
        >
          {busy ? SEND_TEXT.sending : SEND_TEXT.send}
        </Button>
        {error && (
          <Alert severity="error" data-testid="submit-error">
            {error}
          </Alert>
        )}
        {count > 0 && (
          <Typography variant="caption" color="text.secondary" align="center">
            أكمل النواقص ليتفعّل الإرسال
          </Typography>
        )}
      </Stack>
    </Stack>
  );
}
