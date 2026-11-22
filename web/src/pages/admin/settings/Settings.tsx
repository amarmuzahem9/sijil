import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import { useSearchParams } from 'react-router-dom';

import AreasTab from './AreasTab';
import GeneralTab from './GeneralTab';
import PlansTab from './PlansTab';
import TiersTab from './TiersTab';
import TowersTab from './TowersTab';

const TABS = [
  { key: 'areas', label: 'المناطق' },
  { key: 'towers', label: 'الأبراج' },
  { key: 'plans', label: 'الفئات' },
  { key: 'tiers', label: 'الشرائح' },
  { key: 'general', label: 'عام' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

/** «الإعدادات» (specs/004): tabs, with the open tab kept in the URL (?tab=towers). */
export default function Settings() {
  const [params, setParams] = useSearchParams();
  const requested = params.get('tab');
  const tab: TabKey = TABS.some((t) => t.key === requested) ? (requested as TabKey) : 'areas';

  return (
    <>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
        الإعدادات
      </Typography>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, value: TabKey) => setParams({ tab: value }, { replace: true })}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          aria-label="أقسام الإعدادات"
        >
          {TABS.map((t) => (
            <Tab key={t.key} value={t.key} label={t.label} />
          ))}
        </Tabs>
      </Box>
      {tab === 'areas' && <AreasTab />}
      {tab === 'towers' && <TowersTab />}
      {tab === 'plans' && <PlansTab />}
      {tab === 'tiers' && <TiersTab />}
      {tab === 'general' && <GeneralTab />}
    </>
  );
}
