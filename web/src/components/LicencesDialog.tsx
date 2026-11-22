/**
 * «رخص البرمجيات المفتوحة» (specs/006 FR-022, research R12): the card reader is AGPL-3.0, so its
 * source, with every change we make, is offered to the app's users through a public copy.
 * Mounted only while open, so the client configuration is fetched only when asked for.
 */
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { useClientConfig } from '../lib/clientConfig';

export function LicencesDialog({ onClose }: { onClose: () => void }) {
  const config = useClientConfig();
  const items = config.data?.open_source ?? [];
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs" data-testid="licences-dialog">
      <DialogTitle>رخص البرمجيات المفتوحة</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 2 }}>
          قراءة البطاقة الوطنية في هذا التطبيق تستعمل برنامجاً مفتوح المصدر. يمكنك الحصول على كوده
          الكامل، مع كل التعديلات التي أجريناها عليه، من الرابط أدناه.
        </Typography>
        <Stack spacing={1.5}>
          {items.map((item) => (
            <Stack key={item.name} spacing={0.25} data-testid="licence-item">
              <Typography sx={{ fontWeight: 600 }} dir="ltr" align="right">
                {item.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                الرخصة: <bdi dir="ltr">{item.licence}</bdi>
              </Typography>
              <Link href={item.url} target="_blank" rel="noopener noreferrer" dir="ltr">
                {item.url}
              </Link>
            </Stack>
          ))}
          {config.isPending && <Typography variant="body2">جارٍ التحميل…</Typography>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>إغلاق</Button>
      </DialogActions>
    </Dialog>
  );
}
