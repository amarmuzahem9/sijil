/**
 * «الطلبات» (docs/system.md §4.3): tabs بالانتظار / مقبولة / تم الربط / مرفوضة / مسودات.
 * «مسودات» since 005; «بالانتظار» and «مقبولة» since 008; «تم الربط» (012) and «مرفوضة» (010)
 * stay empty until then. With no tab in the URL the page opens on «بالانتظار» once the marketer
 * has requests, else on «مسودات» (specs/008 research R11).
 */
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';

import { listRequests } from '../../lib/requests';
import { REQUEST_TABS, type RequestTab } from '../../lib/requestStatus';
import DraftsTab from './DraftsTab';
import { SubmittedTab } from './SubmittedTab';

const isTab = (value: string | null): value is RequestTab =>
  REQUEST_TABS.some((t) => t.key === value);

export default function Requests() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const any = useQuery({ queryKey: ['requests', 'list'], queryFn: () => listRequests() });
  const hasRequests = (any.data?.items.length ?? 0) > 0;
  const tab: RequestTab = isTab(requested) ? requested : hasRequests ? 'pending' : 'drafts';

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
      ) : tab === 'pending' ? (
        <SubmittedTab statuses={['pending_review']} />
      ) : tab === 'approved' ? (
        <SubmittedTab statuses={['approved']} />
      ) : (
        <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
          لا توجد طلبات بعد
        </Paper>
      )}
    </Stack>
  );
}
