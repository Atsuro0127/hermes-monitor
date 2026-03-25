import { apiGet } from './api';
import { readCache, writeCache, isCached } from './cache';
import { ArticleResponse, Tweet, EnrichedArticle } from './types';
import { bodyToMarkdown } from './filter';

export interface ArticleFetchResult {
  detail: ArticleResponse | null;
  status: 'fresh' | 'cached' | 'failed';
  limitedAccess?: boolean;
}

export async function fetchArticleDetail(articleId: string): Promise<ArticleFetchResult> {
  const cacheKey = `article:${articleId}`;

  if (isCached(cacheKey)) {
    const cached = readCache<ArticleResponse>(cacheKey);
    return { detail: cached, status: 'cached' };
  }

  try {
    const res = await apiGet<ArticleResponse>(`/twitter/article/${articleId}`);
    writeCache(cacheKey, res);
    return { detail: res, status: 'fresh' };
  } catch (err) {
    const msg = (err as Error).message ?? '';
    const isLimited = msg.includes('403') || msg.toLowerCase().includes('limited access');
    if (!isLimited) {
      console.warn(`  ⚠ article ${articleId}: ${msg}`);
    }
    return { detail: null, status: 'failed', limitedAccess: isLimited };
  }
}

export function buildArticle(tweet: Tweet, articleId: string, lang: 'ja' | 'unknown', result: ArticleFetchResult): EnrichedArticle {
  const views = typeof tweet.views_count === 'string'
    ? parseInt(tweet.views_count, 10)
    : (tweet.views_count ?? 0);

  const stats = {
    likes: tweet.favorite_count ?? 0,
    retweets: tweet.retweet_count ?? 0,
    replies: tweet.reply_count ?? 0,
    quotes: tweet.quote_count ?? 0,
    bookmarks: tweet.bookmark_count ?? 0,
    views,
  };

  const engagementScore = stats.likes + stats.retweets * 2 + stats.quotes + stats.replies;
  const tweetUrl = `https://x.com/${tweet.user.screen_name}/status/${tweet.id_str}`;

  const author = {
    name: tweet.user.name,
    screenName: tweet.user.screen_name,
    bio: tweet.user.description,
    followersCount: tweet.user.followers_count,
  };

  const { detail } = result;

  if (detail) {
    return {
      articleId,
      tweetId: tweet.id_str,
      tweetUrl,
      lang,
      title: detail.title ?? '(no title)',
      body: bodyToMarkdown(detail.body ?? ''),
      preview: detail.preview ?? '',
      thumbnail: detail.thumbnail ?? '',
      author,
      stats,
      engagementScore,
      createdAt: tweet.created_at,
      source: 'api',
    };
  }

  return {
    articleId,
    tweetId: tweet.id_str,
    tweetUrl,
    lang,
    title: tweet.full_text.slice(0, 80).replace(/\n/g, ' '),
    body: tweet.full_text,
    preview: tweet.full_text.slice(0, 280),
    thumbnail: '',
    author,
    stats,
    engagementScore,
    createdAt: tweet.created_at,
    source: 'tweet_only',
  };
}
