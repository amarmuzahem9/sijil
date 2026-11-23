/**
 * «الاتصال بالإدارة» (specs/009 US2, research R8). A real link (`<a target="_blank">`) so phone
 * browsers open WhatsApp without a pop-up block; `onOpen` reports the click and is not awaited.
 * Without a number in the settings the button is disabled with its reason.
 */
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { adminWhatsAppLink, CONTACT_ADMIN_TEXT } from '../../../lib/contactAdmin';

export function ContactAdminButton({
  number,
  marketerName,
  onOpen,
}: {
  number: string | null | undefined;
  marketerName: string;
  onOpen: () => void;
}) {
  if (!number)
    return (
      <Stack spacing={0.5}>
        <Button variant="outlined" size="small" disabled>
          {CONTACT_ADMIN_TEXT.action}
        </Button>
        <Typography variant="caption" color="text.secondary">
          {CONTACT_ADMIN_TEXT.unset}
        </Typography>
      </Stack>
    );
  return (
    <Button
      variant="outlined"
      size="small"
      color="inherit"
      component="a"
      href={adminWhatsAppLink(number, marketerName)}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onOpen}
      data-testid="contact-admin"
    >
      {CONTACT_ADMIN_TEXT.action}
    </Button>
  );
}
