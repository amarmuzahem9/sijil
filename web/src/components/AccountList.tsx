import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import type { ReactNode } from 'react';

import { STATE_LABELS } from '../lib/labels';

export interface AccountRow {
  id: number;
  name: string;
  phone: string;
  /** null = no state chip (the main admin row). */
  isActive: boolean | null;
  extra?: ReactNode;
  actions?: ReactNode;
}

export function StateChip({ active }: { active: boolean }) {
  return (
    <Chip
      size="small"
      color={active ? 'success' : 'default'}
      variant={active ? 'filled' : 'outlined'}
      label={active ? STATE_LABELS.active : STATE_LABELS.inactive}
    />
  );
}

/** Cards on a phone, a table from `md` up (specs/002 contracts/ui-routes.md). */
export function AccountList({
  rows,
  extraHeader,
  emptyText,
}: {
  rows: AccountRow[];
  extraHeader?: string;
  emptyText: string;
}) {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up('md'), { noSsr: true });

  if (rows.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">{emptyText}</Typography>
      </Paper>
    );
  }

  if (!desktop) {
    return (
      <Stack spacing={1.5}>
        {rows.map((r) => (
          <Card key={r.id} variant="outlined" data-testid="account-row">
            <CardContent sx={{ pb: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <Typography sx={{ fontWeight: 600, flexGrow: 1 }}>{r.name}</Typography>
                {r.isActive !== null && <StateChip active={r.isActive} />}
              </Box>
              <Typography color="text.secondary" component="div">
                <bdi dir="ltr">{r.phone}</bdi>
              </Typography>
              {r.extra && <Box sx={{ mt: 1 }}>{r.extra}</Box>}
            </CardContent>
            {r.actions && (
              <CardActions sx={{ flexWrap: 'wrap', gap: 0.5 }}>{r.actions}</CardActions>
            )}
          </Card>
        ))}
      </Stack>
    );
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>الاسم</TableCell>
            <TableCell>الهاتف</TableCell>
            {extraHeader && <TableCell>{extraHeader}</TableCell>}
            <TableCell>الحالة</TableCell>
            <TableCell align="left">الإجراءات</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id} data-testid="account-row">
              <TableCell sx={{ fontWeight: 600 }}>{r.name}</TableCell>
              <TableCell>
                <bdi dir="ltr">{r.phone}</bdi>
              </TableCell>
              {extraHeader && <TableCell>{r.extra}</TableCell>}
              <TableCell>{r.isActive !== null && <StateChip active={r.isActive} />}</TableCell>
              <TableCell align="left">
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>{r.actions}</Box>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
