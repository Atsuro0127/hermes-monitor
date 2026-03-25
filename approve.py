"""
pending_review.txt の投稿をキューに追加する。
generate_posts.py → 内容確認・編集 → このスクリプトを実行
"""
import json
import os
from pathlib import Path

os.chdir(Path(__file__).parent)

PENDING_FILE = "pending_review.txt"
QUEUE_FILE = "queue.json"


def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if not os.path.exists(PENDING_FILE):
        print(f"❌ {PENDING_FILE} が見つかりません。generate_posts.py を先に実行してください。")
        return

    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # コメント行を除去して分割
    lines = [l for l in content.split("\n") if not l.startswith("#")]
    clean = "\n".join(lines).strip()

    if not clean:
        print("❌ 承認する投稿がありません。")
        return

    posts_text = [p.strip() for p in clean.split("---") if p.strip()]

    if not posts_text:
        print("❌ 投稿が見つかりませんでした。「---」区切りになっているか確認してください。")
        return

    # 文字数チェック
    valid = []
    for text in posts_text:
        if len(text) > 280:
            print(f"⚠️  スキップ（140文字超 / {len(text)}文字）: {text[:40]}...")
        else:
            valid.append({"text": text, "source": "ai_generated"})

    if not valid:
        print("❌ 有効な投稿がありませんでした。")
        return

    print(f"\n以下の {len(valid)} 件を承認しますか？\n")
    for i, p in enumerate(valid, 1):
        print(f"【{i}】{p['text'][:80].replace(chr(10), ' ')}...")
    print()
    ans = input("承認する場合は y を入力してください: ").strip().lower()
    if ans != "y":
        print("キャンセルしました。pending_review.txt は変更されていません。")
        return

    queue = load_queue()
    queue.extend(valid)

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    # pending をクリア
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        f.write("")

    print(f"✅ {len(valid)} 件の投稿をキューに追加しました")
    print(f"   キュー合計: {len(queue)} 件（約 {len(queue) // 2} 日分）")
    for i, p in enumerate(valid, 1):
        print(f"  {i}. {p['text'][:50].replace(chr(10), ' ')}...")


if __name__ == "__main__":
    main()
