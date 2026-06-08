"""
monitor_futsal_email.py — Gmailを監視し、フットサル枠が空いた通知メールが届いたらLINEで知らせる。

前提:
  .env に GMAIL_ADDRESS / GMAIL_APP_PASSWORD / LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID を設定する
  Googleアカウントで「アプリパスワード」を発行しておくこと
  （Googleアカウント → セキュリティ → 2段階認証ON → アプリパスワード）

実行:
  python monitor_futsal_email.py

スケジュール例（タスクスケジューラ）:
  5分ごとに実行
"""

import email
import imaplib
import json
import os
import sys
import urllib.request
from datetime import datetime
from email.header import decode_header
from pathlib import Path

# Windows端末でのUnicodeエラー対策
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "futsal_email_state.json"

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# 通知メールの判定キーワード（件名 or 送信元に含まれるもの）
SENDER_KEYWORDS = ["labola", "yoyaku"]
SUBJECT_KEYWORDS = ["空き", "キャンセル", "空いた", "空枠", "参加可能", "受付開始", "空き枠"]

# 特定イベントを絞りたい場合（空文字にすれば全labola通知を拾う）
EVENT_KEYWORDS = ["フットサル", "2510257"]


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"notified_uids": []}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def decode_mime_str(value: str) -> str:
    parts = decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def send_line_notification(subject: str, sender: str, received_at: str):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    if not token or not user_id:
        print("[WARN] LINE設定が.envにありません。LINE通知をスキップします。")
        return

    text = (
        "⚽ フットサル空き通知メールが届きました！\n\n"
        f"件名: {subject}\n"
        f"送信元: {sender}\n"
        f"受信時刻: {received_at}\n\n"
        "急いで予約サイトを確認してください！\n"
        "https://yoyaku.labola.jp/r/shop/3078/event/show/2510257/"
    )

    payload = json.dumps({
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as res:
            print(f"[INFO] LINE通知を送信しました status={res.status}")
    except urllib.error.HTTPError as e:
        print(f"[WARN] LINE送信失敗: {e.code} {e.read().decode()}")


def is_target_mail(subject: str, sender: str) -> bool:
    subject_lower = subject.lower()
    sender_lower = sender.lower()

    sender_match = any(kw in sender_lower for kw in SENDER_KEYWORDS)
    subject_match = any(kw in subject_lower for kw in SUBJECT_KEYWORDS)
    event_match = (
        not EVENT_KEYWORDS
        or any(kw in subject_lower or kw in sender_lower for kw in EVENT_KEYWORDS)
    )

    return (sender_match or subject_match) and event_match


def check():
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_address or not app_password:
        print("[ERROR] .envにGMAIL_ADDRESSとGMAIL_APP_PASSWORDを設定してください")
        return

    state = load_state()
    notified_uids = set(state.get("notified_uids", []))

    print(f"[INFO] Gmail接続中... ({gmail_address})")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(gmail_address, app_password)
        mail.select("INBOX")
    except Exception as e:
        print(f"[ERROR] Gmail接続失敗: {e}")
        return

    # 未読メールを取得（全件でも可）
    _, data = mail.search(None, "UNSEEN")
    uids = data[0].split()
    print(f"[INFO] 未読メール {len(uids)} 件を確認")

    found = False
    for uid in uids:
        uid_str = uid.decode()
        if uid_str in notified_uids:
            continue

        _, msg_data = mail.fetch(uid, "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        subject = decode_mime_str(msg.get("Subject", ""))
        sender = decode_mime_str(msg.get("From", ""))
        date_str = msg.get("Date", "")

        print(f"  [{uid_str}] {sender} | {subject}".encode("utf-8", errors="replace").decode("utf-8"))

        if is_target_mail(subject, sender):
            print(f"[HIT] 対象メール発見: {subject}")
            send_line_notification(subject, sender, date_str)
            notified_uids.add(uid_str)
            found = True

    mail.logout()

    if found:
        state["notified_uids"] = list(notified_uids)
        save_state(state)
        print("[INFO] 状態を保存しました")
    else:
        print("[INFO] 対象メールなし")


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] フットサルメール監視 開始")
    check()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 完了")
