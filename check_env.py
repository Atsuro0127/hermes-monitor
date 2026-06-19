"""
check_env.py — 必要な環境変数が全て設定されているか確認する。
スクリプト変更後・デプロイ前に必ず実行すること。
"""
import os
import sys
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv

load_dotenv()

# グループ名の末尾に "(optional)" をつけると未設定でも警告のみ（終了コード0）
REQUIRED = {
    "X投稿 (optional)": [
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
    ],
    "LINE通知": [
        "LINE_CHANNEL_ACCESS_TOKEN",
        "LINE_USER_ID",
    ],
    "フットサル予約": [
        "LABOLA_EMAIL",
        "LABOLA_PASSWORD",
    ],
    "Gmail監視": [
        "GMAIL_ADDRESS",
        "GMAIL_APP_PASSWORD",
    ],
    "Claude API": [
        "ANTHROPIC_API_KEY",
    ],
}

def check():
    all_ok = True
    for group, keys in REQUIRED.items():
        optional = "(optional)" in group
        group_ok = True
        for key in keys:
            val = os.getenv(key)
            stripped = (val or "").strip().strip("﻿")
            if not stripped:
                label = "WARN" if optional else "NG"
                print(f"  [{label}] {key} — 未設定または空")
                group_ok = False
                if not optional:
                    all_ok = False
            else:
                print(f"  [OK] {key} ({len(stripped)}文字)")
        status = "OK" if group_ok else ("WARN" if optional else "NG")
        print(f"[{status}] {group}")
        print()

    if all_ok:
        print("✅ 全ての環境変数が設定されています")
    else:
        print("❌ 未設定の環境変数があります。.envまたはGitHub Secretsを確認してください")
        sys.exit(1)

if __name__ == "__main__":
    check()
