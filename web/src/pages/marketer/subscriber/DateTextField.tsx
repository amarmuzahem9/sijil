/**
 * A date typed and shown as day-month-year, e.g. 10-01-1999 (owner request, specs/006). The form
 * keeps ISO dates (YYYY-MM-DD) and the server stores dates; this field converts both ways.
 *
 * Digits only: the dashes are added while typing. The date is saved once it is complete and real
 * (on the tenth character or on blur); an incomplete or impossible date shows an error and is not
 * sent. Clearing the field saves an empty date.
 */
import TextField from '@mui/material/TextField';
import { useState, type ReactNode } from 'react';

export const INVALID_DATE = 'التاريخ غير صحيح (يوم-شهر-سنة)';

/** `1999-01-10` → `10-01-1999`; '' stays ''. */
export function isoToDisplay(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : '';
}

/** Keep the digits (Arabic-Indic too) and insert the dashes: `10011999` → `10-01-1999`. */
export function formatTyping(raw: string): string {
  const digits = raw
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/\D/g, '')
    .slice(0, 8);
  const parts = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 8)].filter(Boolean);
  return parts.join('-');
}

/** `10-01-1999` → `1999-01-10`, or null when it is not a real date. */
export function displayToIso(text: string): string | null {
  const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(text);
  if (!m) return null;
  const [, dd, mm, yyyy] = m;
  const date = new Date(Date.UTC(Number(yyyy), Number(mm) - 1, Number(dd)));
  const real =
    date.getUTCFullYear() === Number(yyyy) &&
    date.getUTCMonth() === Number(mm) - 1 &&
    date.getUTCDate() === Number(dd);
  return real && Number(yyyy) >= 1900 ? `${yyyy}-${mm}-${dd}` : null;
}

export function DateTextField({
  field,
  label,
  notch,
  value,
  onSave,
  error,
}: {
  field: string;
  label: ReactNode;
  /** Plain text the frame's gap is sized from (the label may carry a mark). */
  notch?: string;
  /** ISO date or ''. */
  value: string;
  onSave: (iso: string) => void;
  error?: string | null;
}) {
  // While the field is being edited it shows what is typed; otherwise the saved value.
  const [editing, setEditing] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const shown = editing ?? isoToDisplay(value);

  const commit = (text: string) => {
    if (text === '') {
      setInvalid(false);
      if (value !== '') onSave('');
      return true;
    }
    const iso = displayToIso(text);
    setInvalid(iso === null);
    if (iso !== null && iso !== value) onSave(iso);
    return iso !== null;
  };

  return (
    <TextField
      id={`field-${field}`}
      label={label}
      value={shown}
      placeholder="يوم-شهر-سنة"
      onFocus={() => setEditing(isoToDisplay(value))}
      onChange={(e) => {
        const text = formatTyping(e.target.value);
        setEditing(text);
        if (text.length === 10) commit(text);
        else setInvalid(false);
      }}
      onBlur={() => {
        if (editing !== null && commit(editing)) setEditing(null);
      }}
      error={invalid || Boolean(error)}
      helperText={invalid ? INVALID_DATE : (error ?? ' ')}
      fullWidth
      autoComplete="off"
      slotProps={{
        inputLabel: { shrink: true },
        input: notch ? { label: notch } : undefined,
        htmlInput: { 'data-testid': `field-${field}`, dir: 'ltr', inputMode: 'numeric' },
      }}
    />
  );
}
