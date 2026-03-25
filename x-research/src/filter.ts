import { Tweet } from './types';

// ひらがな・カタカナ・CJK統合漢字
const JP_REGEX = /[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]/;

export function detectLang(tweet: Tweet): 'ja' | 'unknown' {
  const signals = [tweet.user.name, tweet.user.description, tweet.full_text];
  return signals.some(s => JP_REGEX.test(s ?? '')) ? 'ja' : 'unknown';
}

export function extractArticleId(tweet: { entities?: { urls?: Array<{ expanded_url: string }> } }): string | null {
  for (const u of tweet.entities?.urls ?? []) {
    const m = u.expanded_url.match(/x\.com\/i\/article\/(\d+)/);
    if (m) return m[1];
  }
  return null;
}

export function bodyToMarkdown(body: string): string {
  if (!body) return '';
  // 既にMarkdown風なら基本そのまま返す
  // 連続する改行を段落区切りに
  return body
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
