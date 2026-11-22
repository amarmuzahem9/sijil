/**
 * One card side (specs/005 US2, research.md R5, R6).
 *
 * Two separate buttons, «تصوير» and «من المعرض», each with its own hidden input. Only «تصوير»
 * has `capture="environment"`: on Android a single input with `capture` opens the camera and
 * hides the gallery (owner requirement).
 *
 * The photo is compressed on the device, uploaded with a progress bar, and kept in memory until
 * the upload succeeds so «إعادة المحاولة» resends the same bytes.
 */
import CloudUploadOutlined from '@mui/icons-material/CloudUploadOutlined';
import PhotoCameraOutlined from '@mui/icons-material/PhotoCameraOutlined';
import PhotoLibraryOutlined from '@mui/icons-material/PhotoLibraryOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';

import { ApiError, NETWORK_ERROR_MESSAGE } from '../../../lib/api';
import {
  fetchImageObjectUrl,
  uploadDraftImage,
  type Draft,
  type DraftImage,
  type Side,
} from '../../../lib/drafts';
import { compressImage, ImageDecodeError } from '../../../lib/imageCompress';

type Phase =
  | { kind: 'idle' }
  | { kind: 'compressing' }
  | { kind: 'uploading'; progress: number }
  | { kind: 'failed'; message: string; retryable: boolean };

export const UNFINISHED_UPLOAD = 'يوجد رفع غير مكتمل';

/** Thumbnail URL: the local preview, else the server image fetched once per image id (every
 * server read is an audited image access, so autosaves must not refetch it). */
function useObjectUrl(image: DraftImage | null, local: string | null): string | null {
  const [fetched, setFetched] = useState<{ id: string; url: string } | null>(null);
  const imageId = image?.id ?? null;
  useEffect(() => {
    if (local || !imageId) return;
    let cancelled = false;
    let created: string | null = null;
    fetchImageObjectUrl(imageId)
      .then((url) => {
        if (cancelled) URL.revokeObjectURL(url);
        else {
          created = url;
          setFetched({ id: imageId, url });
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [imageId, local]);
  if (local) return local;
  return fetched && fetched.id === imageId ? fetched.url : null;
}

export function ImageSlot({
  side,
  label,
  image,
  ensureCreated,
  onUploaded,
}: {
  side: Side;
  label: string;
  image: DraftImage | null;
  ensureCreated: () => Promise<string>;
  onUploaded: (draft: Draft) => void;
}) {
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });
  const [changing, setChanging] = useState(false);
  // Preview of the image just uploaded from this page (no extra server read).
  const [localUrl, setLocalUrl] = useState<string | null>(null);
  const pendingBlob = useRef<Blob | null>(null);
  const thumbnail = useObjectUrl(image, localUrl);
  const busy = phase.kind === 'compressing' || phase.kind === 'uploading';

  useEffect(() => () => void (localUrl && URL.revokeObjectURL(localUrl)), [localUrl]);

  // Warn before leaving while an upload is running (edge case in spec).
  useEffect(() => {
    if (!busy) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = UNFINISHED_UPLOAD;
      return UNFINISHED_UPLOAD;
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [busy]);

  async function upload(blob: Blob) {
    setPhase({ kind: 'uploading', progress: 0 });
    try {
      const id = await ensureCreated();
      const draft = await uploadDraftImage(id, side, blob, (progress) =>
        setPhase({ kind: 'uploading', progress }),
      );
      pendingBlob.current = null;
      setLocalUrl(URL.createObjectURL(blob));
      setChanging(false);
      setPhase({ kind: 'idle' });
      onUploaded(draft);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      // Refused files (type, size, dimensions) cannot be fixed by retrying the same bytes.
      const retryable = !apiErr || apiErr.status === 0 || apiErr.status >= 500;
      if (!retryable) pendingBlob.current = null;
      setPhase({
        kind: 'failed',
        message: apiErr?.message || NETWORK_ERROR_MESSAGE,
        retryable,
      });
    }
  }

  async function onPick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // picking the same file again must fire `change`
    if (!file) return;
    setPhase({ kind: 'compressing' });
    let blob: Blob;
    try {
      blob = await compressImage(file);
    } catch (err) {
      setPhase({
        kind: 'failed',
        message: err instanceof ImageDecodeError ? err.message : 'تعذّر قراءة الصورة',
        retryable: false,
      });
      return;
    }
    pendingBlob.current = blob;
    await upload(blob);
  }

  const showPickers = !thumbnail || changing;

  return (
    <Box data-testid={`image-slot-${side}`}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        {label}
      </Typography>

      {thumbnail && (
        <Box
          component="img"
          src={thumbnail}
          alt={label}
          data-testid={`image-${side}-thumbnail`}
          sx={{
            display: 'block',
            width: '100%',
            maxHeight: 240,
            objectFit: 'contain',
            borderRadius: 1,
            bgcolor: 'action.hover',
            mb: 1,
          }}
        />
      )}

      {thumbnail && !changing && !busy && (
        <Button size="small" onClick={() => setChanging(true)}>
          تغيير
        </Button>
      )}

      {showPickers && (
        <Stack direction="row" spacing={1}>
          <Button
            component="label"
            variant="outlined"
            startIcon={<PhotoCameraOutlined />}
            disabled={busy}
            sx={{ flex: 1 }}
          >
            تصوير
            <input
              hidden
              type="file"
              accept="image/*"
              capture="environment"
              data-testid={`image-${side}-camera`}
              onChange={onPick}
            />
          </Button>
          <Button
            component="label"
            variant="outlined"
            startIcon={<PhotoLibraryOutlined />}
            disabled={busy}
            sx={{ flex: 1 }}
          >
            من المعرض
            <input
              hidden
              type="file"
              accept="image/*"
              data-testid={`image-${side}-gallery`}
              onChange={onPick}
            />
          </Button>
        </Stack>
      )}

      {phase.kind === 'compressing' && (
        <Box sx={{ mt: 1 }}>
          <LinearProgress />
          <Typography variant="caption">جارٍ تجهيز الصورة…</Typography>
        </Box>
      )}
      {phase.kind === 'uploading' && (
        <Box sx={{ mt: 1 }} data-testid={`image-${side}-progress`}>
          <LinearProgress variant="determinate" value={Math.round(phase.progress * 100)} />
          <Typography variant="caption">جارٍ الرفع… {Math.round(phase.progress * 100)}%</Typography>
        </Box>
      )}
      {phase.kind === 'failed' && (
        <Alert
          severity="error"
          sx={{ mt: 1 }}
          action={
            phase.retryable ? (
              <Button
                color="inherit"
                size="small"
                startIcon={<CloudUploadOutlined />}
                onClick={() => pendingBlob.current && void upload(pendingBlob.current)}
              >
                إعادة المحاولة
              </Button>
            ) : undefined
          }
        >
          {phase.retryable ? `فشل الرفع: ${phase.message}` : phase.message}
        </Alert>
      )}
    </Box>
  );
}
