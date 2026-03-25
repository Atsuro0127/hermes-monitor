import { parseArgs } from 'util';
import dotenv from 'dotenv';
import { buildQuery, searchArticleTweets } from './search';
import { fetchArticleDetail, buildArticle } from './article';
import { detectLang, extractArticleId } from './filter';
import { saveResults } from './report';
import { ensureDirs } from './cache';
import { EnrichedArticle, RunStats, Tweet } from './types';

dotenv.config();

const CONCURRENCY = parseInt(process.env.CONCURRENCY ?? '3', 10);

async function withConcurrency<T, R>(
  items: T[],
  fn: (item: T, index: number) => Promise<R>,
  limit: number
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;

  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }

  const workers = Array.from({ length: Math.min(limit, items.length) }, worker);
  await Promise.all(workers);
  return results;
}

async function main() {
  const { values } = parseArgs({
    args: process.argv.slice(2),
    options: {
      mode:          { type: 'string', default: 'article' },
      minFaves:      { type: 'string', default: '1000' },
      minRetweets:   { type: 'string' },
      since:         { type: 'string', default: '' },
      until:         { type: 'string', default: '' },
      lang:          { type: 'string', default: 'ja' },
      includeReplies:{ type: 'boolean', default: false },
      maxTweets:     { type: 'string', default: '200' },
    },
  });

  const rawMode = values.mode as string;
  if (rawMode !== 'article' && rawMode !== 'tweet') {
    console.error('Error: --mode must be "article" or "tweet"');
    process.exit(1);
  }

  const opts = {
    mode:           rawMode as 'article' | 'tweet',
    minFaves:       parseInt(values.minFaves as string, 10),
    minRetweets:    values.minRetweets ? parseInt(values.minRetweets as string, 10) : undefined,
    since:          values.since as string,
    until:          values.until as string,
    lang:           values.lang as string,
    includeReplies: values.includeReplies as boolean,
    maxTweets:      parseInt(values.maxTweets as string, 10),
  };

  if (!opts.since || !opts.until) {
    console.error('Error: --since and --until are required');
    process.exit(1);
  }

  ensureDirs();

  // ── 1. 検索 ───────────────────────────────────────────
  const query = buildQuery({
    mode:           opts.mode,
    minFaves:       opts.minFaves,
    minRetweets:    opts.minRetweets,
    since:          opts.since,
    until:          opts.until,
    includeReplies: opts.includeReplies,
  });

  console.log(`\n🔍 Query: ${query}`);
  const { tweets, requestCount } = await searchArticleTweets(query, opts.maxTweets);
  console.log(`  Total tweets: ${tweets.length}`);

  const runStats: RunStats = {
    searchTweetsTotal: tweets.length,
    searchRequestCount: requestCount,
    articleFetchFresh: 0,
    articleFetchCached: 0,
    articleFetchFailed: 0,
    limitedAccessHit: false,
  };

  // ── 2. 言語判定 ───────────────────────────────────────
  const jaTweets: Tweet[] = [];
  const unknownTweets: Tweet[] = [];

  for (const t of tweets) {
    if (opts.lang === 'ja') {
      if (detectLang(t) === 'ja') {
        jaTweets.push(t);
      } else {
        unknownTweets.push(t);
      }
    } else {
      jaTweets.push(t);
    }
  }

  if (opts.lang === 'ja') {
    console.log(`  Japanese: ${jaTweets.length}, Unknown: ${unknownTweets.length}`);
  }

  // ── 3 & 4. モード別に記事取得 or ツイート直接利用 ───
  let allArticles: EnrichedArticle[];

  if (opts.mode === 'tweet') {
    // 通常ツイートモード: 記事APIは呼ばず tweet_only で直接生成
    const allTweetEntries: [Tweet, 'ja' | 'unknown'][] = [
      ...jaTweets.map(t => [t, 'ja' as const] as [Tweet, 'ja' | 'unknown']),
      ...unknownTweets.map(t => [t, 'unknown' as const] as [Tweet, 'ja' | 'unknown']),
    ];
    allArticles = allTweetEntries.map(([tweet, lang]) =>
      buildArticle(tweet, tweet.id_str, lang, { detail: null, status: 'failed' })
    );
  } else {
    // 記事モード: 記事IDを抽出して詳細取得
    function dedup(tweetList: Tweet[]): [string, Tweet][] {
      const map = new Map<string, Tweet>();
      for (const tweet of tweetList) {
        const id = extractArticleId(tweet);
        if (id && !map.has(id)) {
          map.set(id, tweet);
        }
      }
      return Array.from(map.entries());
    }

    const jaEntries = dedup(jaTweets);
    const unknownEntries = dedup(unknownTweets);
    console.log(`  Unique article IDs — ja: ${jaEntries.length}, unknown: ${unknownEntries.length}`);

    const allEntries: [string, Tweet, 'ja' | 'unknown'][] = [
      ...jaEntries.map(([id, t]) => [id, t, 'ja' as const] as [string, Tweet, 'ja' | 'unknown']),
      ...unknownEntries.map(([id, t]) => [id, t, 'unknown' as const] as [string, Tweet, 'ja' | 'unknown']),
    ];

    console.log(`\n📄 Fetching article details (concurrency=${CONCURRENCY})...`);
    let done = 0;
    allArticles = await withConcurrency(
      allEntries,
      async ([articleId, tweet, lang]) => {
        const fetchResult = await fetchArticleDetail(articleId);
        if (fetchResult.status === 'fresh') runStats.articleFetchFresh++;
        else if (fetchResult.status === 'cached') runStats.articleFetchCached++;
        else {
          runStats.articleFetchFailed++;
          if (fetchResult.limitedAccess) runStats.limitedAccessHit = true;
        }
        process.stdout.write(`  [${++done}/${allEntries.length}]\r`);
        return buildArticle(tweet, articleId, lang, fetchResult);
      },
      CONCURRENCY
    );
    process.stdout.write('\n');

    if (runStats.limitedAccessHit) {
      console.warn('\n  ⚠️  Article endpoint returned 403 (Limited Access).');
      console.warn('     記事本文の取得には上位プランの SocialData API キーが必要です。');
      console.warn('     ツイートテキストで代替しています。\n');
    }
  }

  // ── 5. タイトル+著者で重複除去・ソート ──────────────
  function dedupAndSort(articles: EnrichedArticle[]): EnrichedArticle[] {
    const seen = new Set<string>();
    const unique: EnrichedArticle[] = [];
    for (const a of articles) {
      const key = `${a.title}::${a.author.screenName}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(a);
      }
    }
    unique.sort((a, b) => b.engagementScore - a.engagementScore);
    return unique;
  }

  const jaFinal = dedupAndSort(allArticles.filter(a => a.lang === 'ja'));
  const unknownFinal = dedupAndSort(allArticles.filter(a => a.lang === 'unknown'));

  console.log(`  Unique articles — ja: ${jaFinal.length}, unknown: ${unknownFinal.length}`);
  console.log(`  Fetch stats — fresh: ${runStats.articleFetchFresh}, cached: ${runStats.articleFetchCached}, failed: ${runStats.articleFetchFailed}`);

  // ── 6. 保存 ────────────────────────────────────────────
  saveResults(jaFinal, unknownFinal, opts, runStats);
  console.log('\n✅ Done!');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
