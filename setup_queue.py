"""
初回セットアップ: posts_source.txt の20投稿を X用に整形して queue.json に読み込む
一度だけ実行してください。

X文字数ルール: CJK文字=2単位、その他=1単位、上限280単位（日本語は約140文字）
"""
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SOURCE_FILE = "posts_source.txt"
QUEUE_FILE = "queue.json"
X_LIMIT = 280  # X weighted char units


def x_length(text):
    """X基準の文字数カウント（CJK=2, その他=1）"""
    count = 0
    for c in text:
        if '\u3000' <= c <= '\u9fff' or '\uf900' <= c <= '\uffef':
            count += 2
        else:
            count += 1
    return count


def trim_to_x_limit(text, limit=X_LIMIT - 2):
    """X文字数制限に収まるよう末尾をトリム"""
    result = ""
    count = 0
    for c in text:
        w = 2 if ('\u3000' <= c <= '\u9fff' or '\uf900' <= c <= '\uffef') else 1
        if count + w > limit:
            result += "…"
            break
        result += c
        count += w
    return result


with open(SOURCE_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# 丸数字で分割
parts = re.split(r'(?=^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])', content, flags=re.MULTILINE)
parts = [p.strip() for p in parts if p.strip()]

posts = []
for part in parts:
    lines = [l.strip() for l in part.split('\n') if l.strip()]
    if not lines:
        continue

    # 1行目: 番号付きタイトル（番号を除去）
    title_line = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*', '', lines[0])

    # 本文: 2行目以降を結合（空行は改行として残す）
    body_lines = lines[1:]

    # タイトル + 本文を組み合わせてX制限内に収める
    text = title_line
    for bl in body_lines:
        candidate = text + "\n" + bl
        if x_length(candidate) <= X_LIMIT - 2:
            text = candidate
        else:
            break

    # それでも超える場合はトリム
    if x_length(text) > X_LIMIT:
        text = trim_to_x_limit(text)

    posts.append({
        "text": text,
        "source": "original"
    })

with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    json.dump(posts, f, ensure_ascii=False, indent=2)

print(f"OK: {len(posts)}件の投稿を queue.json に追加しました")
for i, p in enumerate(posts, 1):
    chars = x_length(p["text"])
    preview = p["text"][:45].replace('\n', ' ')
    print(f"  {i:2d}. [{chars:3d}/280] {preview}...")
