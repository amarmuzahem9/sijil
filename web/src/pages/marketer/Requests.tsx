/**
 * «الطلبات» (docs/system.md §4.3): tabs بالانتظار / مقبولة / تم الربط / مرفوضة / مسودات.
 * Only «مسودات» has content in feature 005; the others fill in with features 008–012.
 * The page opens on «مسودات» while the marketer has drafts and no requests (research.md R11).
 */
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useSearchParams } from 'react-router-dom';

import { REQUEST_TABS, type RequestTab } from '../../lib/requestStatus';
import DraftsTab from './DraftsTab';

const isTab = (value: string | null): value is RequestTab =>
  REQUEST_TABS.some((t) => t.key === value);

export default function Requests() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  // No request exists before feature 008, so the default is «مسودات».
  const tab: RequestTab = isTab(requested) ? requested : 'drafts';

  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        الطلبات
      </Typography>
      <Tabs
        value={tab}
        onChange={(_, value: RequestTab) => setParams({ tab: value }, { replace: true })}
        variant="scrollable"
        allowScrollButtonsMobile
      >
        {REQUEST_TABS.map((t) => (
          <Tab key={t.key} value={t.key} label={t.label} />
        ))}
      </Tabs>
      {tab === 'drafts' ? (
        <DraftsTab />
      ) : (
        <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
          لا توجد طلبات بعد
        </Paper>
      )}
    </Stack>
  );
}
