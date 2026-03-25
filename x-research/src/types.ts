export interface TweetUser {
  id_str: string;
  name: string;
  screen_name: string;
  description: string;
  followers_count: number;
  verified: boolean;
}

export interface TweetUrl {
  url: string;
  expanded_url: string;
  display_url: string;
}

export interface Tweet {
  id_str: string;
  full_text: string;
  user: TweetUser;
  favorite_count: number;
  retweet_count: number;
  reply_count: number;
  quote_count: number;
  bookmark_count?: number;
  views_count?: number | string;
  created_at: string;
  entities?: { urls?: TweetUrl[] };
}

export interface SearchResponse {
  tweets: Tweet[];
  next_cursor?: string;
}

// 記事詳細APIのレスポンス（本文はAPIから取得、検索結果には含まれない前提）
export interface ArticleResponse {
  id?: string;
  title?: string;
  body?: string;
  preview?: string;
  thumbnail?: string;
}

// 検索クエリの組み立てオプション
export interface QueryOptions {
  mode?: 'article' | 'tweet';
  minFaves?: number;
  minRetweets?: number;
  since: string;
  until: string;
  includeReplies?: boolean;
}

export interface EnrichedArticle {
  articleId: string;
  tweetId: string;
  tweetUrl: string;
  lang: 'ja' | 'unknown';
  title: string;
  body: string;
  preview: string;
  thumbnail: string;
  author: {
    name: string;
    screenName: string;
    bio: string;
    followersCount: number;
  };
  stats: {
    likes: number;
    retweets: number;
    replies: number;
    quotes: number;
    bookmarks: number;
    views: number;
  };
  engagementScore: number;
  createdAt: string;
  source: 'api' | 'tweet_only';
}

export interface RunStats {
  searchTweetsTotal: number;
  searchRequestCount: number;
  articleFetchFresh: number;
  articleFetchCached: number;
  articleFetchFailed: number;
  limitedAccessHit: boolean;
}

export interface CliOptions {
  mode: 'article' | 'tweet';
  minFaves: number;
  minRetweets?: number;
  since: string;
  until: string;
  lang: string;
  includeReplies: boolean;
}
