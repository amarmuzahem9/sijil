/**
 * «النواقص» (specs/005 US5, FR-013, FR-014): every missing or invalid item, each a link to its
 * field, and the «إرسال» button, disabled in this feature (it waits for OTP and the decision
 * engine, features 007 and 008).
 */
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import {
  CODE_MESSAGES,
  FIELD_LABELS,
  type MissingField,
  type MissingItem,
} from '../../../lib/draftValidation';
import { SEND_DISABLED_NOTE } from './sections';

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
  const target =
    document.getElementById(FIELD_TARGETS[field]) ??
    document.querySelector<HTMLElement>(`[data-testid="${FIELD_TARGETS[field]}"]`);
  if (!target) return;
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const focusable = target.matches('input, textarea, [tabindex]')
    ? target
    : target.querySelector<HTMLElement>('input:not([type=file]), textarea, button, [tabindex]');
  focusable?.focus({ preventScroll: true });
}

export function MissingSummary({ missing }: { missing: MissingItem[] }) {
  return (
    <Stack spacing={1.5} data-testid="missing-summary">
      {missing.length === 0 ? (
        <Alert severity="success" icon={<CheckCircleOutlined />}>
          كل الحقول مكتملة
        </Alert>
      ) : (
        <Alert severity="warning">
          <AlertTitle>النواقص ({missing.length})</AlertTitle>
          <Stack component="ul" spacing={0.5} sx={{ m: 0, ps: 2.5 }}>
            {missing.map((item) => (
              <li key={item.field} data-testid={`missing-${item.field}`}>
                <Link component="button" type="button" onClick={() => goTo(item.field)}>
                  {FIELD_LABELS[item.field]}
                </Link>
                {item.code !== 'required' && ` — ${CODE_MESSAGES[item.code]}`}
              </li>
            ))}
          </Stack>
        </Alert>
      )}

      <Stack spacing={0.5}>
        <Button variant="contained" size="large" disabled sx={{ py: 1.5 }}>
          إرسال
        </Button>
        <Typography variant="caption" color="text.secondary" align="center">
          {SEND_DISABLED_NOTE}
        </Typography>
      </Stack>
    </Stack>
  );
}
