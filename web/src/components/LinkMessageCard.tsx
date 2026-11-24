/**
 * «رسالة الربط» (system.md v1.17 §8.4, specs/012 FR-006, FR-007): the server's text, selectable,
 * with «نسخ رسالة الربط» and «مشاركة بالواتساب». A failed copy leaves the text on screen to copy
 * by hand.
 */
import ContentCopyOutlined from '@mui/icons-material/ContentCopyOutlined';
import WhatsApp from '@mui/icons-material/WhatsApp';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import { copyText, whatsappUrl } from '../lib/linkMessage';

export default function LinkMessageCard({ text }: { text: string }) {
  const [status, setStatus] = useState<'copied' | 'failed' | null>(null);

  const copy = async () => {
    setStatus((await copyText(text)) ? 'copied' : 'failed');
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }} data-testid="link-message">
      <Stack spacing={1.5}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          رسالة الربط
        </Typography>
        <Typography
          component="pre"
          data-testid="link-message-text"
          sx={{
            m: 0,
            p: 1.5,
            bgcolor: 'action.hover',
            borderRadius: 1,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'inherit',
            userSelect: 'text',
          }}
        >
          {text}
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
          <Button
            variant="contained"
            fullWidth
            startIcon={<ContentCopyOutlined />}
            onClick={() => void copy()}
          >
            نسخ رسالة الربط
          </Button>
          <Button
            variant="outlined"
            color="success"
            fullWidth
            startIcon={<WhatsApp />}
            component="a"
            href={whatsappUrl(text)}
            target="_blank"
            rel="noopener noreferrer"
          >
            مشاركة بالواتساب
          </Button>
        </Stack>
        {status && (
          <Typography
            variant="caption"
            data-testid="link-message-status"
            color={status === 'copied' ? 'success.main' : 'error.main'}
            sx={{ textAlign: 'center' }}
          >
            {status === 'copied' ? 'تم النسخ' : 'تعذّر النسخ، انسخ النص يدوياً'}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}
