import FormControlLabel from '@mui/material/FormControlLabel';
import FormGroup from '@mui/material/FormGroup';
import FormLabel from '@mui/material/FormLabel';
import Switch from '@mui/material/Switch';

import { PERMISSION_LABELS, PERMISSIONS } from '../lib/labels';
import type { Permission } from '../lib/labels';

/** The §3.3 on/off switches with their Arabic labels, «حذف مشترك» last (specs/011). */
export function PermissionSwitches({
  value,
  onChange,
  disabled = false,
}: {
  value: Permission[];
  onChange: (next: Permission[]) => void;
  disabled?: boolean;
}) {
  const toggle = (p: Permission, on: boolean) =>
    onChange(PERMISSIONS.filter((k) => (k === p ? on : value.includes(k))));
  return (
    <FormGroup>
      <FormLabel component="legend" sx={{ mb: 1 }}>
        الصلاحيات
      </FormLabel>
      {PERMISSIONS.map((p) => (
        <FormControlLabel
          key={p}
          control={
            <Switch
              checked={value.includes(p)}
              onChange={(e) => toggle(p, e.target.checked)}
              disabled={disabled}
              slotProps={{ input: { 'aria-label': PERMISSION_LABELS[p] } }}
            />
          }
          label={PERMISSION_LABELS[p]}
        />
      ))}
    </FormGroup>
  );
}
