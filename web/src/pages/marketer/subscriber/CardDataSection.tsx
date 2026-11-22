/**
 * «بيانات البطاقة» (docs/system.md §5.1 v1.5): the nine name fields of the ministry form, then
 * the national ID and the family number. Typed by hand in this feature (FR-004); card reading
 * comes in 006, and the fourth name is never on the card.
 *
 * Phone layout: first + second and third + fourth side by side, the surname full width, and the
 * mother's names grouped under «اسم الأم».
 */
import Box from '@mui/material/Box';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

import { NO_SURNAME, NO_SURNAME_HINT } from '../../../lib/cardReading';
import type { CardField } from '../../../lib/drafts';
import { NAME_LABELS, OPTIONAL_NAME_FIELDS, type NameField } from '../../../lib/nameFields';
import type { DraftAutosave, TextField } from '../../../lib/useDraftAutosave';
import { DraftTextField } from './DraftTextField';
import { FieldSourceMark } from './FieldSourceMark';

export const FOURTH_NAME_HINT = 'غير موجود على البطاقة، اسأل المشترك';

type CardDataField = NameField | 'national_id' | 'family_number';

// The name fields a card reading fills (the fourth name and the mother's third name and
// surname are never on the card).
const CARD_NAME_FIELDS = [
  'first_name',
  'father_name',
  'grandfather_name',
  'surname',
  'mother_first_name',
  'mother_second_name',
] as const;

function Pair({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 1 }}>{children}</Box>
  );
}

export function CardDataSection({
  autosave,
  errors = {},
  onCommit,
}: {
  autosave: Pick<DraftAutosave, 'values' | 'setText' | 'commitField' | 'serverDraft' | 'saveNow'>;
  errors?: Partial<Record<CardDataField, string>>;
  /** Called on blur instead of `commitField` (the form marks the field as touched). */
  onCommit?: (field: TextField) => void;
}) {
  const { values, setText, serverDraft, saveNow } = autosave;
  const commitField = onCommit ?? autosave.commitField;

  // «من البطاقة» / «عُدِّل يدوياً» (specs/006 FR-008): a value changed here but not yet saved
  // already counts as edited.
  const mark = (field: CardField) => (
    <FieldSourceMark
      field={field}
      mark={serverDraft?.card_fields?.[field]}
      changedHere={values[field] !== (serverDraft?.[field] ?? '')}
    />
  );

  const name = (field: NameField, helperText?: string) => (
    <DraftTextField
      field={field}
      label={
        OPTIONAL_NAME_FIELDS.includes(field)
          ? `${NAME_LABELS[field]} (اختياري)`
          : `${NAME_LABELS[field]} *`
      }
      value={values[field]}
      onText={setText}
      onCommit={commitField}
      error={errors[field]}
      helperText={helperText}
      autoComplete="off"
      adornment={
        (CARD_NAME_FIELDS as readonly string[]).includes(field)
          ? mark(field as CardField)
          : undefined
      }
      disabled={field === 'surname' && values.no_surname}
    />
  );

  const surnameEmptyOnCard =
    serverDraft?.card_reading?.front?.surname_empty === true && !values.surname.trim();

  return (
    <Stack spacing={1}>
      <Pair>
        {name('first_name')}
        {name('father_name')}
      </Pair>
      <Pair>
        {name('grandfather_name')}
        {name('great_grandfather_name', FOURTH_NAME_HINT)}
      </Pair>
      {name('surname')}
      <Box sx={{ mt: -1 }}>
        {surnameEmptyOnCard && !values.no_surname && (
          <Typography variant="caption" color="warning.main" data-testid="no-surname-hint">
            {NO_SURNAME_HINT}
          </Typography>
        )}
        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={values.no_surname}
              onChange={(e) =>
                saveNow(
                  e.target.checked ? { no_surname: true, surname: '' } : { no_surname: false },
                )
              }
              slotProps={{ input: { 'data-testid': 'field-no_surname' } as object }}
            />
          }
          label={NO_SURNAME}
        />
      </Box>

      <Box
        component="fieldset"
        sx={{ border: 1, borderColor: 'divider', borderRadius: 1, px: 1.5, pt: 0.5, pb: 0, m: 0 }}
      >
        <Typography component="legend" variant="subtitle2" sx={{ px: 0.5, fontWeight: 600 }}>
          اسم الأم
        </Typography>
        <Pair>
          {name('mother_first_name')}
          {name('mother_second_name')}
        </Pair>
        <Pair>
          {name('mother_third_name')}
          {name('mother_surname')}
        </Pair>
      </Box>

      <DraftTextField
        field="national_id"
        label="الرقم الوطني *"
        value={values.national_id}
        onText={setText}
        onCommit={commitField}
        error={errors.national_id}
        helperText="12 رقماً"
        ltr
        inputMode="numeric"
        adornment={mark('national_id')}
      />
      <DraftTextField
        field="family_number"
        label="الرقم العائلي *"
        value={values.family_number}
        onText={setText}
        onCommit={commitField}
        error={errors.family_number}
        helperText="كما هو مكتوب على البطاقة"
        ltr
        adornment={mark('family_number')}
      />
    </Stack>
  );
}
