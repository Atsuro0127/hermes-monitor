"""
collect.py — Playwright ブラウザの認証済みセッションを使って Twitter GraphQL API からツイートを収集
出力形式は既存の EnrichedArticle[] JSON と互換

使い方:
  python collect.py --since 2026-03-01 --until 2026-03-25 --minFaves 10000 --maxTweets 200
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

# ── 定数 ─────────────────────────────────────────────────
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
GQL_ENDPOINT = "https://x.com/i/api/graphql/rkp6b4vtR9u7v3naGoOzUQ/SearchTimeline"
GQL_FEATURES = {
    "rweb_video_screen_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}

# ── 日本語判定 ────────────────────────────────────────────
JP_REGEX = re.compile(r'[\u3040-\u30FF\u4E00-\u9FFF\u3400-\u4DBF]')

def detect_lang(text_fields):
    for text in text_fields:
        if text and JP_REGEX.search(text):
            return 'ja'
    return 'unknown'

# ── GraphQL レスポンスからツイートを抽出 ──────────────────
def extract_tweets(data):
    tweets = []
    try:
        instructions = data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
        for inst in instructions:
            entries = inst.get('entries', [])
            for entry in entries:
                content = entry.get('content', {})
                item_content = content.get('itemContent', {})
                tweet_result = item_content.get('tweet_results', {}).get('result', {})

                # tweetでない場合スキップ
                if tweet_result.get('__typename') not in ('Tweet', 'TweetWithVisibilityResults'):
                    continue

                # TweetWithVisibilityResults の場合は内部の tweet を取得
                if tweet_result.get('__typename') == 'TweetWithVisibilityResults':
                    tweet_result = tweet_result.get('tweet', {})

                tweets.append(tweet_result)
    except (KeyError, TypeError):
        pass
    return tweets

def parse_tweet(tweet_result):
    try:
        core = tweet_result.get('core', {})
        user_results = core.get('user_results', {}).get('result', {})
        legacy_user = user_results.get('legacy', {})
        legacy = tweet_result.get('legacy', {})
        views = tweet_result.get('views', {})

        text = legacy.get('full_text', '')
        username = legacy_user.get('screen_name', '')
        display_name = legacy_user.get('name', '')
        bio = legacy_user.get('description', '')
        followers = legacy_user.get('followers_count', 0)
        tweet_id = legacy.get('id_str', '')

        likes = legacy.get('favorite_count', 0)
        retweets = legacy.get('retweet_count', 0)
        replies = legacy.get('reply_count', 0)
        quotes = legacy.get('quote_count', 0)
        bookmarks = legacy.get('bookmark_count', 0)
        view_count = int(views.get('count', 0) or 0)
        created_at_str = legacy.get('created_at', '')

        # 日時パース
        try:
            created_at = datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            created_at = ''

        lang = detect_lang([display_name, bio, text])
        engagement_score = likes + retweets * 2 + quotes + replies
        title = text.split('\n')[0][:80] if text else ''
        tweet_url = f'https://x.com/{username}/status/{tweet_id}'

        return {
            'articleId': tweet_id,
            'tweetId': tweet_id,
            'tweetUrl': tweet_url,
            'lang': lang,
            'title': title,
            'body': text,
            'preview': text[:140],
            'thumbnail': '',
            'author': {
                'name': display_name,
                'screenName': username,
                'bio': bio,
                'followersCount': followers,
            },
            'stats': {
                'likes': likes,
                'retweets': retweets,
                'replies': replies,
                'quotes': quotes,
                'bookmarks': bookmarks,
                'views': view_count,
            },
            'engagementScore': engagement_score,
            'createdAt': created_at,
            'source': 'tweet_only',
        }
    except Exception:
        return None

def get_cursor(data):
    try:
        instructions = data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
        for inst in instructions:
            entries = inst.get('entries', [])
            for entry in entries:
                if entry.get('entryId', '').startswith('cursor-bottom'):
                    return entry['content']['value']
    except (KeyError, TypeError):
        pass
    return None

# ── メイン ────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--since',     required=True)
    parser.add_argument('--until',     required=True)
    parser.add_argument('--minFaves',  type=int, default=10000)
    parser.add_argument('--maxTweets', type=int, default=500)
    parser.add_argument('--lang',      default='ja')
    args = parser.parse_args()

    raw_query = f'min_faves:{args.minFaves} -filter:replies since:{args.since} until:{args.until}'
    if args.lang == 'ja':
        raw_query += ' lang:ja'

    print(f'\nQuery: {raw_query}')
    print(f'Max tweets: {args.maxTweets}')

    # Playwright でブラウザに接続（既存プロファイルを使用）
    user_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\ms-playwright\mcp-chrome-profile')

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )
        page = await context.new_page()
        await page.goto('https://x.com', wait_until='domcontentloaded')

        # ct0 取得
        cookies = await context.cookies()
        ct0 = next((c['value'] for c in cookies if c['name'] == 'ct0'), '')
        auth_token = next((c['value'] for c in cookies if c['name'] == 'auth_token'), '')

        if not auth_token:
            print('Error: auth_token が取得できませんでした。ブラウザでX/Twitterにログインしてください。', file=sys.stderr)
            await context.close()
            sys.exit(1)

        print(f'  auth_token: 取得済み (ct0: {ct0[:20]}...)')

        articles = []
        cursor = None
        page_num = 0

        while len(articles) < args.maxTweets:
            page_num += 1
            variables = {
                'rawQuery': raw_query,
                'count': 20,
                'querySource': 'typed_query',
                'product': 'Latest',
            }
            if cursor:
                variables['cursor'] = cursor

            url = (
                f"{GQL_ENDPOINT}"
                f"?variables={json.dumps(variables, separators=(',', ':'))}"
                f"&features={json.dumps(GQL_FEATURES, separators=(',', ':'))}"
            )

            # JavaScript の fetch でブラウザの認証済みセッションを利用
            data = await page.evaluate(f"""
                async () => {{
                    const res = await fetch({json.dumps(url)}, {{
                        headers: {{
                            'authorization': 'Bearer {BEARER}',
                            'x-csrf-token': {json.dumps(ct0)},
                            'x-twitter-active-user': 'yes',
                            'x-twitter-auth-type': 'OAuth2Session',
                            'x-twitter-client-language': 'ja',
                            'content-type': 'application/json',
                        }},
                        credentials: 'include',
                    }});
                    if (!res.ok) return {{error: res.status, text: await res.text()}};
                    return await res.json();
                }}
            """)

            if 'error' in data:
                print(f'\nAPI error {data["error"]}: {data.get("text", "")[:200]}')
                break

            tweet_results = extract_tweets(data)
            if not tweet_results:
                print(f'\n  ページ {page_num}: ツイートなし（終了）')
                break

            for tr in tweet_results:
                if len(articles) >= args.maxTweets:
                    break
                parsed = parse_tweet(tr)
                if parsed:
                    articles.append(parsed)

            cursor = get_cursor(data)
            print(f'  ページ {page_num}: +{len(tweet_results)} tweets (合計: {len(articles)})', end='\r')

            if not cursor:
                print(f'\n  カーソルなし（終了）')
                break

            await asyncio.sleep(0.5)

        await context.close()

    print(f'\n  収集完了: {len(articles)} 件')

    # ソート
    articles.sort(key=lambda a: a['engagementScore'], reverse=True)

    # 保存
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    out = output_dir / f'report-{ts}.json'
    out.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding='utf-8')

    ja_count = sum(1 for a in articles if a['lang'] == 'ja')
    unknown_count = sum(1 for a in articles if a['lang'] == 'unknown')
    print(f'  ja: {ja_count}, unknown: {unknown_count}')
    print(f'  {out}')
    print('\nDone! 次は npm run analyze を実行してください。')

if __name__ == '__main__':
    asyncio.run(main())
