import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  compressImage,
  fitWithin,
  ImageDecodeError,
  JPEG_QUALITY,
  MAX_EDGE,
} from '../lib/imageCompress';

describe('fitWithin', () => {
  it('scales a landscape photo to 1600 on the longest edge', () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 1600, height: 1200 });
  });

  it('scales a portrait photo by its height', () => {
    expect(fitWithin(3024, 4032)).toEqual({ width: 1200, height: 1600 });
  });

  it('keeps an image that already fits and never upscales', () => {
    expect(fitWithin(1200, 1600)).toEqual({ width: 1200, height: 1600 });
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
  });

  it('uses 1600 and 0.8 as the owner asked', () => {
    expect(MAX_EDGE).toBe(1600);
    expect(JPEG_QUALITY).toBe(0.8);
  });
});

describe('compressImage', () => {
  const drawImage = vi.fn();
  let toBlobArgs: unknown[] = [];
  const canvas = {
    width: 0,
    height: 0,
    getContext: () => ({ drawImage }),
    toBlob: (cb: (b: Blob | null) => void, ...args: unknown[]) => {
      toBlobArgs = args;
      cb(new Blob(['jpeg'], { type: 'image/jpeg' }));
    },
  };

  function mockCanvas() {
    const real = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string) =>
      tag === 'canvas'
        ? (canvas as unknown as HTMLCanvasElement)
        : real(tag)) as typeof document.createElement);
  }

  // jsdom has no HTMLImageElement.decode; give the fallback path one to mock.
  function stubDecode(impl: () => Promise<void>) {
    const fn = vi.fn(impl);
    Object.defineProperty(HTMLImageElement.prototype, 'decode', {
      configurable: true,
      writable: true,
      value: fn,
    });
    return fn;
  }

  afterEach(() => {
    delete (HTMLImageElement.prototype as Partial<HTMLImageElement>).decode;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    drawImage.mockReset();
  });

  it('decodes with EXIF orientation and encodes JPEG 0.8 at most 1600px', async () => {
    const close = vi.fn();
    const createImageBitmap = vi.fn().mockResolvedValue({ width: 4000, height: 3000, close });
    vi.stubGlobal('createImageBitmap', createImageBitmap);
    mockCanvas();

    const out = await compressImage(new Blob(['raw']));

    expect(createImageBitmap).toHaveBeenCalledWith(expect.any(Blob), {
      imageOrientation: 'from-image',
    });
    expect(canvas.width).toBe(1600);
    expect(canvas.height).toBe(1200);
    expect(drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, 1600, 1200);
    expect(toBlobArgs).toEqual(['image/jpeg', 0.8]);
    expect(out.type).toBe('image/jpeg');
    expect(close).toHaveBeenCalled();
  });

  it('falls back to an <img> when createImageBitmap fails', async () => {
    vi.stubGlobal('createImageBitmap', vi.fn().mockRejectedValue(new Error('unsupported')));
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: vi.fn() });
    const decode = stubDecode(() => Promise.resolve());
    vi.spyOn(HTMLImageElement.prototype, 'naturalWidth', 'get').mockReturnValue(800);
    vi.spyOn(HTMLImageElement.prototype, 'naturalHeight', 'get').mockReturnValue(600);
    mockCanvas();

    await compressImage(new Blob(['raw']));

    expect(decode).toHaveBeenCalled();
    expect(canvas.width).toBe(800); // never upscaled
    expect(canvas.height).toBe(600);
  });

  it('reports an unreadable file with an Arabic message', async () => {
    vi.stubGlobal('createImageBitmap', vi.fn().mockRejectedValue(new Error('bad')));
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: vi.fn() });
    stubDecode(() => Promise.reject(new Error('bad')));

    await expect(compressImage(new Blob(['x']))).rejects.toBeInstanceOf(ImageDecodeError);
    await expect(compressImage(new Blob(['x']))).rejects.toThrow('تعذّر قراءة الصورة');
  });
});
