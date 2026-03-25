const BASE_URL = 'https://api.socialdata.tools';
const MAX_RETRIES = 3;

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function apiGet<T>(endpoint: string, params?: Record<string, string>): Promise<T> {
  const apiKey = process.env.SOCIALDATA_API_KEY;
  if (!apiKey) throw new Error('SOCIALDATA_API_KEY is not set in .env');

  const url = new URL(`${BASE_URL}${endpoint}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }

  let lastError: Error = new Error('Unknown error');

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url.toString(), {
        headers: {
          Authorization: `Bearer ${apiKey}`,
          Accept: 'application/json',
        },
      });

      if (res.status === 429) {
        const wait = parseInt(res.headers.get('retry-after') || '60', 10) * 1000;
        console.warn(`\n  ⏳ Rate limited. Waiting ${wait / 1000}s...`);
        await sleep(wait);
        continue; // retry without counting as attempt
      }

      if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }

      return (await res.json()) as T;
    } catch (err) {
      lastError = err as Error;
      if (attempt < MAX_RETRIES - 1) {
        await sleep(1000 * 2 ** attempt);
      }
    }
  }

  throw lastError;
}
