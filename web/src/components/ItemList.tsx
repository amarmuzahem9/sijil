import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
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

import { StateChip } from './AccountList';

export interface ItemColumn<T> {
  header: string;
  render: (row: T) => ReactNode;
}

/**
 * Settings lists (specs/004): cards on a phone, a table from `md` up. The first column is the
 * card title; the state chip and the actions come last.
 */
export function ItemList<T extends { id: number; is_active: boolean }>({
  rows,
  columns,
  actions,
  emptyText,
}: {
  rows: T[];
  columns: ItemColumn<T>[];
  actions: (row: T) => ReactNode;
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

  const [title, ...rest] = columns;

  if (!desktop) {
    return (
      <Stack spacing={1.5}>
        {rows.map((row) => (
          <Card key={row.id} variant="outlined" data-testid="item-row">
            <CardContent sx={{ pb: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <Typography component="div" sx={{ fontWeight: 600, flexGrow: 1 }}>
                  {title.render(row)}
                </Typography>
                <StateChip active={row.is_active} />
              </Box>
              {rest.map((col) => (
                <Typography key={col.header} variant="body2" component="div">
                  <Typography component="span" variant="body2" color="text.secondary">
                    {col.header}:{' '}
                  </Typography>
                  {col.render(row)}
                </Typography>
              ))}
            </CardContent>
            <CardActions sx={{ flexWrap: 'wrap', gap: 0.5 }}>{actions(row)}</CardActions>
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
            {columns.map((col) => (
              <TableCell key={col.header}>{col.header}</TableCell>
            ))}
            <TableCell>الحالة</TableCell>
            <TableCell align="left">الإجراءات</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.id} data-testid="item-row">
              {columns.map((col, i) => (
                <TableCell key={col.header} sx={i === 0 ? { fontWeight: 600 } : undefined}>
                  {col.render(row)}
                </TableCell>
              ))}
              <TableCell>
                <StateChip active={row.is_active} />
              </TableCell>
              <TableCell align="left">
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>{actions(row)}</Box>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
