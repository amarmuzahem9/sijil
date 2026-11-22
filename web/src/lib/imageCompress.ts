/**
 * Card-image compression on the device before upload (specs/005 research.md R5, Principle V):
 * longest edge at most 1600px, JPEG quality 0.8, EXIF orientation applied.
 *
 * Re-encoding through a canvas also strips every EXIF tag (GPS position, device model), and
 * turns iPhone HEIC photos (decoded natively by Safari) into JPEG.
 */
export const MAX_EDGE = 1600;
export const JPEG_QUALITY = 0.8;

/** Scale (w, h) down so the longest edge is at most `max`; never upscales. */
export function fitWithin(width: number, height: number, max = MAX_EDGE) {
  const longest = Math.max(width, height);
  if (longest <= max) return { width, height };
  const scale = max / longest;
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

type Decoded = { source: CanvasImageSource; width: number; height: number; close: () => void };

async function decode(file: Blob): Promise<Decoded> {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    return {
      source: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      close: () => bitmap.close(),
    };
  } catch {
    // Older Safari: an <img> applies EXIF orientation by default in current browsers.
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.decoding = 'async';
      img.src = url;
      await img.decode();
      return {
        source: img,
        width: img.naturalWidth,
        height: img.naturalHeight,
        close: () => undefined,
      };
    } finally {
      URL.revokeObjectURL(url);
    }
  }
}

export class ImageDecodeError extends Error {
  constructor() {
    super('تعذّر قراءة الصورة، اختر صورة أخرى');
  }
}

/** Compress a photo from the camera or the gallery into the JPEG that is uploaded. */
export async function compressImage(file: Blob): Promise<Blob> {
  let decoded: Decoded;
  try {
    decoded = await decode(file);
  } catch {
    throw new ImageDecodeError();
  }
  try {
    const { width, height } = fitWithin(decoded.width, decoded.height);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new ImageDecodeError();
    ctx.drawImage(decoded.source, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY),
    );
    if (!blob) throw new ImageDecodeError();
    return blob;
  } finally {
    decoded.close();
  }
}
