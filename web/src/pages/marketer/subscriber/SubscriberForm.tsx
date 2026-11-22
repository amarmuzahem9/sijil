/**
 * «إضافة مشترك جديد» — one page with the sections in the order of docs/system.md §5 (FR-003).
 *
 * Shell (specs/005 T016): section frames, the sticky save-badge slot and the bottom slot for
 * «النواقص» and the disabled «إرسال». The sections, autosave and loading are filled in by the
 * user-story tasks.
 */
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';
import { useParams } from 'react-router-dom';

import { SECTIONS, SEND_DISABLED_NOTE, type SectionId } from './sections';

function FormSection({
  id,
  title,
  children,
}: {
  id: SectionId;
  title: string;
  children?: ReactNode;
}) {
  return (
    <Paper
      component="section"
      variant="outlined"
      id={id}
      aria-labelledby={`${id}-title`}
      sx={{ p: 2 }}
    >
      <Typography id={`${id}-title`} component="h2" variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
        {title}
      </Typography>
      {children ?? (
        <Typography variant="body2" color="text.secondary">
          قريباً
        </Typography>
      )}
    </Paper>
  );
}

export default function SubscriberForm() {
  const { draftId } = useParams<{ draftId?: string }>();

  return (
    <Stack
      spacing={2}
      sx={{ maxWidth: 640 }}
      data-testid="subscriber-form"
      data-draft-id={draftId ?? ''}
    >
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 2,
          bgcolor: 'background.default',
          py: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
        }}
      >
        <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
          إضافة مشترك جديد
        </Typography>
        {/* Save badge slot (US1, SaveBadge). */}
        <Box data-testid="save-badge-slot" />
      </Box>

      {SECTIONS.map((section) => (
        <FormSection key={section.id} id={section.id} title={section.title} />
      ))}

      {/* «النواقص» slot (US5, MissingSummary). */}
      <Box data-testid="missing-summary-slot" />

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
