/**
 * «الاستيراد» (docs/system.md §10 item 9, `reports`): the legacy Google Form subscribers (specs/014)
 * and the SAS subscribers (specs/015).
 */
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import LegacyImport from './LegacyImport';
import SasImport from './SasImport';

type ImportTab = 'legacy' | 'sas';

export default function ImportPage() {
  const [tab, setTab] = useState<ImportTab>('legacy');
  return (
    <Stack spacing={2}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        الاستيراد
      </Typography>
      <Tabs value={tab} onChange={(_, value: ImportTab) => setTab(value)} variant="scrollable">
        <Tab value="legacy" label="المشتركون القدامى" />
        <Tab value="sas" label="مشتركو SAS" />
      </Tabs>
      {tab === 'legacy' ? <LegacyImport /> : <SasImport />}
    </Stack>
  );
}
