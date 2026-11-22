/** Save status of the draft (specs/005 research.md R11, US1). */
import CloudDoneOutlined from '@mui/icons-material/CloudDoneOutlined';
import CloudOffOutlined from '@mui/icons-material/CloudOffOutlined';
import ErrorOutlineOutlined from '@mui/icons-material/ErrorOutlineOutlined';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';

import type { SaveState } from '../../../lib/autosaveQueue';

export function SaveBadge({ state, onRetry }: { state: SaveState; onRetry: () => void }) {
  switch (state) {
    case 'idle':
      return null;
    case 'saving':
      return (
        <Chip
          size="small"
          data-testid="save-badge"
          icon={<CircularProgress size={14} />}
          label="جارٍ الحفظ…"
        />
      );
    case 'saved':
      return (
        <Chip
          size="small"
          color="success"
          variant="outlined"
          data-testid="save-badge"
          icon={<CloudDoneOutlined />}
          label="محفوظ"
        />
      );
    case 'offline':
      return (
        <Chip
          size="small"
          color="warning"
          variant="outlined"
          data-testid="save-badge"
          icon={<CloudOffOutlined />}
          label="غير متصل — سيُعاد الحفظ تلقائياً"
        />
      );
    case 'failed':
      return (
        <Button
          size="small"
          color="error"
          variant="outlined"
          data-testid="save-badge"
          startIcon={<ErrorOutlineOutlined />}
          onClick={onRetry}
        >
          لم يُحفظ — إعادة المحاولة
        </Button>
      );
    default:
      // conflict / deleted / session_ended are shown by their own banner or dialog.
      return (
        <Chip
          size="small"
          color="warning"
          data-testid="save-badge"
          icon={<CloudOffOutlined />}
          label="الحفظ متوقف"
        />
      );
  }
}
