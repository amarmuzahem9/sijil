/**
 * «من البطاقة» / «عُدِّل يدوياً» beside a card field (specs/006 FR-008, research R8).
 *
 * - From the card and unchanged → «من البطاقة» (please check it against the card).
 * - Read from the card, then changed here or on the server → «عُدِّل يدوياً».
 * - Never read (typed only) → nothing.
 */
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import type { ReactNode } from 'react';

import { MARK_EDITED, MARK_FROM_CARD } from '../../../lib/cardReading';
import type { CardField, CardFieldMark } from '../../../lib/drafts';

export function fieldMarkText(
  mark: CardFieldMark | undefined,
  changedHere: boolean,
  empty = false,
): string | null {
  // An empty field never carries a mark (owner request after the staging test): a reading that
  // was not accepted leaves the field empty for the marketer, with no «من البطاقة».
  if (!mark || empty) return null;
  if (mark.source === 'card' && !changedHere) return MARK_FROM_CARD;
  return mark.original != null ? MARK_EDITED : null;
}

export function FieldSourceMark({
  field,
  mark,
  changedHere,
  empty = false,
}: {
  field: CardField;
  mark: CardFieldMark | undefined;
  changedHere: boolean;
  empty?: boolean;
}) {
  const text = fieldMarkText(mark, changedHere, empty);
  if (!text) return null;
  return (
    <Chip
      size="small"
      label={text}
      color={text === MARK_FROM_CARD ? 'info' : 'default'}
      variant="outlined"
      data-testid={`mark-${field}`}
      sx={{
        height: 18,
        fontSize: 10,
        flexShrink: 0,
        bgcolor: 'background.paper',
        '& .MuiChip-label': { px: 0.75 },
      }}
    />
  );
}

// Room for the mark in the outlined frame's gap. The gap is sized from a plain-text copy of the
// label (no second copy of the mark in the page); the mark's own background covers the line.
const MARK_ROOM = String.fromCharCode(0xa0).repeat(16);

/** The text MUI sizes the frame's gap from when a label carries a mark. */
export const notchText = (text: string, hasMark: boolean): string =>
  hasMark ? text + MARK_ROOM : text;

/**
 * A field label with its mark beside it: the mark sits on the field's frame with the label, never
 * inside the box over the value (owner request after the staging test).
 */
export function MarkedLabel({ text, mark }: { text: string; mark: ReactNode }) {
  return (
    <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
      {text}
      {mark}
    </Box>
  );
}
