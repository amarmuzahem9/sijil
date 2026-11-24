/**
 * /notifications — «الإشعارات» (docs/system.md v1.17 §4.4, specs/012 US2, US4).
 * Newest first, older ones on «عرض الأقدم». Tapping a row marks it read and opens the request.
 * A deleted request (011) shows its number and «محذوف», never the erased name.
 */
import NotificationsNoneOutlined from '@mui/icons-material/NotificationsNoneOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  KIND_TITLES,
  listNotifications,
  markAllRead,
  markRead,
  notificationKeys,
  type NotificationItem,
} from '../../lib/notifications';
import { DELETED_TAG } from '../../lib/requests';
import { formatBaghdad } from '../../lib/time';

function Row({
  item,
  onOpen,
}: {
  item: NotificationItem;
  onOpen: (item: NotificationItem) => void;
}) {
  const unread = item.read_at === null;
  return (
    <ListItemButton
      data-testid={`notification-${item.id}`}
      data-unread={String(unread)}
      onClick={() => onOpen(item)}
      sx={{
        display: 'block',
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: unread ? 'action.selected' : undefined,
      }}
    >
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        {unread && (
          <Box
            aria-label="غير مقروء"
            sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'error.main', flexShrink: 0 }}
          />
        )}
        <Typography sx={{ fontWeight: unread ? 700 : 500 }}>{KIND_TITLES[item.kind]}</Typography>
      </Stack>
      <Stack
        direction="row"
        spacing={1}
        sx={{ mt: 0.5, alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}
      >
        <Typography dir="ltr" sx={{ fontWeight: 600 }}>{`#${item.number_label}`}</Typography>
        {item.deleted ? (
          <Chip
            size="small"
            label={DELETED_TAG.label}
            sx={{ bgcolor: DELETED_TAG.bg, color: DELETED_TAG.fg, fontWeight: 600 }}
          />
        ) : (
          item.full_name && <Typography color="text.secondary">{item.full_name}</Typography>
        )}
      </Stack>
      {item.reason_label && (
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          السبب: {item.reason_label}
        </Typography>
      )}
      <Typography variant="caption" color="text.secondary">
        {formatBaghdad(item.created_at)}
      </Typography>
    </ListItemButton>
  );
}

export default function Notifications() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [marking, setMarking] = useState(false);
  const query = useInfiniteQuery({
    queryKey: notificationKeys.list,
    queryFn: ({ pageParam }) => listNotifications(pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => last.next_before ?? undefined,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: notificationKeys.all });

  const open = async (item: NotificationItem) => {
    if (item.read_at === null) {
      try {
        await markRead(item.id);
      } catch {
        // Opening the request matters more than the read mark; the badge corrects itself.
      }
      void refresh();
    }
    navigate(`/requests/${item.request_id}`);
  };

  const readAll = async () => {
    setMarking(true);
    try {
      await markAllRead();
      await refresh();
    } finally {
      setMarking(false);
    }
  };

  if (query.isPending) return <CircularProgress aria-label="جارٍ التحميل" />;
  if (query.isError) return <Alert severity="warning">{query.error.message}</Alert>;

  const items = query.data.pages.flatMap((page) => page.items);
  const anyUnread = items.some((item) => item.read_at === null);

  return (
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6" component="h1" sx={{ fontWeight: 700 }}>
          الإشعارات
        </Typography>
        {items.length > 0 && (
          <Button size="small" onClick={() => void readAll()} disabled={marking || !anyUnread}>
            تعليم الكل كمقروء
          </Button>
        )}
      </Stack>

      {items.length === 0 ? (
        <Stack spacing={1} sx={{ alignItems: 'center', py: 6, color: 'text.secondary' }}>
          <NotificationsNoneOutlined fontSize="large" />
          <Typography>لا توجد إشعارات</Typography>
        </Stack>
      ) : (
        <Paper variant="outlined">
          <List disablePadding aria-label="قائمة الإشعارات">
            {items.map((item) => (
              <Row key={item.id} item={item} onOpen={(i) => void open(i)} />
            ))}
          </List>
        </Paper>
      )}

      {query.hasNextPage && (
        <Button
          variant="outlined"
          onClick={() => void query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
        >
          عرض الأقدم
        </Button>
      )}
    </Stack>
  );
}
