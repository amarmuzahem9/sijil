import { inflateRawSync } from 'node:zlib';

/**
 * A small ZIP reader for the export tests (specs/019 T045): enough for the files Sijil writes
 * (stored or deflated entries, ZIP64 sizes in the central directory), so the e2e image needs no
 * extra library. Not a general-purpose ZIP parser.
 */
export function readZip(data: Buffer): Map<string, Buffer> {
  let eocd = -1;
  for (let i = data.length - 22; i >= Math.max(0, data.length - 65_557); i--) {
    if (data.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error('not a zip file');
  const entries = data.readUInt16LE(eocd + 10);
  let offset = data.readUInt32LE(eocd + 16);
  const files = new Map<string, Buffer>();
  for (let n = 0; n < entries; n++) {
    if (data.readUInt32LE(offset) !== 0x02014b50) throw new Error('bad central directory');
    const method = data.readUInt16LE(offset + 10);
    let compressed = data.readUInt32LE(offset + 20);
    let size = data.readUInt32LE(offset + 24);
    const nameLength = data.readUInt16LE(offset + 28);
    const extraLength = data.readUInt16LE(offset + 30);
    const commentLength = data.readUInt16LE(offset + 32);
    let local = data.readUInt32LE(offset + 42);
    const name = data.toString('utf8', offset + 46, offset + 46 + nameLength);
    // ZIP64: the real values follow, in this order, for each field that reads 0xFFFFFFFF.
    let extra = offset + 46 + nameLength;
    const extraEnd = extra + extraLength;
    while (extra + 4 <= extraEnd) {
      const id = data.readUInt16LE(extra);
      const length = data.readUInt16LE(extra + 2);
      if (id === 0x0001) {
        let at = extra + 4;
        if (size === 0xffffffff) {
          size = Number(data.readBigUInt64LE(at));
          at += 8;
        }
        if (compressed === 0xffffffff) {
          compressed = Number(data.readBigUInt64LE(at));
          at += 8;
        }
        if (local === 0xffffffff) local = Number(data.readBigUInt64LE(at));
      }
      extra += 4 + length;
    }
    const start = local + 30 + data.readUInt16LE(local + 26) + data.readUInt16LE(local + 28);
    const raw = data.subarray(start, start + compressed);
    files.set(name, method === 8 ? inflateRawSync(raw) : Buffer.from(raw));
    if (files.get(name)!.length !== size) throw new Error(`bad size for ${name}`);
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return files;
}

const ENTITIES: Record<string, string> = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&apos;': "'",
};

/** Every text of an .xlsx (shared and inline strings), and every link target of its sheets. */
export function readXlsx(data: Buffer): {
  texts: string[];
  links: string[];
  formulas: number;
} {
  const files = readZip(data);
  const texts: string[] = [];
  const links: string[] = [];
  let formulas = 0;
  for (const [name, body] of files) {
    const xml = body.toString('utf8');
    if (name === 'xl/sharedStrings.xml' || /^xl\/worksheets\/sheet\d+\.xml$/.test(name)) {
      for (const match of xml.matchAll(/<t(?:\s[^>]*)?>([^<]*)<\/t>/g)) {
        texts.push(match[1].replace(/&(amp|lt|gt|quot|apos);/g, (e) => ENTITIES[e]));
      }
      formulas += (xml.match(/<f[\s>]/g) ?? []).length;
    }
    if (/^xl\/worksheets\/_rels\/sheet\d+\.xml\.rels$/.test(name)) {
      for (const match of xml.matchAll(/Target="([^"]+)"/g)) links.push(match[1]);
    }
  }
  return { texts, links, formulas };
}
