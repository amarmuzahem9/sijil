/** «البطاقة الوطنية»: front, then back (docs/system.md §5.1; only the unified card is accepted). */
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import type { DraftAutosave } from '../../../lib/useDraftAutosave';
import { ImageSlot } from './ImageSlot';

export function CardSection({
  autosave,
}: {
  autosave: Pick<DraftAutosave, 'serverDraft' | 'ensureCreated' | 'applyServerDraft'>;
}) {
  const images = autosave.serverDraft?.images ?? { front: null, back: null };
  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        البطاقة الوطنية الموحدة فقط.
      </Typography>
      <ImageSlot
        side="front"
        label="وجه البطاقة"
        image={images.front}
        ensureCreated={autosave.ensureCreated}
        onUploaded={autosave.applyServerDraft}
      />
      <ImageSlot
        side="back"
        label="ظهر البطاقة"
        image={images.back}
        ensureCreated={autosave.ensureCreated}
        onUploaded={autosave.applyServerDraft}
      />
    </Stack>
  );
}
