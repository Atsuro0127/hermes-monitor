"""
GitHub ActionsのIPからlabolaへログインできるかのみテストする。
book_futsal.pyとは独立して実行可能。
"""
import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from book_futsal import login, LOGIN_URL

load_dotenv()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        result = await login(page)
        if result:
            print("[PASS] ログイン成功 — GitHub ActionsのIPはブロックされていません")
        else:
            print("[FAIL] ログイン失敗 — IPブロックまたは認証エラーの可能性あり")
            await page.screenshot(path="test_login_result.png")
            print("[DEBUG] スクリーンショット保存: test_login_result.png")
        await browser.close()
    return result

if __name__ == "__main__":
    ok = asyncio.run(main())
    exit(0 if ok else 1)
