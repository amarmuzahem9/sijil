/**
 * Six one-digit boxes for the WhatsApp code (owner request, specs/007).
 *
 * - Left to right even on the Arabic page, like the code in the WhatsApp message.
 * - Typing moves to the next box; Backspace on an empty box goes back and clears it.
 * - Pasting or a keyboard suggestion (autocomplete="one-time-code") spreads the whole code.
 * - Arabic-Indic digits are accepted.
 * - The sixth digit submits by itself.
 * - `phase` colours the boxes: red with a short shake for a wrong code, green on success.
 *
 * The digits live only in this component's state; nothing is stored on the device.
 */
import Box from '@mui/material/Box';
import { keyframes } from '@mui/material/styles';
import {
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type FocusEvent,
  type KeyboardEvent,
} from 'react';

import { CODE_LENGTH, normalizeCodeEntry, OTP_TEXT } from '../../../lib/otp';

export type CodePhase = 'idle' | 'checking' | 'error' | 'success';

const shake = keyframes`
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px); }
  40% { transform: translateX(6px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
`;

const EMPTY: string[] = Array.from({ length: CODE_LENGTH }, () => '');

export function OtpCodeBoxes({
  phase,
  onComplete,
}: {
  phase: CodePhase;
  onComplete: (code: string) => void;
}) {
  const [digits, setDigits] = useState<string[]>(EMPTY);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const locked = phase === 'checking' || phase === 'success';

  const focus = (index: number) => {
    const target = inputs.current[Math.max(0, Math.min(CODE_LENGTH - 1, index))];
    target?.focus();
    target?.select();
  };

  const commit = (next: string[], focusIndex: number) => {
    setDigits(next);
    if (next.every(Boolean)) {
      inputs.current[focusIndex]?.blur();
      onComplete(next.join(''));
    } else {
      focus(focusIndex);
    }
  };

  /** Write `text` from `start` on (paste, keyboard suggestion, typing). */
  const spread = (text: string, start: number) => {
    const next = [...digits];
    let at = start;
    for (const d of text) {
      if (at >= CODE_LENGTH) break;
      next[at] = d;
      at += 1;
    }
    commit(next, Math.min(at, CODE_LENGTH - 1));
  };

  const onInput = (index: number, raw: string) => {
    let clean = normalizeCodeEntry(raw);
    if (!clean) {
      const next = [...digits];
      next[index] = '';
      setDigits(next);
      return;
    }
    // A digit typed after the one already in the box (the selection was lost): keep the new one.
    if (clean.length === 2 && digits[index] && clean[0] === digits[index]) clean = clean[1];
    spread(clean, clean.length === CODE_LENGTH ? 0 : index);
  };

  const onPaste = (index: number, e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const clean = normalizeCodeEntry(e.clipboardData.getData('text'));
    if (clean) spread(clean, clean.length === CODE_LENGTH ? 0 : index);
  };

  const onKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      e.preventDefault();
      const next = [...digits];
      if (next[index]) {
        next[index] = '';
        setDigits(next);
      } else if (index > 0) {
        next[index - 1] = '';
        setDigits(next);
        focus(index - 1);
      }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      focus(index - 1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      focus(index + 1);
    }
  };

  const color = phase === 'error' ? 'error.main' : phase === 'success' ? 'success.main' : 'divider';

  return (
    <Box
      role="group"
      aria-label={OTP_TEXT.codeLabel}
      dir="ltr"
      data-testid="otp-code"
      data-phase={phase}
      sx={{
        display: 'flex',
        flexDirection: 'row',
        gap: 1,
        width: '100%',
        maxWidth: 336,
        animation: phase === 'error' ? `${shake} 0.4s ease-in-out` : 'none',
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
    >
      {digits.map((digit, index) => (
        <Box
          key={index}
          component="input"
          ref={(el: HTMLInputElement | null) => {
            inputs.current[index] = el;
          }}
          value={digit}
          // Opens the keyboard on the first box after each new code (or after a wrong one).
          autoFocus={index === 0}
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="one-time-code"
          dir="ltr"
          disabled={locked}
          aria-label={`${OTP_TEXT.digitLabel} ${index + 1}`}
          aria-invalid={phase === 'error' || undefined}
          data-testid={`otp-digit-${index}`}
          onChange={(e: ChangeEvent<HTMLInputElement>) => onInput(index, e.target.value)}
          onPaste={(e: ClipboardEvent<HTMLInputElement>) => onPaste(index, e)}
          onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => onKeyDown(index, e)}
          onFocus={(e: FocusEvent<HTMLInputElement>) => e.target.select()}
          sx={{
            flex: '1 1 0',
            minWidth: 0,
            height: 56,
            p: 0,
            textAlign: 'center',
            fontSize: 26,
            fontWeight: 600,
            fontVariantNumeric: 'tabular-nums',
            fontFamily: 'inherit',
            color: phase === 'error' ? 'error.main' : 'text.primary',
            bgcolor: phase === 'success' ? 'rgba(46, 125, 50, 0.08)' : 'background.paper',
            border: 2,
            borderColor: digit && phase === 'idle' ? 'primary.main' : color,
            borderRadius: 2,
            outline: 'none',
            caretColor: 'transparent',
            transition: 'border-color 120ms, background-color 120ms, box-shadow 120ms',
            '&:focus': {
              borderColor: phase === 'idle' ? 'primary.main' : color,
              boxShadow: (t) => `0 0 0 3px ${t.palette.primary.main}33`,
            },
            '&:disabled': { opacity: 1, WebkitTextFillColor: 'currentColor' },
          }}
        />
      ))}
    </Box>
  );
}
