/** One card image of a request, fetched through the API (each open is logged, §13). */
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';
import { useEffect, useState } from 'react';

import { requestImageUrl } from '../../../lib/adminRequests';

export function RequestImage({
  imageId,
  alt,
  height = 180,
}: {
  imageId: string;
  alt: string;
  height?: number;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    let made: string | null = null;
    requestImageUrl(imageId)
      .then((u) => {
        made = u;
        if (alive) setUrl(u);
        else URL.revokeObjectURL(u);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [imageId]);

  if (failed)
    return (
      <Box
        sx={{
          height,
          display: 'grid',
          placeItems: 'center',
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          الصورة غير متوفرة
        </Typography>
      </Box>
    );
  if (!url) return <Skeleton variant="rounded" height={height} />;
  return (
    <Box
      component="img"
      src={url}
      alt={alt}
      sx={{ width: '100%', maxHeight: height, objectFit: 'contain', borderRadius: 1 }}
    />
  );
}
