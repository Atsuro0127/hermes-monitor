import { apiGet } from './api';
import { readCache, writeCache } from './cache';
import { Tweet, SearchResponse, QueryOptions } from './types';

export function buildQuery(opts: QueryOptions): string {
  const parts = [
    ...(opts.mode !== 'tweet' ? ['url:x.com/i/article'] : []),
    ...(opts.minFaves    ? [`min_faves:${opts.minFaves}`]        : []),
    ...(opts.minRetweets ? [`min_retweets:${opts.minRetweets}`]  : []),
    ...(opts.includeReplies ? [] : ['-filter:replies']),
    `since:${opts.since}`,
    `until:${opts.until}`,
  ];
  return parts.join(' ');
}

export interface SearchResult {
  tweets: Tweet[];
  requestCount: number;
}

export async function searchArticleTweets(query: string, maxTweets = 0): Promise<SearchResult> {
  const cacheKey = `search:${query}${maxTweets ? `:max${maxTweets}` : ''}`;
  const cached = readCache<Tweet[]>(cacheKey);
  if (cached) {
    console.log('  (loaded from cache)');
    return { tweets: cached, requestCount: 0 };
  }

  const allTweets: Tweet[] = [];
  let cursor: string | undefined;
  let page = 0;

  while (true) {
    const params: Record<string, string> = { query, type: 'Latest' };
    if (cursor) params.cursor = cursor;

    process.stdout.write(`  Page ${++page}... `);
    const res = await apiGet<SearchResponse>('/twitter/search', params);

    const tweets = res.tweets ?? [];
    allTweets.push(...tweets);
    process.stdout.write(`${tweets.length} tweets (total: ${allTweets.length})\n`);

    if (allTweets.length > 0 && allTweets.length % 500 === 0) {
      console.log(`  ⏳ ${allTweets.length} tweets fetched so far...`);
    }

    if (!res.next_cursor || tweets.length === 0) break;
    if (maxTweets > 0 && allTweets.length >= maxTweets) {
      console.log(`  🛑 --maxTweets ${maxTweets} に達したので停止`);
      break;
    }
    cursor = res.next_cursor;
  }

  writeCache(cacheKey, allTweets);
  return { tweets: allTweets, requestCount: page };
}
