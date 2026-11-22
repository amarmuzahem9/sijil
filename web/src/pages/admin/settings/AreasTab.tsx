import AddOutlined from '@mui/icons-material/AddOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { FormDialog } from '../../../components/FormDialog';
import { ItemList } from '../../../components/ItemList';
import { areasApi } from '../../../lib/settings';
import type { Area } from '../../../lib/settings';
import { useItemActions } from './useItemActions';

const NAME_ERROR = 'الاسم يجب أن يكون بين 1 و100 حرف';

function AreaDialog({
  area,
  onSaved,
  onClose,
}: {
  area: Area | null;
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const [name, setName] = useState(area?.name ?? '');
  const [touched, setTouched] = useState(false);
  const trimmed = name.trim();
  const error = trimmed.length < 1 || trimmed.length > 100 ? NAME_ERROR : null;

  return (
    <FormDialog
      title={area ? 'تعديل المنطقة' : 'إضافة منطقة'}
      onClose={onClose}
      onSubmit={async () => {
        setTouched(true);
        if (error) return false;
        if (area) await areasApi.update(area.id, { name: trimmed });
        else await areasApi.create({ name: trimmed });
        await onSaved();
      }}
    >
      <TextField
        label="اسم المنطقة"
        value={name}
        onChange={(e) => setName(e.target.value)}
        error={touched && Boolean(error)}
        helperText={touched ? error : null}
        required
        fullWidth
        autoFocus
      />
    </FormDialog>
  );
}

/** «المناطق» (specs/004 US1). */
export default function AreasTab() {
  const areas = useQuery({ queryKey: ['settings', 'areas'], queryFn: areasApi.list });
  const actions = useItemActions(areasApi);
  const [editing, setEditing] = useState<Area | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Area | null>(null);

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Button variant="contained" startIcon={<AddOutlined />} onClick={() => setEditing('new')}>
          إضافة منطقة
        </Button>
      </Box>
      {areas.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {areas.isError && <Alert severity="error">{areas.error.message}</Alert>}
      {areas.isSuccess && (
        <ItemList
          rows={areas.data}
          emptyText="لا توجد مناطق بعد"
          columns={[
            { header: 'المنطقة', render: (a) => a.name },
            { header: 'الأبراج', render: (a) => a.tower_count },
          ]}
          actions={(a) => (
            <>
              <Button size="small" onClick={() => setEditing(a)}>
                تعديل
              </Button>
              {a.is_active ? (
                <Button
                  size="small"
                  color="warning"
                  disabled={actions.busy}
                  onClick={() => actions.setActive(a.id, false)}
                >
                  إيقاف
                </Button>
              ) : (
                <Button
                  size="small"
                  color="success"
                  disabled={actions.busy}
                  onClick={() => actions.setActive(a.id, true)}
                >
                  تفعيل
                </Button>
              )}
              {!a.in_use && (
                <Button size="small" color="error" onClick={() => setDeleting(a)}>
                  حذف
                </Button>
              )}
            </>
          )}
        />
      )}
      {editing !== null && (
        <AreaDialog
          area={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await actions.saved();
          }}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        title="حذف المنطقة"
        message={`حذف منطقة «${deleting?.name ?? ''}» نهائياً؟ يمكن الحذف فقط لأنها غير مستعملة.`}
        confirmLabel="حذف"
        busy={actions.busy}
        onConfirm={async () => {
          if (deleting && (await actions.remove(deleting.id))) setDeleting(null);
        }}
        onClose={() => setDeleting(null)}
      />
      <Snackbar
        open={actions.notice !== null}
        autoHideDuration={4000}
        onClose={actions.clearNotice}
        message={actions.notice}
      />
    </>
  );
}
