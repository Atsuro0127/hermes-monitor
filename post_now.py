"""
次の投稿をキューから取り出してXに投稿する。
Windowsタスクスケジューラで 8:00、12:00、19:30 に実行する。
"""
import json
import os
import sys
import io
import subprocess
import smtplib
from email.mime.text import MIMEText
import tweepy
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

# Windows環境での文字化け対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# スクリプトのあるフォルダを基準にする
os.chdir(Path(__file__).parent)
load_dotenv()

QUEUE_FILE = "queue.json"
HISTORY_FILE = "posted_history.json"
LOW_QUEUE_THRESHOLD = 9  # この件数を下回ったら補充アラート


def _auto_generate():
    """generate_posts.py を実行してGmailで通知する"""
    python = sys.executable
    base = Path(__file__).parent
    pending = base / "pending_review.txt"
    try:
        subprocess.run([python, str(base / "generate_posts.py")], timeout=120)
        print("[INFO] 投稿を生成しました。確認メールを送信します。")
        _send_email(pending)
    except Exception as e:
        print(f"[ERROR] 自動生成に失敗しました: {e}")


def _send_email(pending_path):
    """生成された投稿内容をGmailで通知する"""
    gmail = os.getenv("GMAIL_ADDRESS")
    app_pw = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail or not app_pw:
        print("[WARN] Gmail設定が.envにありません。メール通知をスキップします。")
        return

    try:
        content = pending_path.read_text(encoding="utf-8") if pending_path.exists() else "(内容なし)"
        body = f"""X自動投稿システムから通知です。

新しい投稿候補が生成されました。
内容を確認して、OKなら以下を実行してください：

  cd C:\\Users\\atsur\\Documents\\my-first-project
  python approve.py

---
【生成された投稿候補】
{content}
"""
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = "【X自動投稿】投稿候補の確認をお願いします"
        msg["From"] = gmail
        msg["To"] = gmail

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail, app_pw)
            server.send_message(msg)
        print("[INFO] 確認メールを送信しました。")
    except Exception as e:
        print(f"[WARN] メール送信失敗: {e}")
X_LIMIT = 280  # X weighted char units


def x_length(text):
    count = 0
    for c in text:
        if '\u3000' <= c <= '\u9fff' or '\uf900' <= c <= '\uffef':
            count += 2
        else:
            count += 1
    return count


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def post_tweet(text):
    client = tweepy.Client(
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    )
    response = client.create_tweet(text=text)
    return response.data["id"]


def main():
    queue = load_json(QUEUE_FILE, [])

    if not queue:
        print("❌ キューが空です。generate_posts.py を実行して投稿を生成してください。")
        sys.exit(1)

    post = queue.pop(0)
    text = post["text"]

    # 文字数チェック（X上限: 280 weighted units）
    wlen = x_length(text)
    if wlen > X_LIMIT:
        print(f"[SKIP] 投稿が文字数超過 ({wlen}/280)。スキップします。")
        print(f"  内容: {text[:60]}...")
        save_json(QUEUE_FILE, queue)
        sys.exit(1)

    try:
        tweet_id = post_tweet(text)
        now = datetime.now().isoformat()
        print(f"✅ 投稿成功 [{now}]")
        print(f"   ID: {tweet_id}")
        print(f"   内容: {text[:60]}...")

        history = load_json(HISTORY_FILE, [])
        history.append({
            "tweet_id": str(tweet_id),
            "text": text,
            "posted_at": now,
            "source": post.get("source", "unknown"),
        })
        save_json(HISTORY_FILE, history)
        save_json(QUEUE_FILE, queue)

        remaining = len(queue)
        if remaining < LOW_QUEUE_THRESHOLD:
            print(f"[INFO] キュー残り {remaining} 件。自動生成を開始します...")
            _auto_generate()

    except tweepy.errors.TweepyException as e:
        print(f"❌ 投稿失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
