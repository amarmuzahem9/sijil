/**
 * «من البطاقة» / «عُدِّل يدوياً» beside a card field (specs/006 FR-008, research R8).
 *
 * - From the card and unchanged → «من البطاقة» (please check it against the card).
 * - Read from the card, then changed here or on the server → «عُدِّل يدوياً».
 * - Never read (typed only) → nothing.
 */
import Chip from '@mui/material/Chip';

import { MARK_EDITED, MARK_FROM_CARD } from '../../../lib/cardReading';
import type { CardField, CardFieldMark } from '../../../lib/drafts';

export function fieldMarkText(
  mark: CardFieldMark | undefined,
  changedHere: boolean,
): string | null {
  if (!mark) return null;
  if (mark.source === 'card' && !changedHere) return MARK_FROM_CARD;
  return mark.original != null ? MARK_EDITED : null;
}

export function FieldSourceMark({
  field,
  mark,
  changedHere,
}: {
  field: CardField;
  mark: CardFieldMark | undefined;
  changedHere: boolean;
}) {
  const text = fieldMarkText(mark, changedHere);
  if (!text) return null;
  return (
    <Chip
      size="small"
      label={text}
      color={text === MARK_FROM_CARD ? 'info' : 'default'}
      variant="outlined"
      data-testid={`mark-${field}`}
      sx={{ height: 20, fontSize: 11, flexShrink: 0, '& .MuiChip-label': { px: 0.75 } }}
    />
  );
}
