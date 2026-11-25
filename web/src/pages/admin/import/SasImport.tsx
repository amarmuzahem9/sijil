/**
 * «مشتركو SAS» (docs/system.md 1.20 §12.2; specs/015 US1, research R16). One page, in steps:
 * 1. choose the SAS export;
 * 2. the preview: counts, the table of prefixes with no tower by the rule (a tower, or «بلا برج»,
 *    each), and flagged rows grouped by problem, with a choice per row and «تخطي للكل» per group;
 * 3. «تأكيد الاستيراد»;
 * 4. the summary.
 * Nothing is saved before the confirmation. The server holds the preview and every choice, so the
 * page shows what the server answered.
 */
import UploadFileOutlined from '@mui/icons-material/UploadFileOutlined';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { useState } from 'react';

import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { ApiError } from '../../../lib/api';
import {
  SAS_CHOICE_LABELS,
  SAS_FLAG_LABELS,
  SAS_INFO_LABELS,
  SAS_KIND_LABELS,
  type SasChoice,
  type SasChoiceItem,
  type SasCounts,
  type SasFlagGroup,
  type SasFlaggedRow,
  type SasImportSummary,
  type SasPrefix,
  type SasPrefixItem,
  type SasPreview,
  type SasTower,
  cancelSasPreview,
  confirmSasImport,
  groupSasFlagged,
  sasFlagText,
  setSasChoices,
  towerLabel,
  uploadSasFile,
} from '../../../lib/sasImport';

const FILE_LABEL = 'ملف مشتركي SAS (xlsx أو csv)';
const PAGE = 200;
const NO_TOWER = 'none';

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'حدث خطأ غير متوقع، حاول مرة أخرى';
}

function PrefixRow({
  entry,
  towers,
  busy,
  onMap,
}: {
  entry: SasPrefix;
  towers: SasTower[];
  busy: boolean;
  onMap: (item: SasPrefixItem) => void;
}) {
  const value = !entry.chosen ? '' : entry.tower_id === null ? NO_TOWER : String(entry.tower_id);
  return (
    <Stack
      data-testid={`prefix-${entry.prefix}`}
      direction={{ xs: 'column', sm: 'row' }}
      spacing={1}
      sx={{ alignItems: { sm: 'center' } }}
    >
      <Typography sx={{ fontWeight: 700, minWidth: 96 }} dir="ltr">
        {entry.prefix}
      </Typography>
      <Typography color="text.secondary" sx={{ minWidth: 56 }}>
        {entry.rows} صف
      </Typography>
      <TextField
        select
        size="small"
        value={value}
        disabled={busy}
        sx={{ minWidth: 220 }}
        slotProps={{
          select: { native: true },
          htmlInput: { 'aria-label': `برج ${entry.prefix}` },
        }}
        onChange={(e) => {
          const chosen = e.target.value;
          if (!chosen) return;
          onMap({ prefix: entry.prefix, tower_id: chosen === NO_TOWER ? null : Number(chosen) });
        }}
      >
        <option value="" disabled>
          اختر البرج
        </option>
        <option value={NO_TOWER}>بلا برج</option>
        {towers.map((tower) => (
          <option key={tower.id} value={tower.id}>
            {towerLabel(tower)}
          </option>
        ))}
      </TextField>
      {entry.from_previous && <Chip size="small" variant="outlined" label="من استيراد سابق" />}
    </Stack>
  );
}

function RowCard({
  row,
  busy,
  onChoose,
}: {
  row: SasFlaggedRow;
  busy: boolean;
  onChoose: (items: SasChoiceItem[]) => void;
}) {
  const phones = [row.phone, row.username_phone !== row.phone ? row.username_phone : null]
    .filter(Boolean)
    .join('، ');
  return (
    <Card variant="outlined" data-testid={`row-${row.index}`}>
      <CardContent>
        <Stack spacing={1}>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
            <Typography sx={{ fontWeight: 700 }} dir="ltr">
              {row.username ?? '—'}
            </Typography>
            <Typography color="text.secondary">الصف {row.index}</Typography>
            {row.sas_id && <Typography color="text.secondary">SAS {row.sas_id}</Typography>}
            <Chip size="small" label={SAS_KIND_LABELS[row.kind]} />
          </Stack>
          <Typography>{row.full_name || '—'}</Typography>
          <Typography variant="body2" color="text.secondary">
            الهاتف: <span dir="ltr">{phones || '—'}</span>
          </Typography>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.5 }}>
            {row.flags.map((flag, i) => (
              <Chip key={i} size="small" variant="outlined" label={sasFlagText(flag)} />
            ))}
          </Stack>
          {row.allowed.length > 0 && (
            <ToggleButtonGroup
              exclusive
              size="small"
              value={row.choice}
              disabled={busy}
              onChange={(_, choice: SasChoice | null) => {
                if (choice) onChoose([{ index: row.index, choice }]);
              }}
            >
              {row.allowed.map((choice) => (
                <ToggleButton key={choice} value={choice}>
                  {SAS_CHOICE_LABELS[choice]}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
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
  group: SasFlagGroup;
  busy: boolean;
  onChoose: (items: SasChoiceItem[]) => void;
}) {
  const [shown, setShown] = useState(PAGE);
  const skippable = group.rows.filter((r) => r.allowed.includes('skip'));
  const more = group.rows.length - shown;
  return (
    <Stack spacing={1} data-testid={`group-${group.code}`}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700 }}>
          {SAS_FLAG_LABELS[group.code]} ({group.rows.length})
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
      {group.rows.slice(0, shown).map((row) => (
        <RowCard key={row.index} row={row} busy={busy} onChoose={onChoose} />
      ))}
      {more > 0 && (
        <Button onClick={() => setShown(shown + PAGE)} sx={{ alignSelf: 'flex-start' }}>
          عرض المزيد ({Math.min(more, PAGE)})
        </Button>
      )}
    </Stack>
  );
}

function Summary({ summary, onAgain }: { summary: SasImportSummary; onAgain: () => void }) {
  const skipped = summary.skipped_rows
    .map((r) => `الصف ${r.index}${r.sas_id ? ` (SAS ${r.sas_id})` : ''}`)
    .join('، ');
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1}>
        <Alert severity="success">تم الاستيراد</Alert>
        <Typography>عدد الصفوف: {summary.rows}</Typography>
        <Typography>المضاف: {summary.added}</Typography>
        <Typography>المحدَّث: {summary.updated}</Typography>
        <Typography>بلا تغيير: {summary.unchanged}</Typography>
        <Typography>المتخطّى: {summary.skipped}</Typography>
        <Typography>وُسم «غير موجود في آخر ملف»: {summary.missing_marked}</Typography>
        <Typography>عاد في هذا الملف: {summary.missing_cleared}</Typography>
        <Typography>بلا هاتف صالح: {summary.without_phone}</Typography>
        <Typography>بادئات رُبطت: {summary.prefixes_mapped}</Typography>
        {skipped && <Typography>الصفوف المتخطّاة: {skipped}</Typography>}
        <Button variant="outlined" onClick={onAgain} sx={{ alignSelf: 'flex-start' }}>
          استيراد ملف آخر
        </Button>
      </Stack>
    </Paper>
  );
}

function infoChips(counts: SasCounts) {
  return (Object.keys(SAS_INFO_LABELS) as (keyof SasCounts)[])
    .filter((key) => counts[key] > 0)
    .map((key) => (
      <Chip key={key} variant="outlined" label={`${SAS_INFO_LABELS[key]}: ${counts[key]}`} />
    ));
}

export default function SasImport() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<SasPreview | null>(null);
  const [summary, setSummary] = useState<SasImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

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
    const created = await run(() => uploadSasFile(file));
    if (created) setPreview(created);
  }

  async function update(choices: SasChoiceItem[], prefixes: SasPrefixItem[]) {
    if (!preview) return;
    setNotice(null);
    const updated = await run(() => setSasChoices(preview.id, choices, prefixes));
    if (updated) setPreview(updated);
  }

  async function confirm() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      setSummary(await confirmSasImport(preview.id));
      setPreview(null);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'preview_changed' && err.extra.preview) {
        setPreview(err.extra.preview as SasPreview);
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
    await run(() => cancelSasPreview(id));
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
          ارفع ملف المشتركين المصدَّر من SAS. لا يُحفظ شيء قبل «تأكيد الاستيراد»، وعمود كلمة السر لا
          يُقرأ ولا يُحفظ.
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

  const { counts } = preview;
  const notImported = (kind: SasFlaggedRow['kind']) =>
    preview.flagged.filter((r) => r.kind === kind && r.choice !== 'import').length;
  const toAdd = counts.new - notImported('new');
  const toUpdate = counts.update - notImported('update');
  const groups = groupSasFlagged(preview.flagged);
  const waiting = counts.waiting_choice > 0 || preview.waiting_prefixes > 0;

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
            <Chip color="success" label={`${SAS_KIND_LABELS.new}: ${counts.new}`} />
            <Chip color="info" label={`${SAS_KIND_LABELS.update}: ${counts.update}`} />
            <Chip label={`${SAS_KIND_LABELS.unchanged}: ${counts.unchanged}`} />
            <Chip color="warning" label={`تحتاج قراراً: ${counts.flagged}`} />
          </Stack>
          <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1 }}>
            {infoChips(counts)}
          </Stack>
        </Stack>
      </Paper>

      {preview.prefixes.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={1.5}>
            <Typography component="h3" variant="subtitle1" sx={{ fontWeight: 700 }}>
              بادئات بلا برج معروف
            </Typography>
            <Typography variant="body2" color="text.secondary">
              اختر برج كل بادئة أو «بلا برج». يُحفظ الاختيار للاستيرادات القادمة.
            </Typography>
            {preview.prefixes.map((entry) => (
              <PrefixRow
                key={entry.prefix}
                entry={entry}
                towers={preview.towers}
                busy={busy}
                onMap={(item) => update([], [item])}
              />
            ))}
          </Stack>
        </Paper>
      )}

      {groups.map((group) => (
        <Group key={group.code} group={group} busy={busy} onChoose={(items) => update(items, [])} />
      ))}

      <Stack spacing={1}>
        {counts.waiting_choice > 0 && (
          <Typography color="warning.main">بقيت {counts.waiting_choice} صفوف بلا اختيار</Typography>
        )}
        {preview.waiting_prefixes > 0 && (
          <Typography color="warning.main">
            بقيت {preview.waiting_prefixes} بادئة بلا برج
          </Typography>
        )}
        <Stack direction="row" spacing={1}>
          <Button
            variant="contained"
            disabled={busy || waiting}
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
        message={`سيُضاف ${toAdd} ويُحدَّث ${toUpdate} من مشتركي SAS. لا يمكن التراجع بعد التأكيد.`}
        confirmLabel="استيراد"
        busy={busy}
        onConfirm={confirm}
        onClose={() => setConfirming(false)}
      />
    </Stack>
  );
}
