/**
 * A date the marketer types or picks from the calendar (owner request after the staging test,
 * specs/006).
 *
 * The value is shown as YYYY-MM-DD, aligned right like the other fields. Read from the right it is
 * day, then month, then year: 1999-01-10 reads 10, 01, 1999. The form and the server keep the
 * same ISO text, so nothing is converted.
 *
 * - Typing: digits only, and the dashes are added (19990110 → 1999-01-10). A pasted day-first date
 *   with separators (10/01/1999) is turned around.
 * - Saving: the date is saved once it is complete and real, on the tenth character or on blur. An
 *   incomplete or impossible date shows an error and is not sent. Clearing the field saves an
 *   empty date.
 * - Calendar: the button opens the browser's own date picker, which saves at once.
 */
import CalendarMonthOutlined from '@mui/icons-material/CalendarMonthOutlined';
import Box from '@mui/material/Box';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import { useState, type ChangeEvent, type MouseEvent, type ReactNode } from 'react';

export const INVALID_DATE = 'التاريخ غير صحيح';
export const PICK_DATE = 'اختر من التقويم';
const MIN_DATE = '1900-01-01';

const toLatinDigits = (s: string) =>
  s
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0));

/**
 * What is typed, as YYYY-MM-DD: `19990110` → `1999-01-10` (Arabic-Indic digits too). A complete
 * day-first date with separators, such as a pasted `10/01/1999`, becomes `1999-01-10`.
 */
export function formatTyping(raw: string): string {
  const text = toLatinDigits(raw).trim();
  const dayFirst = /^(\d{1,2})\D+(\d{1,2})\D+(\d{4})$/.exec(text);
  if (dayFirst) {
    const [, dd, mm, yyyy] = dayFirst;
    return `${yyyy}-${mm.padStart(2, '0')}-${dd.padStart(2, '0')}`;
  }
  const digits = text.replace(/\D/g, '').slice(0, 8);
  return [digits.slice(0, 4), digits.slice(4, 6), digits.slice(6, 8)].filter(Boolean).join('-');
}

/** True when `text` is a real date written YYYY-MM-DD, from 1900 on. */
export function isRealDate(text: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  return (
    y >= 1900 &&
    date.getUTCFullYear() === y &&
    date.getUTCMonth() === mo - 1 &&
    date.getUTCDate() === d
  );
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
  // While the field is being typed in it shows what is typed; otherwise the saved value.
  const [editing, setEditing] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const shown = editing ?? value;

  const commit = (text: string) => {
    if (text === '') {
      setInvalid(false);
      if (value !== '') onSave('');
      return true;
    }
    const ok = isRealDate(text);
    setInvalid(!ok);
    if (ok && text !== value) onSave(text);
    return ok;
  };

  const calendar = (
    <InputAdornment position="end">
      <Box sx={{ position: 'relative', display: 'flex', color: 'action.active' }}>
        <CalendarMonthOutlined fontSize="small" />
        {/* The browser's own picker, laid over the icon so a tap on a phone opens it directly. */}
        <Box
          component="input"
          type="date"
          tabIndex={-1}
          aria-label={PICK_DATE}
          title={PICK_DATE}
          data-testid={`picker-${field}`}
          min={MIN_DATE}
          value={isRealDate(value) ? value : ''}
          onClick={(e: MouseEvent<HTMLInputElement>) => {
            try {
              e.currentTarget.showPicker();
            } catch {
              // Older browsers open the picker on the tap itself.
            }
          }}
          onChange={(e: ChangeEvent<HTMLInputElement>) => {
            const picked = e.target.value;
            setEditing(null);
            setInvalid(false);
            if (picked !== value) onSave(picked);
          }}
          sx={{
            position: 'absolute',
            inset: -6,
            width: 'calc(100% + 12px)',
            height: 'calc(100% + 12px)',
            opacity: 0,
            cursor: 'pointer',
            border: 0,
            p: 0,
            m: 0,
          }}
        />
      </Box>
    </InputAdornment>
  );

  return (
    <TextField
      id={`field-${field}`}
      label={label}
      value={shown}
      placeholder="يوم-شهر-سنة"
      onFocus={() => setEditing(value)}
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
        input: { ...(notch ? { label: notch } : {}), endAdornment: calendar },
        // Digits left to right, aligned right like the other fields: read from the right it is
        // day, month, year.
        htmlInput: {
          'data-testid': `field-${field}`,
          dir: 'ltr',
          inputMode: 'numeric',
          style: { textAlign: 'right' },
        },
      }}
    />
  );
}
