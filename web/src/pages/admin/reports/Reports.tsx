import FileDownloadOutlined from '@mui/icons-material/FileDownloadOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import Paper from '@mui/material/Paper';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';

import {
  DATE_KIND_LABELS,
  PERIOD_LABELS,
  REQUEST_TYPE_LABELS,
  type DateKind,
  type PeriodKind,
} from '../../../lib/labels';
import {
  EXPORTS_QUERY_KEY,
  REPORT_PAGE_SIZE,
  createExport,
  fetchOptions,
  fetchReport,
  type ReportFilters,
  type ReportRow,
  type ReportStatus,
  type RequestType,
} from '../../../lib/reports';
import { STATUS_COLORS, STATUS_LABELS } from '../../../lib/requestStatus';
import { formatBaghdad } from '../../../lib/time';
import ExportsList from './ExportsList';

const STATUSES: ReportStatus[] = ['pending_review', 'approved', 'rejected', 'linked'];
const TYPES: RequestType[] = ['new', 'additional', 'return'];

/** The choices of the form; ids and codes as strings, '' = all. */
interface Form {
  period: PeriodKind;
  from: string;
  to: string;
  date_kind: DateKind;
  area_id: string;
  tower_id: string;
  marketer_id: string;
  plan_id: string;
  status: string;
  type: string;
}

const INITIAL: Form = {
  period: 'month',
  from: '',
  to: '',
  date_kind: 'submitted',
  area_id: '',
  tower_id: '',
  marketer_id: '',
  plan_id: '',
  status: '',
  type: '',
};

/** The filters sent to the server, or null while a range lacks one of its days. */
function toFilters(form: Form): ReportFilters | null {
  const filters: ReportFilters = { period: form.period, date_kind: form.date_kind };
  if (form.period === 'range') {
    if (!form.from || !form.to) return null;
    filters.from = form.from;
    filters.to = form.to;
  }
  if (form.area_id) filters.area_id = Number(form.area_id);
  if (form.tower_id) filters.tower_id = Number(form.tower_id);
  if (form.marketer_id) filters.marketer_id = Number(form.marketer_id);
  if (form.plan_id) filters.plan_id = Number(form.plan_id);
  if (form.status) filters.status = form.status as ReportStatus;
  if (form.type) filters.type = form.type as RequestType;
  return filters;
}

function Select({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <TextField
      id={id}
      select
      label={label}
      size="small"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      sx={{ minWidth: 150, flex: '1 1 150px' }}
      slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
    >
      <option value="">الكل</option>
      {children}
    </TextField>
  );
}

function StatusChip({ status }: { status: ReportStatus }) {
  const color = STATUS_COLORS[status];
  return (
    <Chip
      size="small"
      label={STATUS_LABELS[status]}
      sx={{ bgcolor: color.bg, color: color.fg, fontWeight: 600 }}
    />
  );
}

function Row({ row }: { row: ReportRow }) {
  const parts = [
    row.tower,
    row.plan,
    row.marketer,
    `التقديم ${formatBaghdad(row.submitted_at)}`,
    row.linked_at ? `الربط ${formatBaghdad(row.linked_at)}` : null,
  ].filter((part): part is string => Boolean(part));
  return (
    <Card variant="outlined" data-testid="report-row">
      <CardActionArea component={RouterLink} to={`/admin/subscribers/sijil/${row.id}`}>
        <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Stack
            direction="row"
            sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}
          >
            <Stack spacing={0.25} sx={{ minWidth: 0 }}>
              <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Typography variant="body2" dir="ltr" component="span">
                  {row.number_label}
                </Typography>
                <Chip size="small" variant="outlined" label={REQUEST_TYPE_LABELS[row.type]} />
              </Stack>
              {row.deleted ? (
                <Typography color="text.secondary">محذوف</Typography>
              ) : (
                <Typography sx={{ fontWeight: 700 }}>{row.name ?? '—'}</Typography>
              )}
              <Stack
                direction="row"
                divider={<span aria-hidden>·</span>}
                sx={{ gap: 0.75, color: 'text.secondary', flexWrap: 'wrap' }}
              >
                {parts.map((part) => (
                  <Typography key={part} variant="body2" component="span" dir="auto">
                    {part}
                  </Typography>
                ))}
              </Stack>
            </Stack>
            <StatusChip status={row.status} />
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function SummaryList({
  title,
  items,
}: {
  title: string;
  items: { label: string; count: number }[];
}) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, flex: '1 1 200px' }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
        {title}
      </Typography>
      {items.map((item) => (
        <Stack
          key={item.label}
          direction="row"
          sx={{ justifyContent: 'space-between', gap: 1 }}
          component="div"
        >
          <Typography variant="body2" dir="auto">
            {item.label}
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {item.count}
          </Typography>
        </Stack>
      ))}
    </Paper>
  );
}

/**
 * «تصدير» for the current filters (specs/019 US2). The identity box shows only when the server
 * allows it (`can_export_identity`: the main admin, or `reports` + `review`) and starts unticked
 * (FR-008, FR-009); the server checks it again.
 */
function ExportControls({
  filters,
  allowIdentity,
}: {
  filters: ReportFilters | null;
  allowIdentity: boolean;
}) {
  const [identity, setIdentity] = useState(false);
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: () => createExport(filters!, allowIdentity && identity),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EXPORTS_QUERY_KEY }),
  });
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Stack
        direction="row"
        sx={{ gap: 1.5, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}
      >
        {allowIdentity ? (
          <FormControlLabel
            control={
              <Checkbox checked={identity} onChange={(e) => setIdentity(e.target.checked)} />
            }
            label="تضمين الرقم الوطني والعائلي والصور"
          />
        ) : (
          <Typography variant="body2" color="text.secondary">
            الملف بدون الرقم الوطني والعائلي والصور.
          </Typography>
        )}
        <Button
          variant="contained"
          startIcon={<FileDownloadOutlined />}
          disabled={filters === null || create.isPending}
          onClick={() => create.mutate()}
        >
          تصدير
        </Button>
      </Stack>
      {create.isError && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {create.error.message}
        </Alert>
      )}
    </Paper>
  );
}

/**
 * «التقارير والتصدير» (docs/system.md v1.25 §11; specs/019 US1): the submitted requests of a
 * period by submission or link date, narrowed by area, tower, marketer, plan, status and type,
 * with counts by status, tower and marketer. No amount appears here (FR-016); the server decides
 * what each permission sees (FR-002).
 */
export default function Reports() {
  const [form, setForm] = useState<Form>(INITIAL);
  const [page, setPage] = useState(1);
  const filters = useMemo(() => toFilters(form), [form]);
  const set = (patch: Partial<Form>) => {
    setForm((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  const options = useQuery({ queryKey: ['report-options'], queryFn: fetchOptions });
  const report = useQuery({
    queryKey: ['report', filters, page],
    queryFn: () => fetchReport(filters!, page),
    enabled: filters !== null,
    placeholderData: keepPreviousData,
  });

  const towers = (options.data?.towers ?? []).filter(
    (t) => !form.area_id || String(t.area_id) === form.area_id,
  );
  const data = report.data;

  return (
    <Stack spacing={2} sx={{ maxWidth: 960 }}>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700 }}>
        التقارير والتصدير
      </Typography>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack spacing={1.5}>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <ToggleButtonGroup
              exclusive
              size="small"
              value={form.period}
              onChange={(_, value: PeriodKind | null) => value && set({ period: value })}
            >
              {(Object.keys(PERIOD_LABELS) as PeriodKind[]).map((kind) => (
                <ToggleButton key={kind} value={kind}>
                  {PERIOD_LABELS[kind]}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            <ToggleButtonGroup
              exclusive
              size="small"
              value={form.date_kind}
              onChange={(_, value: DateKind | null) => value && set({ date_kind: value })}
            >
              {(Object.keys(DATE_KIND_LABELS) as DateKind[]).map((kind) => (
                <ToggleButton key={kind} value={kind}>
                  {DATE_KIND_LABELS[kind]}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Box>
          {form.period === 'range' && (
            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
              <TextField
                id="report-from"
                label="من"
                type="date"
                size="small"
                value={form.from}
                onChange={(e) => set({ from: e.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                id="report-to"
                label="إلى"
                type="date"
                size="small"
                value={form.to}
                onChange={(e) => set({ to: e.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Box>
          )}
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            <Select
              id="report-area"
              label="المنطقة"
              value={form.area_id}
              onChange={(v) => set({ area_id: v, tower_id: '' })}
            >
              {options.data?.areas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.active ? a.name : `${a.name} (موقوفة)`}
                </option>
              ))}
            </Select>
            <Select
              id="report-tower"
              label="البرج"
              value={form.tower_id}
              onChange={(v) => set({ tower_id: v })}
            >
              {towers.map((t) => (
                <option key={t.id} value={t.id}>
                  {`${t.name} (${t.code})${t.active ? '' : ' (موقوف)'}`}
                </option>
              ))}
            </Select>
            <Select
              id="report-marketer"
              label="المسوّق"
              value={form.marketer_id}
              onChange={(v) => set({ marketer_id: v })}
            >
              {options.data?.marketers.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.archived ? `${m.name} (مؤرشف)` : m.name}
                </option>
              ))}
            </Select>
            <Select
              id="report-plan"
              label="الفئة"
              value={form.plan_id}
              onChange={(v) => set({ plan_id: v })}
            >
              {options.data?.plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.active ? p.name : `${p.name} (موقوفة)`}
                </option>
              ))}
            </Select>
            <Select
              id="report-status"
              label="الحالة"
              value={form.status}
              onChange={(v) => set({ status: v })}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
            <Select
              id="report-type"
              label="النوع"
              value={form.type}
              onChange={(v) => set({ type: v })}
            >
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {REQUEST_TYPE_LABELS[t]}
                </option>
              ))}
            </Select>
          </Box>
        </Stack>
      </Paper>

      {filters === null && (
        <Typography variant="body2" color="text.secondary">
          اختر يوم البداية ويوم النهاية.
        </Typography>
      )}
      <ExportsList />
      {report.isPending && filters !== null && <Skeleton height={96} />}
      {report.isError && <Alert severity="error">{report.error.message}</Alert>}
      {data && !report.isError && (
        <>
          <Typography variant="body2" color="text.secondary" data-testid="report-total">
            {`العدد: ${data.total}`}
          </Typography>
          {data.total === 0 ? (
            <Typography color="text.secondary">لا توجد طلبات بهذه الفلاتر</Typography>
          ) : (
            <>
              <ExportControls filters={filters} allowIdentity={data.can_export_identity} />
              <Box
                data-testid="report-summary"
                sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}
              >
                <SummaryList
                  title="حسب الحالة"
                  items={data.summary.by_status.map((s) => ({
                    label: STATUS_LABELS[s.status],
                    count: s.count,
                  }))}
                />
                <SummaryList
                  title="حسب البرج"
                  items={data.summary.by_tower.map((t) => ({ label: t.tower, count: t.count }))}
                />
                <SummaryList
                  title="حسب المسوّق"
                  items={data.summary.by_marketer.map((m) => ({
                    label: m.marketer,
                    count: m.count,
                  }))}
                />
              </Box>
              {data.rows.map((row) => (
                <Row key={row.id} row={row} />
              ))}
              {data.total > REPORT_PAGE_SIZE && (
                <Stack direction="row" sx={{ gap: 1 }}>
                  <Button disabled={page === 1} onClick={() => setPage(page - 1)}>
                    السابق
                  </Button>
                  <Button
                    disabled={page * REPORT_PAGE_SIZE >= data.total}
                    onClick={() => setPage(page + 1)}
                  >
                    التالي
                  </Button>
                </Stack>
              )}
            </>
          )}
        </>
      )}
    </Stack>
  );
}
