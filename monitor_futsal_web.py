"""
monitor_futsal_web.py — labolaのイベントページを直接監視し、
空きが出たら自動予約する。

GitHub Actions で1分ごとに実行。
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

import book_futsal

load_dotenv()

EVENT_ID = "2510258"
SHOP_ID = "3078"
EVENT_URL = f"https://yoyaku.labola.jp/r/shop/{SHOP_ID}/event/show/{EVENT_ID}/"


async def check_and_book():
    if book_futsal.is_already_booked():
        print("[INFO] 予約済みのため監視をスキップ")
        return

    print(f"[INFO] イベントページを確認中: {EVENT_URL}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(EVENT_URL)
        await page.wait_for_load_state("networkidle")

        # 「申し込む」リンクがあれば空きあり
        apply_link = page.locator(f'a[href*="/booking/event/{EVENT_ID}/"]')
        count = await apply_link.count()
        await browser.close()

    if count > 0:
        print("[HIT] 空きを検知！")
        # 予約処理より先にLINE通知（予約失敗時でも手動対応できるように）
        book_futsal.send_line_notification(
            f"🔔 空きが出ました！今すぐ自動予約を実行中...\n\n"
            f"イベントページ: {EVENT_URL}\n\n"
            "完了したらまたお知らせします！"
        )
        await book_futsal.run()
    else:
        print("[INFO] 満席（空きなし）")


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Webポーリング開始")
    asyncio.run(check_and_book())
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 完了")
