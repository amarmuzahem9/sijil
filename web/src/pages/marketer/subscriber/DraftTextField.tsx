/** A text field wired to the draft autosave: debounced on typing, saved on blur. */
import TextField from '@mui/material/TextField';
import type { HTMLAttributes, ReactNode } from 'react';

import type { TextField as DraftField } from '../../../lib/useDraftAutosave';
import { MarkedLabel, notchText } from './FieldSourceMark';

export function DraftTextField({
  field,
  label,
  value,
  onText,
  onCommit,
  error,
  helperText,
  ltr = false,
  inputMode,
  multiline = false,
  autoComplete = 'off',
  labelMark,
  disabled = false,
}: {
  field: DraftField;
  label: string;
  value: string;
  onText: (field: DraftField, value: string) => void;
  onCommit: (field: DraftField) => void;
  error?: string | null;
  helperText?: string | null;
  ltr?: boolean;
  inputMode?: HTMLAttributes<HTMLInputElement>['inputMode'];
  multiline?: boolean;
  autoComplete?: string;
  /** Shown with the label on the field's frame, e.g. the «من البطاقة» mark (specs/006). */
  labelMark?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <TextField
      id={`field-${field}`}
      name={field}
      label={labelMark ? <MarkedLabel text={label} mark={labelMark} /> : label}
      value={value}
      onChange={(e) => onText(field, e.target.value)}
      onBlur={() => onCommit(field)}
      error={Boolean(error)}
      helperText={error ?? helperText ?? ' '}
      fullWidth
      disabled={disabled}
      multiline={multiline}
      minRows={multiline ? 2 : undefined}
      autoComplete={autoComplete}
      slotProps={{
        // The frame's gap gets plain text only, so the mark is not copied into it.
        input: labelMark ? { label: notchText(label, true) } : undefined,
        htmlInput: {
          dir: ltr ? 'ltr' : undefined,
          inputMode,
          'data-testid': `field-${field}`,
        },
      }}
    />
  );
}
