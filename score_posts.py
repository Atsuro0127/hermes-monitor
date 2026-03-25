"""
score_posts.py — 投稿を採点し、7点未満なら自動で再生成してキューに追加する。

フロー:
  generate_posts.py → pending_review.txt → [このスクリプト] → queue.json

使い方:
  python score_posts.py
"""
import json
import os
import sys
import io
import anthropic
from dotenv import load_dotenv
from pathlib import Path

os.chdir(Path(__file__).parent)
load_dotenv()

PENDING_FILE         = "pending_review.txt"
QUEUE_FILE           = "queue.json"
SCORING_CONTEXT_FILE = "scoring_context.json"
PASS_SCORE           = 7
MAX_RETRIES          = 2

SCORING_CRITERIA = """
## 採点基準（10点満点）

### A. フック力（0〜3点）
最初の1〜2行で続きを読みたくなるか
- 3点: 意外な事実・逆説・「コンサルあるある」の鋭い一言など強い引きがある
- 2点: 興味は引けるが普通
- 1点: 抽象的で刺さらない
- 0点: 読む理由がない

### B. 具体性（0〜2点）
コンサル現場ならではの一次体験・観察があるか
- 2点: 実際の案件・クライアント・職場での具体的な場面・経験・数字がある（経験者しか書けない）
- 1点: 少し具体的だが、誰でも言えそうな部分が多い
- 0点: 全体的に抽象論・教科書的

### C. コンサル知見の独自性（0〜2点）
コンサル経験者ならではの視点・気づきが出ているか
以下の軸が出ているか：
・現場で実際に見た/気づいたこと（「〇〇してわかった」「コンサルで気づいたこと」）
・問いを正しく設定する重要性（問いがズレると全部ズレる）
・論理だけでは人は動かない（相手が動ける形にする）
・目的を先に掴む・バリューを常に考える
・仮説を持って動く（丸投げしない）
- 2点: コンサル経験者らしい独自の視点・知見が明確に出ている
- 1点: 薄く出ているが弱い、または一般論に近い
- 0点: 誰でも言えそうな内容

### D. 共感・拡散性（0〜2点）
コンサル・ビジネス層が「わかる」「シェアしたい」と思うか
- 2点: コンサル界隈あるある・職場観察・意外な本質など、ターゲット層が強く共感する
- 1点: 共感はあるが対象が狭い、またはインパクトが弱い
- 0点: 共感しにくい、またはターゲット層に刺さらない

### E. 読みやすさ（0〜1点）
文字数・改行・構造が適切か
- 1点: 140〜280字、改行・構造が適切
- 0点: 長すぎ/短すぎ/読みにくい
"""

USER_STYLE = """
## 投稿者のプロフィール・スタイル
- 元外資コンサル（マネージャー、5年以上）→ MBA → 独立1年以上
- ターゲット: コンサル転職・キャリアアップを目指す会社員
- 文体: 「だと思う」「〜から」等の柔らかい断言、絵文字・ハッシュタグなし
- 構成: 短い1行タイトル → 2〜4文の説明 → 締めの一言
- テーマの軸: コンサル仕事術、バリュー意識、目的思考、問いに答える力
"""

BUZZ_PATTERNS = """
## バズる投稿の構造（コンサル系アカウントの実データより）

### 高エンゲージメントパターン（実例あり）
1. **コンサルあるある・現場観察型**
   「コンサルの仕事をするようになって気づいたこと」「ファームにいてわかったこと」
   → 経験者しか言えないリアルな職場観察。共感で拡散される。

2. **意外な本質暴露型**
   「〇〇が速い本当の理由は〜だから」「〇〇と思われているが実際は〜」
   → 表面的な話ではなく、現場の本質をズバリ言い切る。

3. **問い・論点の発見型**
   「10分考えても答えが出ないときは問いが間違っている」
   → 問いを正しく設定することの重要性。コンサル的思考の真髄。

4. **対比・逆説型**
   「〇〇と思われがちだが、本当は〜」「論理的に正しいだけでは〜」
   → 世間の認識とのズレを突く。読者の認識を更新させる。

5. **経験談ストーリー型**
   具体的な案件・クライアントでの出来事から始めて、普遍的な学びに昇華する。

6. **シンプル格言型**
   短く刺さる一文から始め、2〜3行で理由を補足する。冗長にならない。

### 共通の構造
- 冒頭1行で「これは自分のことだ」と思わせる
- 具体的な場面・数字・固有名詞で信頼性を上げる
- 締めで「だから自分はこう思う」と価値観を提示

### 参考アカウント3選（コンサル系で高エンゲージメントのアカウント）
- **@bcg_acn**: コンサル・ファームの内側を率直に語る。「決められない大人」「ボールを止めない」など人・組織の本質観察。「本当の理由は〜」と構造を見る思考。
- **@narisumashi100**: 泥臭い一次情報収集の体験談。「現場で200人にアンケートを取った」等、経験者しか語れないリアル。若手への実践的アドバイス。
- **@nmmg091**: コンサル転職・実務の具体的な知見。「監査からコンサルに転職するならプロマネを学べ」等、業界内部の実情を語る。
"""


def load_scoring_context() -> str:
    """scoring_context.json から最新のバズ投稿例を読み込んでプロンプト用テキストに変換"""
    if not Path(SCORING_CONTEXT_FILE).exists():
        return ""
    try:
        with open(SCORING_CONTEXT_FILE, encoding="utf-8") as f:
            ctx = json.load(f)
        ref = ctx.get("reference_posts", [])[:6]
        trend = ctx.get("trending_posts", [])[:4]
        updated = ctx.get("updated_at", "")[:10]
        if not ref and not trend:
            return ""
        lines = [f"\n## 最新バズ投稿データ（{updated}更新）"]
        if ref:
            lines.append("\n### 参考アカウントの高エンゲージメント投稿（採点の参考例）")
            for p in ref:
                acct = p.get("account", "")
                text = p.get("text", "")[:100]
                likes = p.get("likes", 0)
                lines.append(f"- @{acct} ({likes}いいね): {text.replace(chr(10), ' ')}")
        if trend:
            lines.append("\n### 直近のトレンド投稿")
            for p in trend:
                text = p.get("text", "")[:80]
                likes = p.get("likes", 0)
                lines.append(f"- ({likes}いいね): {text.replace(chr(10), ' ')}")
        return "\n".join(lines)
    except Exception:
        return ""


def get_client():
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def normalize_score_a(raw: dict) -> dict:
    """採点役AのtotalをLLM自己申告値ではなくscore_A〜Eの合計で上書きする"""
    for key, default in [("score_A", 0), ("score_B", 0), ("score_C", 0), ("score_D", 0), ("score_E", 0), ("reason", "")]:
        raw.setdefault(key, default)
    raw["total"] = raw["score_A"] + raw["score_B"] + raw["score_C"] + raw["score_D"] + raw["score_E"]
    return raw


def validate_score_b(raw: dict) -> bool:
    """採点役Bのtotalが0〜10の整数かチェック（boolは除外）"""
    total = raw.get("total")
    return type(total) is int and 0 <= total <= 10


def is_pass(score_a_total: int, score_b_total: int) -> bool:
    """A・B両方7点以上でPASS"""
    return score_a_total >= 7 and score_b_total >= 7


def build_retry_feedback(reason_a: str, reason_b: str) -> str:
    """差し戻し用フィードバック文字列を生成"""
    return f"採点役A（品質基準）の指摘: {reason_a}\n採点役B（ターゲット目線）の指摘: {reason_b}"


def score_post_a(client, text: str, context: str = "") -> dict:
    """採点役A: 既存基準 + scoring_contextで微調整して採点（Claude Sonnet）"""
    dynamic_note = ""
    if context:
        dynamic_note = f"\n\n## 今週のバズ傾向（採点の補足観点）\n{context}\n上記の傾向を踏まえ、採点基準の各軸を微調整して評価すること。"

    prompt = f"""以下の投稿を採点してください。

{SCORING_CRITERIA}

{USER_STYLE}
{dynamic_note}

## 採点対象の投稿
{text}

## 出力形式（JSON）
{{
  "score_A": <0〜3>,
  "score_B": <0〜2>,
  "score_C": <0〜2>,
  "score_D": <0〜2>,
  "score_E": <0〜1>,
  "total": <合計点>,
  "reason": "<50字以内で改善点または良い点を1つ>"
}}

JSONのみ出力してください。"""

    res = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = res.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    return normalize_score_a(data)


def revise_post(client, text: str, score_result: dict, context: str = "") -> str:
    """採点結果を踏まえて投稿を改善する"""
    prompt = f"""以下の投稿が採点で{score_result['total']}点でした。
改善点: {score_result['reason']}

{SCORING_CRITERIA}

{USER_STYLE}

{BUZZ_PATTERNS}
{context}

## 元の投稿
{text}

上記の採点基準で7点以上になるよう投稿を改善してください。
元の思想・メッセージは保ちながら、フック・具体性・読みやすさを改善してください。
改善後の投稿本文のみ出力してください（説明不要）。"""

    res = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return res.content[0].text.strip()


def load_queue() -> list:
    if not Path(QUEUE_FILE).exists():
        return []
    with open(QUEUE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: list):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 50)
    print("投稿採点 & キュー追加スクリプト")
    print("=" * 50)

    if not Path(PENDING_FILE).exists():
        print(f"ERROR: {PENDING_FILE} が見つかりません。")
        return

    with open(PENDING_FILE, encoding="utf-8") as f:
        content = f.read()

    lines = [l for l in content.split("\n") if not l.startswith("#")]
    clean = "\n".join(lines).strip()

    if not clean:
        print("ERROR: 採点する投稿がありません。")
        return

    posts = [p.strip() for p in clean.split("---") if p.strip()]
    print(f"\n{len(posts)} 件の投稿を採点します...\n")

    client = get_client()
    context = load_scoring_context()
    if context:
        print("  → scoring_context.json を採点基準に反映しました\n")

    approved = []
    results = []

    for i, original_text in enumerate(posts, 1):
        print(f"【{i}/{len(posts)}】{original_text[:40].replace(chr(10), ' ')}...")

        text = original_text
        score_result = None

        for attempt in range(MAX_RETRIES + 1):
            score_result = score_post_a(client, text, context)
            total = score_result["total"]
            label = "PASS" if total >= PASS_SCORE else "FAIL"
            print(f"  採点: {total}/10点 [{label}]  "
                  f"A={score_result['score_A']} B={score_result['score_B']} "
                  f"C={score_result['score_C']} D={score_result['score_D']} "
                  f"E={score_result['score_E']}")
            print(f"  理由: {score_result['reason']}")

            if total >= PASS_SCORE:
                break

            if attempt < MAX_RETRIES:
                print(f"  → 7点未満のため自動改善中... (試行 {attempt + 1}/{MAX_RETRIES})")
                text = revise_post(client, text, score_result, context)
                print(f"  改善後: {text[:60].replace(chr(10), ' ')}...")

        results.append({
            "original": original_text,
            "final_text": text,
            "score": score_result["total"],
            "passed": score_result["total"] >= PASS_SCORE,
        })

        if score_result["total"] >= PASS_SCORE:
            approved.append({"text": text, "source": "ai_generated"})
            print(f"  → キューに追加")
        else:
            print(f"  → {MAX_RETRIES}回改善しても{PASS_SCORE}点未満のためスキップ")
        print()

    # 7点以上のものだけ pending_review.txt に戻す（ユーザー確認用）
    passed = sum(1 for r in results if r["passed"])
    print("=" * 50)
    print(f"採点結果: {passed}/{len(posts)} 件が7点以上")

    if approved:
        review_content = "\n---\n".join(a["text"] for a in approved)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            f.write(review_content)
        print(f"\n{PENDING_FILE} に {passed} 件を保存しました。")
        print("内容を確認後、approve.py を実行してキューに追加してください。")
    else:
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            f.write("")
        print("\n7点以上の投稿がありませんでした。")

    print("=" * 50)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    main()
