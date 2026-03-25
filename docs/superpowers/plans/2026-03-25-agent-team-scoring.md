# Agent Team 採点システム Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `score_posts.py` の採点を Claude Haiku 1体から Claude Sonnet 2体（基準採点役A・ターゲット目線採点役B）の Agent Team に刷新し、両者が7点以上の投稿のみをPASSさせる。

**Architecture:** 採点役A（Sonnet）が既存SCORING_CRITERIAとscorinng_context.jsonで基準採点し、採点役B（Sonnet）がターゲットペルソナのみで採点する。どちらかがFAILならOpusが両フィードバックを受けて再生成（最大2回）。PASSした投稿はpending_review.txtに書き戻してapprove.pyフローへ渡す。

**Tech Stack:** Python 3.10、anthropic SDK（claude-sonnet-4-6、claude-opus-4-6）、pytest

---

## ファイル構成

| ファイル | 変更内容 |
|---------|---------|
| `score_posts.py` | 全面書き換え（Haiku単体 → Sonnet 2体 Agent Team） |
| `tests/test_score_posts.py` | 新規作成（採点ロジックの単体テスト） |

---

### Task 1: テストファイルのセットアップと採点役Aの単体テスト

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_score_posts.py`

- [ ] **Step 1: testsディレクトリとinitファイルを作成**

```bash
mkdir tests
touch tests/__init__.py
```

- [ ] **Step 2: 採点役Aのテストを書く（まだ実装はしない）**

`tests/test_score_posts.py` に以下を書く:

```python
"""score_posts.py Agent Team のテスト"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_score_a_total_is_sum_of_axes():
    """採点役AのtotalはLLM自己申告値を無視してscore_A〜Eの合計で上書きする"""
    from score_posts import normalize_score_a
    raw = {"score_A": 3, "score_B": 2, "score_C": 1, "score_D": 2, "score_E": 1, "total": 99, "reason": "test"}
    result = normalize_score_a(raw)
    assert result["total"] == 9  # 3+2+1+2+1


def test_score_a_missing_keys_default_to_zero():
    """採点役Aの出力にキーが欠けている場合は0で補完する"""
    from score_posts import normalize_score_a
    raw = {"score_A": 3, "reason": "test"}
    result = normalize_score_a(raw)
    assert result["total"] == 3
    assert result["score_B"] == 0


def test_score_b_valid_range():
    """採点役Bのtotalが0〜10の整数なら正常"""
    from score_posts import validate_score_b
    assert validate_score_b({"total": 7, "reason": "ok"}) is True
    assert validate_score_b({"total": 0, "reason": "ok"}) is True
    assert validate_score_b({"total": 10, "reason": "ok"}) is True


def test_score_b_out_of_range():
    """採点役Bのtotalが範囲外ならFalse"""
    from score_posts import validate_score_b
    assert validate_score_b({"total": 11, "reason": "ng"}) is False
    assert validate_score_b({"total": -1, "reason": "ng"}) is False


def test_score_b_non_integer():
    """採点役Bのtotalが整数でなければFalse"""
    from score_posts import validate_score_b
    assert validate_score_b({"total": 7.5, "reason": "ng"}) is False


def test_pass_requires_both_agents_7_or_above():
    """A・B両方7点以上でPASS"""
    from score_posts import is_pass
    assert is_pass(score_a_total=7, score_b_total=7) is True
    assert is_pass(score_a_total=10, score_b_total=10) is True


def test_fail_if_either_agent_below_7():
    """どちらか一方でも6点以下はFAIL"""
    from score_posts import is_pass
    assert is_pass(score_a_total=6, score_b_total=8) is False
    assert is_pass(score_a_total=8, score_b_total=6) is False
    assert is_pass(score_a_total=6, score_b_total=6) is False


def test_build_retry_prompt_includes_both_feedbacks():
    """差し戻しプロンプトに採点役A・B両方のreasonが含まれる"""
    from score_posts import build_retry_feedback
    feedback = build_retry_feedback("フックが弱い", "刺さらない")
    assert "採点役A（品質基準）の指摘: フックが弱い" in feedback
    assert "採点役B（ターゲット目線）の指摘: 刺さらない" in feedback
```

- [ ] **Step 3: テストが失敗することを確認**

```bash
cd C:\Users\atsur\Documents\my-first-project
python -m pytest tests/test_score_posts.py -v
```

期待: `ImportError` または `ModuleNotFoundError`（まだ関数が存在しない）

- [ ] **Step 4: コミット**

```bash
git add tests/__init__.py tests/test_score_posts.py
git commit -m "test: add agent team scoring unit tests (red)"
```

---

### Task 2: ヘルパー関数の実装

**Files:**
- Modify: `score_posts.py`（importと定数は既存のまま、新関数を追加）

- [ ] **Step 1: 既存の `score_posts.py` の先頭にある import と定数を確認**

既存の以下はそのまま残す:
- `SCORING_CRITERIA`
- `USER_STYLE`
- `BUZZ_PATTERNS`
- `load_scoring_context()`
- `get_client()`

- [ ] **Step 2: `score_posts.py` に以下のヘルパー関数を追加（既存関数の直前に挿入）**

```python
def normalize_score_a(raw: dict) -> dict:
    """採点役AのtotalをLLM自己申告値ではなくscore_A〜Eの合計で上書きする"""
    for key, default in [("score_A", 0), ("score_B", 0), ("score_C", 0), ("score_D", 0), ("score_E", 0), ("reason", "")]:
        raw.setdefault(key, default)
    raw["total"] = raw["score_A"] + raw["score_B"] + raw["score_C"] + raw["score_D"] + raw["score_E"]
    return raw


def validate_score_b(raw: dict) -> bool:
    """採点役Bのtotalが0〜10の整数かチェック"""
    total = raw.get("total")
    return isinstance(total, int) and 0 <= total <= 10


def is_pass(score_a_total: int, score_b_total: int) -> bool:
    """A・B両方7点以上でPASS"""
    return score_a_total >= 7 and score_b_total >= 7


def build_retry_feedback(reason_a: str, reason_b: str) -> str:
    """差し戻し用フィードバック文字列を生成"""
    return f"採点役A（品質基準）の指摘: {reason_a}\n採点役B（ターゲット目線）の指摘: {reason_b}"
```

- [ ] **Step 3: テストを実行してPASSすることを確認**

```bash
python -m pytest tests/test_score_posts.py -v
```

期待: 全8件 PASS

- [ ] **Step 4: コミット**

```bash
git add score_posts.py
git commit -m "feat: add helper functions for agent team scoring"
```

---

### Task 3: 採点役A（基準採点）の実装

**Files:**
- Modify: `score_posts.py`

- [ ] **Step 1: `score_post` 関数を `score_post_a` に書き換える**

既存の `score_post()` を以下に置き換える（関数名変更＋モデル変更＋context動的補足を追加）:

```python
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
```

- [ ] **Step 2: テストを実行して既存テストが壊れていないことを確認**

```bash
python -m pytest tests/test_score_posts.py -v
```

期待: 全件 PASS

- [ ] **Step 3: コミット**

```bash
git add score_posts.py
git commit -m "feat: implement score_post_a with Sonnet and dynamic context"
```

---

### Task 4: 採点役B（ターゲット目線）の実装

**Files:**
- Modify: `score_posts.py`

- [ ] **Step 1: `score_post_b` 関数を追加**

```python
def score_post_b(client, text: str) -> dict:
    """採点役B: ターゲット目線のみで採点（Claude Sonnet、データなし）"""
    prompt = f"""あなたは「コンサル転職・キャリアアップを目指す会社員」です。
以下のXへの投稿を読んで、素直な感想として採点してください。

採点基準：
- 10点: 強く共感・シェアしたい
- 7〜9点: 刺さった・参考になった
- 4〜6点: まあまあ・普通
- 1〜3点: ピンとこない・スルーする
- 0点: 全く刺さらない

## 採点対象の投稿
{text}

## 出力形式（JSON）
{{
  "total": <0〜10の整数>,
  "reason": "<50字以内で刺さった理由または刺さらなかった理由>"
}}

JSONのみ出力してください。"""

    res = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = res.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
```

- [ ] **Step 2: テストを実行して全件PASSを確認**

```bash
python -m pytest tests/test_score_posts.py -v
```

- [ ] **Step 3: コミット**

```bash
git add score_posts.py
git commit -m "feat: implement score_post_b with Sonnet target persona"
```

---

### Task 5: Opusによる差し戻し再生成関数の実装

**Files:**
- Modify: `score_posts.py`

- [ ] **Step 1: 既存の `revise_post()` を `revise_post_with_opus()` に書き換える**

```python
def revise_post_with_opus(client, text: str, feedback: str) -> str:
    """採点役A・Bのフィードバックを受けてOpusが投稿を再生成"""
    prompt = f"""以下の投稿が採点で不合格でした。

{feedback}

{SCORING_CRITERIA}

{USER_STYLE}

{BUZZ_PATTERNS}

## 元の投稿
{text}

上記のフィードバックを踏まえ、採点基準でA・B両方7点以上になるよう投稿を改善してください。
元の思想・メッセージは保ちながら、フック・具体性・ターゲットへの共感を改善してください。
改善後の投稿本文のみ出力してください（説明不要）。"""

    res = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return res.content[0].text.strip()
```

- [ ] **Step 2: テストを実行して全件PASSを確認**

```bash
python -m pytest tests/test_score_posts.py -v
```

- [ ] **Step 3: コミット**

```bash
git add score_posts.py
git commit -m "feat: implement revise_post_with_opus for retry"
```

---

### Task 6: main関数をAgent Team構成に書き換え

**Files:**
- Modify: `score_posts.py`（`main()` 関数全体を置き換え）

- [ ] **Step 1: 既存の `main()` 関数を以下に完全に置き換える**

```python
def main():
    print("=" * 50)
    print("投稿採点 & キュー追加スクリプト（Agent Team）")
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
        print("  → scoring_context.json を採点役Aの基準に反映しました\n")

    approved = []
    results = []

    for i, original_text in enumerate(posts, 1):
        print(f"【{i}/{len(posts)}】{original_text[:40].replace(chr(10), ' ')}...")

        text = original_text
        final_score_a = None
        final_score_b = None
        passed = False

        for attempt in range(MAX_RETRIES + 1):
            # 採点役A
            try:
                score_a = score_post_a(client, text, context)
            except Exception as e:
                print(f"  [ERROR] 採点役A呼び出し失敗 (試行{attempt + 1}): {e}")
                score_a = {"total": 0, "score_A": 0, "score_B": 0, "score_C": 0, "score_D": 0, "score_E": 0, "reason": "採点エラー"}

            # 採点役B
            try:
                score_b_raw = score_post_b(client, text)
                if not validate_score_b(score_b_raw):
                    raise ValueError(f"採点役Bのtotalが範囲外: {score_b_raw.get('total')}")
                score_b = score_b_raw
            except Exception as e:
                print(f"  [ERROR] 採点役B呼び出し失敗 (試行{attempt + 1}): {e}")
                score_b = {"total": 0, "reason": "採点エラー"}

            final_score_a = score_a
            final_score_b = score_b

            label_a = "PASS" if score_a["total"] >= 7 else "FAIL"
            label_b = "PASS" if score_b["total"] >= 7 else "FAIL"
            print(f"  採点A: {score_a['total']}/10点 [{label_a}]  "
                  f"A={score_a['score_A']} B={score_a['score_B']} "
                  f"C={score_a['score_C']} D={score_a['score_D']} "
                  f"E={score_a['score_E']}")
            print(f"  採点A理由: {score_a['reason']}")
            print(f"  採点B: {score_b['total']}/10点 [{label_b}]")
            print(f"  採点B理由: {score_b['reason']}")

            if is_pass(score_a["total"], score_b["total"]):
                passed = True
                break

            if attempt < MAX_RETRIES:
                print(f"  → FAIL。生成役に差し戻し中... (試行 {attempt + 1}/{MAX_RETRIES})")
                feedback = build_retry_feedback(score_a["reason"], score_b["reason"])
                try:
                    text = revise_post_with_opus(client, text, feedback)
                    print(f"  再生成: {text[:60].replace(chr(10), ' ')}...")
                except Exception as e:
                    print(f"  [ERROR] 再生成失敗: {e}。この投稿をスキップします。")
                    break

        results.append({
            "original": original_text,
            "final_text": text,
            "score_a": final_score_a["total"] if final_score_a else 0,
            "score_b": final_score_b["total"] if final_score_b else 0,
            "passed": passed,
        })

        if passed:
            approved.append({"text": text, "source": "ai_generated"})
            print(f"  → PASS。保存します")
        else:
            print(f"  → {MAX_RETRIES}回差し戻しても不合格のためスキップ")
        print()

    passed_count = sum(1 for r in results if r["passed"])
    print("=" * 50)
    print(f"採点結果: {passed_count}/{len(posts)} 件がPASS")

    if approved:
        review_content = "\n---\n".join(a["text"] for a in approved)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            f.write(review_content)
        print(f"\n{PENDING_FILE} に {passed_count} 件を保存しました。")
        print("内容を確認後、approve.py を実行してキューに追加してください。")
    else:
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            f.write("")
        print("\nPASSした投稿がありませんでした。")

    print("=" * 50)
```

- [ ] **Step 2: テストを実行して全件PASSを確認**

```bash
python -m pytest tests/test_score_posts.py -v
```

- [ ] **Step 3: 不要になった旧関数を削除**

`score_posts.py` から以下を削除する:
- `score_post()` 関数（`score_post_a` に置き換え済み）
- `revise_post()` 関数（`revise_post_with_opus` に置き換え済み）

- [ ] **Step 4: コミット**

```bash
git add score_posts.py
git commit -m "feat: rewrite main() with Agent Team scoring flow"
```

---

### Task 7: 動作確認

**Files:**
- Read: `pending_review.txt`（テスト用に手動作成）

- [ ] **Step 1: テスト用の pending_review.txt を作成**

```bash
cat > pending_review.txt << 'EOF'
コンサルに入って最初に驚いたのは、議事録の質が仕事の質と直結することだった。内容より構造が大事で、「誰が何をいつまでに」が書けない人は信頼されない。
---
キャリアはスキルより文脈で決まる。同じ実力でも、コンサル出身というだけで次のドアが開く。これが現実だと気づいたとき、ブランドの意味を理解した。
---
会議で発言できない人の多くは、準備不足ではなく「正解を出そう」としている。コンサルで学んだのは、仮説でいいから先に言う勇気だった。
EOF
```

- [ ] **Step 2: スクリプトを実行して動作確認**

```bash
python score_posts.py
```

確認ポイント:
- 採点役A・Bそれぞれのスコアとreasonが表示されること
- A・B両方7点以上の投稿が PASS と表示されること
- PASSした投稿が `pending_review.txt` に書き戻されること
- FAILした投稿は差し戻しループが走ること

- [ ] **Step 3: 最終コミット**

```bash
git add score_posts.py tests/
git commit -m "feat: complete agent team scoring implementation"
```
