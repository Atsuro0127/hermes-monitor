"""
AI投稿生成スクリプト。
1. 自分の過去投稿＋エンゲージメントを取得
2. コンサル・キャリア系のバズ投稿を調査
3. Claudeで新投稿を5件生成 → pending_review.txt に保存

実行後、pending_review.txt を確認・編集してから approve.py を実行してください。
"""
import json
import os
import sys
import io
import tweepy
import anthropic
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

os.chdir(Path(__file__).parent)
load_dotenv()

HISTORY_FILE = "posted_history.json"
PENDING_FILE = "pending_review.txt"
GENERATE_COUNT = 15  # 生成する投稿数
REFERENCE_ACCOUNTS = [
    "bcg_acn",         # コンサル現場観察・本質暴露
    "narisumashi100",  # 一次情報・泥臭い現場体験
    "nmmg091",         # コンサル転職・実務
]
X_RESEARCH_OUTPUT = Path(__file__).parent / "x-research" / "output"


def get_x_client():
    return tweepy.Client(
        bearer_token=os.getenv("X_BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        wait_on_rate_limit=True,
    )


def get_my_tweets():
    """自分の過去投稿とエンゲージメント指標を取得"""
    client = get_x_client()
    try:
        me = client.get_me()
        user_id = me.data.id

        tweets = client.get_users_tweets(
            id=user_id,
            max_results=100,
            tweet_fields=["public_metrics", "created_at"],
            exclude=["retweets", "replies"],
        )

        if not tweets.data:
            print("  → 投稿がまだありません。履歴ファイルから読み込みます。")
            return get_my_tweets_from_history()

        results = []
        for t in tweets.data:
            m = t.public_metrics
            results.append({
                "text": t.text,
                "likes": m["like_count"],
                "retweets": m["retweet_count"],
                "replies": m["reply_count"],
                "impressions": m.get("impression_count", 0),
                "engagement_score": m["like_count"] + m["retweet_count"] * 3 + m["reply_count"] * 2,
            })
        results.sort(key=lambda x: x["engagement_score"], reverse=True)
        return results

    except tweepy.errors.TweepyException as e:
        print(f"  ⚠️  X API エラー: {e}。履歴ファイルから読み込みます。")
        return get_my_tweets_from_history()


def get_my_tweets_from_history():
    """posted_history.json から投稿履歴を読み込む（X APIが使えない場合のフォールバック）"""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    return [{"text": h["text"], "likes": 0, "retweets": 0, "replies": 0,
             "impressions": 0, "engagement_score": 0} for h in history]


def get_reference_account_posts():
    """x-research/output の最新 report-*.json から参考アカウントの投稿を取得"""
    if not X_RESEARCH_OUTPUT.exists():
        return []
    files = sorted(
        [f for f in X_RESEARCH_OUTPUT.iterdir()
         if f.name.startswith("report-") and f.suffix == ".json"],
        reverse=True,
    )
    posts_by_account = {acct: [] for acct in REFERENCE_ACCOUNTS}
    seen = set()
    for f in files:
        try:
            articles = json.loads(f.read_text(encoding="utf-8"))
            for a in articles:
                screen_name = a.get("author", {}).get("screenName")
                if screen_name in posts_by_account:
                    text = a.get("body", "")
                    if text and text not in seen:
                        seen.add(text)
                        posts_by_account[screen_name].append({
                            "account": screen_name,
                            "text": text,
                            "likes": a.get("stats", {}).get("likes", 0),
                            "engagementScore": a.get("engagementScore", 0),
                        })
        except Exception:
            continue
    # 各アカウントのtop2を取得してまとめる
    result = []
    for acct, posts in posts_by_account.items():
        posts.sort(key=lambda x: x["engagementScore"], reverse=True)
        result.extend(posts[:2])
    return result


def get_trending_posts():
    """コンサル・キャリア系のバズ投稿をX APIで検索"""
    client = get_x_client()
    keywords = [
        "コンサル 転職 -is:retweet lang:ja",
        "キャリア スキル -is:retweet lang:ja",
        "仕事 思考法 -is:retweet lang:ja",
    ]
    trending = []
    for query in keywords:
        try:
            result = client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["public_metrics"],
            )
            if result.data:
                for t in result.data:
                    m = t.public_metrics
                    trending.append({
                        "text": t.text,
                        "likes": m["like_count"],
                        "retweets": m["retweet_count"],
                    })
        except tweepy.errors.TweepyException as e:
            print(f"  ⚠️  検索エラー ({query[:20]}...): {e}")

    trending.sort(key=lambda x: x["likes"] + x["retweets"] * 3, reverse=True)
    return trending[:15]


def generate_with_claude(my_tweets, trending_posts, count, reference_posts=None):
    """Claude APIで新投稿を生成"""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # 成果上位の投稿
    top_mine = my_tweets[:5] if my_tweets else []
    # エンゲージメント低い投稿（反省材料）
    bottom_mine = my_tweets[-3:] if len(my_tweets) >= 6 else []

    ref_section = ""
    if reference_posts:
        ref_section = f"""
## 参考アカウント（{", ".join("@" + a for a in REFERENCE_ACCOUNTS)}）の高エンゲージメント投稿
これらはコンサル系で高エンゲージメントのアカウント。以下の観点で参考にすること：

【文体・構成】
- 「〜なんですよね」「〜なのかということ」など柔らかく断言する語尾
- 現場の観察を一言で言い切り、その理由や背景を続ける構成
- 「コンサルの仕事をするようになって気づいた〇〇が、〜ということ」のような導入

【思想・観点】
- コンサル・ファームの"内側"を率直に語る（外から見えない現実）
- 「決められない大人」「ボールを止めない」など、人の行動・組織の本質を観察する視点
- 「問いが間違っている」「本当の理由は〜」など、表面でなく構造を見る思考
- 自分の経験から普遍的な教訓を引き出す（体験 → 本質）

【投稿例（実データ）】
{json.dumps(reference_posts, ensure_ascii=False, indent=2)}
"""

    prompt = f"""あなたはSNSコンテンツの専門家です。
以下の分析データをもとに、Xへの新しい投稿を{count}件生成してください。

## 投稿者のプロフィール
- 元大手外資コンサル（マネージャー、5年以上）→ MBA取得 → 独立1年以上
- ターゲット: コンサル転職・キャリアアップを目指す会社員
- スタイル: きれいごとなし、本音、実体験ベース

## 自分の過去投稿（エンゲージメント上位）
{json.dumps(top_mine, ensure_ascii=False, indent=2)}

## 自分の過去投稿（エンゲージメント低め・参考）
{json.dumps(bottom_mine, ensure_ascii=False, indent=2)}
{ref_section}
## 類似アカウントのバズ投稿
{json.dumps(trending_posts[:10], ensure_ascii=False, indent=2)}

## 生成ルール
- 1投稿あたり **140文字以内**（厳守）
- 参考アカウント（{", ".join("@" + a for a in REFERENCE_ACCOUNTS)}）の「コンサルあるある」「意外な本質暴露」「問い発見」のパターンを積極的に活用する
- 伸びた投稿のフォーマット・語尾・構成を参考にする
- 伸びなかった投稿のパターンは避ける
- バズ投稿のテーマや切り口を参考にしつつ、自分の経験に落とし込む
- 投稿は「---」で区切る

投稿本文のみを出力してください（番号・説明・コメント不要）。"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def main():
    print("=" * 50)
    print("AI投稿生成スクリプト")
    print("=" * 50)

    print("\n① 自分の過去投稿を取得中...")
    my_tweets = get_my_tweets()
    print(f"   → {len(my_tweets)} 件取得")
    if my_tweets:
        top = my_tweets[0]
        print(f"   → 最高エンゲージメント: いいね{top['likes']} RT{top['retweets']}")
        print(f"      「{top['text'][:40]}...」")

    print("\n② バズ投稿を調査中...")
    trending = get_trending_posts()
    print(f"   → トレンド: {len(trending)} 件取得")
    reference = get_reference_account_posts()
    print(f"   → 参考アカウント: {len(reference)} 件取得")

    # 採点基準更新用にデータを保存
    scoring_context = {
        "updated_at": datetime.now().isoformat(),
        "reference_posts": reference,
        "trending_posts": trending[:10],
    }
    with open("scoring_context.json", "w", encoding="utf-8") as f:
        json.dump(scoring_context, f, ensure_ascii=False, indent=2)
    print("   → scoring_context.json を更新しました")

    print(f"\n③ Claude APIで {GENERATE_COUNT} 件の投稿を生成中...")
    generated = generate_with_claude(my_tweets, trending, GENERATE_COUNT, reference)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"""# 生成日時: {timestamp}
# -----------------------------------------------
# 使い方:
#   1. 下の投稿を確認・編集してください
#   2. 不要な投稿は「---」ごと削除してください
#   3. OKなら: python approve.py を実行
# -----------------------------------------------

"""
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        f.write(header + generated)

    print(f"\n✅ {PENDING_FILE} に保存しました")
    print("   内容を確認・編集後、approve.py を実行してキューに追加してください。")
    print("=" * 50)


if __name__ == "__main__":
    main()
