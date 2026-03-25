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
