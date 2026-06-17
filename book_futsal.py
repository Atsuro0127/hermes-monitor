"""
book_futsal.py — labolaの6/20初心者フットサルクリニックを自動予約する。

monitor_futsal_web.py または monitor_futsal_email.py から呼び出される。
予約済みフラグ (futsal_booked.json) で二重予約を防止。
"""

import asyncio
import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

BASE_DIR = Path(__file__).parent
BOOKED_FLAG = BASE_DIR / "futsal_booked.json"

EVENT_ID = "2510258"
SHOP_ID = "3078"
EVENT_URL = f"https://yoyaku.labola.jp/r/shop/{SHOP_ID}/event/show/{EVENT_ID}/"
LOGIN_URL = f"https://yoyaku.labola.jp/r/shop/{SHOP_ID}/member/login/"
BOOKING_URL = f"https://yoyaku.labola.jp/r/booking/event/{EVENT_ID}/shop/{SHOP_ID}/booking-info/"


def is_already_booked() -> bool:
    if not BOOKED_FLAG.exists():
        return False
    with open(BOOKED_FLAG, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("booked", False)


def mark_as_booked(booking_id: str = ""):
    with open(BOOKED_FLAG, "w", encoding="utf-8") as f:
        json.dump({"booked": True, "booking_id": booking_id}, f, ensure_ascii=False, indent=2)


def send_line_notification(message: str):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    if not token or not user_id:
        print("[WARN] LINE設定がありません")
        return

    payload = json.dumps({
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
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
            print(f"[INFO] LINE通知送信 status={res.status}")
    except urllib.error.HTTPError as e:
        print(f"[WARN] LINE送信失敗: {e.code} {e.read().decode()}")


async def login(page) -> bool:
    email = os.getenv("LABOLA_EMAIL")
    password = os.getenv("LABOLA_PASSWORD")

    await page.goto(LOGIN_URL)
    await page.wait_for_load_state("networkidle")

    # すでにログイン済みの場合はスキップ
    if "member/login" not in page.url:
        print("[INFO] すでにログイン済み")
        return True

    # メールアドレスでログイン
    await page.locator("#id_membership_code").fill(email)
    await page.locator("#id_password").fill(password)
    await page.get_by_role("button", name="ログイン").click()
    await page.wait_for_load_state("networkidle")

    if "member/login" in page.url:
        print("[ERROR] ログイン失敗")
        return False

    print("[INFO] ログイン成功")
    return True


async def check_vacancy(page) -> bool:
    """イベントページに「申し込む」リンクがあれば空きあり"""
    await page.goto(EVENT_URL)
    await page.wait_for_load_state("networkidle")

    apply_link = page.locator(f'a[href*="/booking/event/{EVENT_ID}/"]')
    count = await apply_link.count()
    return count > 0


async def book(page) -> bool:
    """予約を実行する。成功したらTrue"""
    # STEP1: 料金プラン選択
    await page.goto(BOOKING_URL)
    await page.wait_for_load_state("networkidle")

    if "booking-info" not in page.url:
        print(f"[ERROR] 予約ページに遷移できません: {page.url}")
        return False

    # 料金プランのラジオボタンを選択
    radio = page.get_by_role("radio").first
    await radio.check()

    await page.get_by_role("button", name="情報入力へ進む").click()
    await page.wait_for_load_state("networkidle")

    # STEP2: 情報入力（会員情報が自動入力済み）
    await page.get_by_role("button", name="内容確認へ進む").click()
    await page.wait_for_load_state("networkidle")

    # STEP3: 同意チェックボックスをJSでON
    await page.evaluate("""
        () => {
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }
    """)
    await page.wait_for_timeout(500)

    # 申込みボタンをクリック
    submit_btn = page.get_by_role("button", name="この内容で申込む")
    await submit_btn.click()
    await page.wait_for_load_state("networkidle")

    # STEP4: 完了確認
    if "finish" in page.url:
        print(f"[INFO] 予約完了! URL: {page.url}")
        return True
    else:
        print(f"[ERROR] 予約完了ページに遷移しませんでした: {page.url}")
        return False


async def run():
    if is_already_booked():
        print("[INFO] すでに予約済みです。スキップします。")
        return False

    print(f"[INFO] 予約処理を開始します (event={EVENT_ID})")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # ログイン
            if not await login(page):
                send_line_notification("❌ labolaログイン失敗。手動で予約してください！\n" + EVENT_URL)
                return False

            # 空き確認
            if not await check_vacancy(page):
                print("[INFO] 空きなし。予約をスキップします。")
                return False

            print("[INFO] 空きあり！予約を実行します。")

            # 予約実行
            success = await book(page)

            if success:
                mark_as_booked()
                send_line_notification(
                    "✅ フットサル予約完了！\n\n"
                    "【初心者限定】フットサルクリニック ※サポート\n"
                    "2026/06/20（土）19:00〜21:00\n"
                    "アディダスフットサルパーク 池袋\n\n"
                    "楽しんできてください！⚽"
                )
                return True
            else:
                send_line_notification(
                    "⚠️ 空きを検知しましたが予約に失敗しました。\n急いで手動で予約してください！\n" + EVENT_URL
                )
                return False

        except Exception as e:
            print(f"[ERROR] 予約処理中にエラー: {e}")
            send_line_notification(f"⚠️ 予約処理中にエラーが発生しました。\n手動で確認してください！\n{EVENT_URL}\n\nエラー: {e}")
            return False
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
