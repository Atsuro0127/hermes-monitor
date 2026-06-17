"""
monitor_hermes.py — エルメス公式サイトでベアンのキーケース在庫を監視し、
新たに出品されたらLINEで通知する。

Windows: タスクスケジューラで実行
GitHub Actions: .github/workflows/hermes_monitor.yml で5分ごとに実行
"""
import asyncio
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
SEARCH_URL = "https://www.hermes.com/jp/ja/search/?s=ベアン"
KEY_KEYWORDS = ["キー", "porte-clés", "porte clés", "porteclés"]
STATE_FILE = BASE_DIR / "hermes_monitor_state.json"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"seen_ids": []}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_line_notification(items: list):
    token = (os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or "").strip().lstrip("﻿")
    user_id = (os.getenv("LINE_USER_ID") or "").strip().lstrip("﻿")
    if not token or not user_id:
        print("[WARN] LINE設定が.envにありません。LINE通知をスキップします。")
        return

    lines = ["【エルメス】ベアンのキーケースが入荷しました！\n"]
    for item in items:
        lines.append(f"・{item['name']}")
        if item['price']:
            lines.append(f"  {item['price']}")
        lines.append(f"  {item['url']}\n")
    lines.append("今すぐチェック：")
    lines.append(SEARCH_URL)

    text = "\n".join(lines)
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
            print(f"[INFO] LINE通知を送信しました ({len(items)}件) status={res.status}")
    except urllib.error.HTTPError as e:
        print(f"[WARN] LINE送信失敗: {e.code} {e.read().decode()}")


async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto(SEARCH_URL, wait_until="domcontentloaded")
        await asyncio.sleep(2)  # JS描画待ち

        # 商品リストを取得
        items = await page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('[data-testid="product-item"], .product-item-grid, .product-item').forEach(el => {
                    const link = el.querySelector('a[href*="/product/"]');
                    const price = el.querySelector('[class*="price"], [data-testid*="price"]');
                    if (link) {
                        results.push({
                            name: link.innerText.trim(),
                            url: 'https://www.hermes.com' + link.getAttribute('href'),
                            price: price ? price.innerText.trim() : '',
                        });
                    }
                });
                return results;
            }
        """)

        # JS未描画の場合はアクセシビリティツリーからリンクを取得
        if not items:
            links = await page.query_selector_all('a[href*="/jp/ja/product/"]')
            for link in links:
                href = await link.get_attribute("href")
                text = await link.inner_text()
                if href and text.strip():
                    items.append({
                        "name": text.strip(),
                        "url": "https://www.hermes.com" + href,
                        "price": "",
                    })

        await browser.close()

    return items


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{now}] エルメス監視スクリプト実行中...")

    items = asyncio.run(check())
    print(f"  「ベアン」検索結果: {len(items)}件")

    # キーケース候補を抽出
    key_items = []
    for item in items:
        name_lower = item["name"].lower()
        if any(kw in name_lower or kw in item["name"] for kw in KEY_KEYWORDS):
            key_items.append(item)

    if not key_items:
        print("  キーケースはまだ掲載されていません。")
        return

    # 既に通知済みでないものだけ通知
    state = load_state()
    seen_ids = set(state.get("seen_ids", []))
    new_items = [item for item in key_items if item["url"] not in seen_ids]

    if not new_items:
        print(f"  キーケース{len(key_items)}件あり（通知済み）")
        return

    print(f"  新しいキーケースを発見！ {len(new_items)}件")
    for item in new_items:
        print(f"    ・{item['name']} {item['price']}")
        print(f"      {item['url']}")

    send_line_notification(new_items)

    # 通知済みとして記録
    for item in new_items:
        seen_ids.add(item["url"])
    save_state({"seen_ids": list(seen_ids)})


if __name__ == "__main__":
    main()
