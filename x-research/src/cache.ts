import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

const CACHE_DIR = path.join(process.cwd(), 'cache');
const OUTPUT_DIR = path.join(process.cwd(), 'output');

export function ensureDirs(): void {
  [CACHE_DIR, OUTPUT_DIR].forEach(d => {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  });
}

function cacheFile(key: string): string {
  const hash = crypto.createHash('md5').update(key).digest('hex');
  return path.join(CACHE_DIR, `${hash}.json`);
}

export function readCache<T>(key: string): T | null {
  const file = cacheFile(key);
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8')) as T;
  } catch {
    return null;
  }
}

export function writeCache<T>(key: string, data: T): void {
  fs.writeFileSync(cacheFile(key), JSON.stringify(data, null, 2));
}

export function isCached(key: string): boolean {
  return fs.existsSync(cacheFile(key));
}
