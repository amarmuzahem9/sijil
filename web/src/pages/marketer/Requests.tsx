/**
 * «الطلبات» (docs/system.md §4.3): tabs بالانتظار / مقبولة / تم الربط / مرفوضة / مسودات.
 * «مسودات» since 005; «بالانتظار» and «مقبولة» since 008; «مرفوضة» since 010; «تم الربط» lists
 * linked requests, newest link first, since 013. The search box (specs/012 US3) finds the marketer's
 * own requests by name, phone or number and replaces the tabs while it holds 2 characters or
 * more. With no tab in the URL the page opens on «بالانتظار» once the marketer
 * has requests, else on «مسودات» (specs/008 research R11).
 */
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import InputAdornment from '@mui/material/InputAdornment';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { listRequests } from '../../lib/requests';
import { isSearchable } from '../../lib/requestSearch';
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
  const [text, setText] = useState('');
  const [search, setSearch] = useState('');
  // Ask once typing pauses, not on every key.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(isSearchable(text) ? text.trim() : ''), 300);
    return () => clearTimeout(timer);
  }, [text]);
  const searching = isSearchable(text) && search !== '';

  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        الطلبات
      </Typography>
      <TextField
        type="search"
        size="small"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="بحث بالاسم أو الهاتف أو رقم الطلب"
        slotProps={{
          htmlInput: { 'aria-label': 'بحث بالاسم أو الهاتف أو رقم الطلب' },
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlined />
              </InputAdornment>
            ),
          },
        }}
      />
      {searching ? (
        <SubmittedTab statuses={[]} q={search} />
      ) : (
        <>
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
          ) : tab === 'rejected' ? (
            <SubmittedTab statuses={['rejected']} />
          ) : (
            <SubmittedTab statuses={['linked']} />
          )}
        </>
      )}
    </Stack>
  );
}
