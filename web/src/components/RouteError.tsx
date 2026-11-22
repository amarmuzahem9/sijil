/**
 * Route error element: any error thrown while rendering a page shows an Arabic message with a way
 * out, instead of React Router's default developer screen. No error details are shown to the user
 * (they may hold form data); the error goes to the console for debugging.
 */
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useEffect } from 'react';
import { useRouteError } from 'react-router-dom';

export const ROUTE_ERROR_TITLE = 'حدث خطأ غير متوقع في هذه الصفحة';
export const ROUTE_ERROR_HINT =
  'ما كتبته وحُفظ تلقائياً باقٍ على الخادم. أعد تحميل الصفحة، وإذا تكرر الخطأ أبلغ الأدمن.';

export default function RouteError() {
  const error = useRouteError();
  useEffect(() => {
    console.error('route error', error);
  }, [error]);

  return (
    <Container maxWidth="sm" sx={{ py: 6 }}>
      <Stack spacing={2} role="alert" data-testid="route-error">
        <Typography variant="h6" component="h1">
          {ROUTE_ERROR_TITLE}
        </Typography>
        <Alert severity="error">{ROUTE_ERROR_HINT}</Alert>
        <Stack direction="row" spacing={1}>
          <Button variant="contained" onClick={() => window.location.reload()}>
            إعادة تحميل الصفحة
          </Button>
          <Button variant="outlined" onClick={() => window.location.assign('/')}>
            الرجوع إلى الرئيسية
          </Button>
        </Stack>
      </Stack>
    </Container>
  );
}
