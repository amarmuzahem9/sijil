import GroupAddOutlined from '@mui/icons-material/GroupAddOutlined';
import PersonAddAlt1Outlined from '@mui/icons-material/PersonAddAlt1Outlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '../../lib/api';

interface DashboardData {
  linked_this_month: number;
  month_label: string;
}

export default function Dashboard() {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['marketer-dashboard'],
    queryFn: () => apiFetch<DashboardData>('/api/marketer/dashboard'),
  });

  return (
    <Stack spacing={2} sx={{ maxWidth: 560 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        الرئيسية
      </Typography>

      {/* Both actions are enabled by features 004 and 008. */}
      <Button
        variant="contained"
        size="large"
        disabled
        startIcon={<PersonAddAlt1Outlined />}
        sx={{ py: 2.5, fontSize: '1.15rem' }}
      >
        إضافة مشترك جديد
      </Button>
      <Stack spacing={0.5}>
        <Button variant="outlined" size="large" disabled startIcon={<GroupAddOutlined />} sx={{ py: 1.5 }}>
          إضافة اشتراك لمشترك موجود
        </Button>
        <Typography variant="caption" color="text.secondary" align="center">
          قريباً
        </Typography>
      </Stack>

      <Card variant="outlined">
        <CardContent>
          {isPending && <Skeleton width="60%" height={36} />}
          {isError && (
            <Alert
              severity="error"
              action={
                <Button color="inherit" size="small" onClick={() => refetch()}>
                  إعادة المحاولة
                </Button>
              }
            >
              {error.message}
            </Alert>
          )}
          {data && (
            <>
              <Typography variant="h6" data-testid="linked-counter">
                تم الربط هذا الشهر: {data.linked_this_month}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {data.month_label}
              </Typography>
            </>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
}
