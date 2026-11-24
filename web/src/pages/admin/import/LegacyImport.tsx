/**
 * «المشتركون القدامى» (docs/system.md 1.19 §12.1; specs/014 US1). One page, in steps: choose the
 * Google Form export → «جارٍ سحب الصور N من M» → the preview (counts, «الحالة» values, flagged rows
 * grouped by problem, a choice per row, «تخطي للكل» per group, a correction field for an odd family
 * number) → «تأكيد الاستيراد» → the summary. Nothing is saved before the confirmation; the server
 * holds the preview and every choice, so the page shows what the server answered.
 */
import UploadFileOutlined from '@mui/icons-material/UploadFileOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';

import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { ApiError } from '../../../lib/api';
import {
  CHOICE_LABELS,
  FLAG_LABELS,
  type Choice,
  type ChoiceItem,
  type FlagGroup,
  type FlaggedRow,
  type ImportSummary,
  type LegacyPreview,
  cancelPreview,
  confirmImport,
  flagText,
  getPreview,
  groupFlagged,
  setChoices,
  uploadLegacyFile,
} from '../../../lib/legacyImport';

const FILE_LABEL = 'ملف المشتركين القدامى (xlsx أو csv)';

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'حدث خطأ غير متوقع، حاول مرة أخرى';
}

function RowCard({
  row,
  busy,
  onChoose,
}: {
  row: FlaggedRow;
  busy: boolean;
  onChoose: (items: ChoiceItem[]) => void;
}) {
  const [correcting, setCorrecting] = useState(row.choice === 'correct');
  const [value, setValue] = useState(row.corrected_family_number ?? row.family_number_file ?? '');
  const shown: Choice | null = correcting ? 'correct' : row.choice;

  function choose(choice: Choice | null) {
    if (choice === null) return;
    if (choice === 'correct') {
      setCorrecting(true);
      return;
    }
    setCorrecting(false);
    onChoose([{ index: row.index, choice }]);
  }

  return (
    <Card variant="outlined" data-testid={`row-${row.index}`}>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
            <Typography sx={{ fontWeight: 700 }} dir="ltr">
              {row.legacy_number ?? '—'}
            </Typography>
            <Typography color="text.secondary">الصف {row.index}</Typography>
            {!row.counts_in_check && <Chip size="small" color="warning" label="لا يُحسب في الفحص" />}
          </Stack>
          <Typography>{row.full_name || '—'}</Typography>
          <Typography variant="body2" color="text.secondary">
            الهاتف: <span dir="ltr">{row.phone_file ?? '—'}</span> · الرقم العائلي:{' '}
            <span dir="ltr">{row.family_number_file ?? '—'}</span>
            {row.status_text ? ` · الحالة: ${row.status_text}` : ''}
          </Typography>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.5 }}>
            {row.flags.map((flag, i) => (
              <Chip key={i} size="small" variant="outlined" label={flagText(flag)} />
            ))}
          </Stack>
          {row.allowed.length > 0 && (
            <ToggleButtonGroup
              exclusive
              size="small"
              value={shown}
              disabled={busy}
              onChange={(_, choice: Choice | null) => choose(choice)}
            >
              {row.allowed.map((choice) => (
                <ToggleButton key={choice} value={choice}>
                  {CHOICE_LABELS[choice]}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          )}
          {correcting && (
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <TextField
                size="small"
                label="الرقم العائلي الصحيح"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                slotProps={{ htmlInput: { dir: 'ltr', maxLength: 40 } }}
              />
              <Button
                variant="outlined"
                disabled={busy || !value.trim()}
                onClick={() =>
                  onChoose([{ index: row.index, choice: 'correct', family_number: value.trim() }])
                }
              >
                حفظ التصحيح
              </Button>
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}

function Group({
  group,
  busy,
  onChoose,
}: {
  group: FlagGroup;
  busy: boolean;
  onChoose: (items: ChoiceItem[]) => void;
}) {
  const skippable = group.rows.filter((r) => r.allowed.includes('skip'));
  return (
    <Stack spacing={1} data-testid={`group-${group.code}`}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700 }}>
          {FLAG_LABELS[group.code]} ({group.rows.length})
        </Typography>
        {skippable.length > 0 && (
          <Button
            size="small"
            disabled={busy}
            onClick={() => onChoose(skippable.map((r) => ({ index: r.index, choice: 'skip' })))}
          >
            تخطي للكل
          </Button>
        )}
      </Stack>
      {group.rows.map((row) => (
        <RowCard key={row.index} row={row} busy={busy} onChoose={onChoose} />
      ))}
    </Stack>
  );
}

function Summary({ summary, onAgain }: { summary: ImportSummary; onAgain: () => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1}>
        <Alert severity="success">تم الاستيراد</Alert>
        <Typography>عدد الصفوف: {summary.rows}</Typography>
        <Typography>المستورد: {summary.imported}</Typography>
        <Typography>المتخطّى: {summary.skipped}</Typography>
        <Typography>مستورد سابقاً: {summary.already_imported}</Typography>
        <Typography>لا يُحسب في الفحص: {summary.not_counted}</Typography>
        <Typography>غير مكتمل: {summary.incomplete}</Typography>
        <Typography>أرقام عائلية مصحّحة: {summary.corrected}</Typography>
        {summary.skipped_numbers.length > 0 && (
          <Typography>الصفوف المتخطّاة: {summary.skipped_numbers.join('، ')}</Typography>
        )}
        {summary.incomplete_numbers.length > 0 && (
          <Typography>الصفوف غير المكتملة: {summary.incomplete_numbers.join('، ')}</Typography>
        )}
        <Button variant="outlined" onClick={onAgain} sx={{ alignSelf: 'flex-start' }}>
          استيراد ملف آخر
        </Button>
      </Stack>
    </Paper>
  );
}

export default function LegacyImport({ pollMs = 2000 }: { pollMs?: number }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<LegacyPreview | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const previewId = preview?.id;
  const fetching = preview?.status === 'fetching';
  useEffect(() => {
    if (!previewId || !fetching) return;
    const timer = setTimeout(() => {
      getPreview(previewId)
        .then(setPreview)
        .catch((err) => {
          setError(messageOf(err));
          setPreview(null);
        });
    }, pollMs);
    return () => clearTimeout(timer);
  }, [previewId, fetching, preview, pollMs]);

  async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (err) {
      setError(messageOf(err));
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  async function upload() {
    if (!file) return;
    setNotice(null);
    const created = await run(() => uploadLegacyFile(file));
    if (created) setPreview(created);
  }

  async function choose(items: ChoiceItem[]) {
    if (!preview) return;
    setNotice(null);
    const updated = await run(() => setChoices(preview.id, items));
    if (updated) setPreview(updated);
  }

  async function confirm() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      setSummary(await confirmImport(preview.id));
      setPreview(null);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'preview_changed' && err.extra.preview) {
        setPreview(err.extra.preview as LegacyPreview);
        setNotice(err.message);
      } else {
        setError(messageOf(err));
      }
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  async function cancel() {
    if (!preview) return;
    const id = preview.id;
    await run(() => cancelPreview(id));
    setPreview(null);
    setNotice(null);
  }

  function reset() {
    setSummary(null);
    setPreview(null);
    setFile(null);
    setNotice(null);
    setError(null);
  }

  const errorAlert = error && <Alert severity="error">{error}</Alert>;

  if (summary) return <Summary summary={summary} onAgain={reset} />;

  if (!preview) {
    return (
      <Stack spacing={2}>
        {errorAlert}
        <Typography color="text.secondary">
          ارفع ملف Google Form للمشتركين القدامى. لا يُحفظ شيء قبل «تأكيد الاستيراد».
        </Typography>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={1}
          sx={{ alignItems: { sm: 'center' } }}
        >
          <Button component="label" variant="outlined" startIcon={<UploadFileOutlined />}>
            اختيار ملف
            <input
              hidden
              type="file"
              accept=".xlsx,.csv"
              aria-label={FILE_LABEL}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Button>
          <Typography variant="body2" dir="ltr">
            {file?.name ?? ''}
          </Typography>
        </Stack>
        <Button
          variant="contained"
          disabled={!file || busy}
          onClick={upload}
          sx={{ alignSelf: 'flex-start' }}
        >
          رفع ومعاينة
        </Button>
      </Stack>
    );
  }

  if (preview.status === 'fetching') {
    const fraction = preview.images_total ? preview.images_done / preview.images_total : 0;
    return (
      <Stack spacing={2}>
        {errorAlert}
        <Typography>
          جارٍ سحب الصور {preview.images_done} من {preview.images_total}
        </Typography>
        <LinearProgress variant="determinate" value={fraction * 100} />
        <Button onClick={cancel} disabled={busy} sx={{ alignSelf: 'flex-start' }}>
          إلغاء المعاينة
        </Button>
      </Stack>
    );
  }

  if (preview.status === 'failed') {
    return (
      <Stack spacing={2}>
        <Alert severity="error">تعذّرت المعاينة، ارفع الملف من جديد</Alert>
        <Button onClick={cancel} sx={{ alignSelf: 'flex-start' }}>
          رفع ملف آخر
        </Button>
      </Stack>
    );
  }

  const { counts } = preview;
  const toImport =
    counts.ready +
    preview.flagged.filter((r) => r.choice === 'import' || r.choice === 'correct').length;
  const groups = groupFlagged(preview.flagged);

  return (
    <Stack spacing={2}>
      {notice && <Alert severity="warning">{notice}</Alert>}
      {errorAlert}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1}>
          <Typography sx={{ fontWeight: 700 }} dir="ltr" component="div">
            {preview.file_name}
          </Typography>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            <Chip label={`عدد الصفوف: ${counts.rows}`} />
            <Chip color="success" label={`جاهزة: ${counts.ready}`} />
            <Chip color="warning" label={`تحتاج قراراً: ${counts.flagged}`} />
            <Chip label={`مستورد سابقاً: ${counts.already_imported}`} />
            <Chip label={`لا تُحسب في الفحص: ${counts.not_counted}`} />
          </Stack>
          <Typography variant="subtitle2">قيم «الحالة»</Typography>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            {preview.status_values.map((v) => (
              <Chip
                key={v.value ?? ''}
                size="small"
                variant="outlined"
                label={`${v.value ?? '(فارغة)'}: ${v.rows}${v.counts_in_check ? '' : ' (لا تُحسب في الفحص)'}`}
              />
            ))}
          </Stack>
        </Stack>
      </Paper>

      {groups.map((group) => (
        <Group key={group.code} group={group} busy={busy} onChoose={choose} />
      ))}

      <Stack spacing={1}>
        {counts.waiting_choice > 0 && (
          <Typography color="warning.main">بقيت {counts.waiting_choice} صفوف بلا اختيار</Typography>
        )}
        <Stack direction="row" spacing={1}>
          <Button
            variant="contained"
            disabled={busy || counts.waiting_choice > 0}
            onClick={() => setConfirming(true)}
          >
            تأكيد الاستيراد
          </Button>
          <Button onClick={cancel} disabled={busy}>
            إلغاء المعاينة
          </Button>
        </Stack>
      </Stack>

      <ConfirmDialog
        open={confirming}
        title="تأكيد الاستيراد"
        message={`سيُحفظ ${toImport} مشتركاً قديماً. لا يمكن التراجع بعد التأكيد.`}
        confirmLabel="استيراد"
        busy={busy}
        onConfirm={confirm}
        onClose={() => setConfirming(false)}
      />
    </Stack>
  );
}
