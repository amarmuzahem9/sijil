import AddOutlined from '@mui/icons-material/AddOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { FormDialog } from '../../../components/FormDialog';
import { ItemList } from '../../../components/ItemList';
import { areasApi, towersApi } from '../../../lib/settings';
import type { Area, Tower } from '../../../lib/settings';
import { useItemActions } from './useItemActions';

const CODE_RE = /^[A-Z0-9]{2,20}$/;

function TowerDialog({
  tower,
  areas,
  onSaved,
  onClose,
}: {
  tower: Tower | null;
  areas: Area[];
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const [code, setCode] = useState(tower?.code ?? '');
  const [name, setName] = useState(tower?.name ?? '');
  const [areaId, setAreaId] = useState<number | ''>(tower?.area.id ?? '');
  const [touched, setTouched] = useState(false);

  const cleanCode = code.trim().toUpperCase();
  const codeError = CODE_RE.test(cleanCode)
    ? null
    : 'الرمز أحرف إنجليزية كبيرة وأرقام فقط (2 إلى 20)';
  const nameError =
    name.trim().length < 1 || name.trim().length > 100 ? 'الاسم يجب أن يكون بين 1 و100 حرف' : null;
  const areaError = areaId === '' ? 'اختر المنطقة' : null;
  // New towers: active areas only. Editing: any area, including the tower's current one.
  const choices = tower ? areas : areas.filter((a) => a.is_active);

  return (
    <FormDialog
      title={tower ? 'تعديل البرج' : 'إضافة برج'}
      onClose={onClose}
      onSubmit={async () => {
        setTouched(true);
        if (codeError || nameError || areaError || areaId === '') return false;
        const body = { code: cleanCode, name: name.trim(), area_id: areaId };
        if (tower) {
          await towersApi.update(
            tower.id,
            tower.in_use ? { name: body.name, area_id: areaId } : body,
          );
        } else {
          await towersApi.create(body);
        }
        await onSaved();
      }}
    >
      <TextField
        label="رمز البرج"
        value={code}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        error={touched && Boolean(codeError)}
        helperText={
          tower?.in_use ? 'البرج مستعمل، لا يمكن تغيير رمزه' : touched ? codeError : 'مثال: ALM01'
        }
        disabled={Boolean(tower?.in_use)}
        required
        fullWidth
        autoFocus={!tower}
        slotProps={{ htmlInput: { dir: 'ltr', autoCapitalize: 'characters' } }}
      />
      <TextField
        label="اسم البرج"
        value={name}
        onChange={(e) => setName(e.target.value)}
        error={touched && Boolean(nameError)}
        helperText={touched ? nameError : null}
        required
        fullWidth
      />
      <TextField
        select
        label="المنطقة"
        value={areaId}
        onChange={(e) => setAreaId(Number(e.target.value))}
        error={touched && Boolean(areaError)}
        helperText={
          touched && areaError ? areaError : choices.length === 0 ? 'أضف منطقة فعّالة أولاً' : null
        }
        required
        fullWidth
      >
        {choices.map((a) => (
          <MenuItem key={a.id} value={a.id}>
            {a.name}
            {a.is_active ? '' : ' (موقوفة)'}
          </MenuItem>
        ))}
      </TextField>
    </FormDialog>
  );
}

/** «الأبراج» (specs/004 US1). */
export default function TowersTab() {
  const towers = useQuery({ queryKey: ['settings', 'towers'], queryFn: towersApi.list });
  const areas = useQuery({ queryKey: ['settings', 'areas'], queryFn: areasApi.list });
  const actions = useItemActions(towersApi);
  const [editing, setEditing] = useState<Tower | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Tower | null>(null);

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Button variant="contained" startIcon={<AddOutlined />} onClick={() => setEditing('new')}>
          إضافة برج
        </Button>
      </Box>
      {towers.isPending && <CircularProgress aria-label="جارٍ التحميل" />}
      {towers.isError && <Alert severity="error">{towers.error.message}</Alert>}
      {towers.isSuccess && (
        <ItemList
          rows={towers.data}
          emptyText="لا توجد أبراج بعد"
          columns={[
            { header: 'الرمز', render: (t) => <bdi dir="ltr">{t.code}</bdi> },
            { header: 'الاسم', render: (t) => t.name },
            {
              header: 'المنطقة',
              render: (t) => `${t.area.name}${t.area.is_active ? '' : ' (موقوفة)'}`,
            },
          ]}
          actions={(t) => (
            <>
              <Button size="small" onClick={() => setEditing(t)}>
                تعديل
              </Button>
              {t.is_active ? (
                <Button
                  size="small"
                  color="warning"
                  disabled={actions.busy}
                  onClick={() => actions.setActive(t.id, false)}
                >
                  إيقاف
                </Button>
              ) : (
                <Button
                  size="small"
                  color="success"
                  disabled={actions.busy}
                  onClick={() => actions.setActive(t.id, true)}
                >
                  تفعيل
                </Button>
              )}
              {!t.in_use && (
                <Button size="small" color="error" onClick={() => setDeleting(t)}>
                  حذف
                </Button>
              )}
            </>
          )}
        />
      )}
      {editing !== null && (
        <TowerDialog
          tower={editing === 'new' ? null : editing}
          areas={areas.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await actions.saved();
          }}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        title="حذف البرج"
        message={`حذف البرج ${deleting?.code ?? ''} نهائياً؟ يمكن الحذف فقط لأنه غير مستعمل.`}
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
