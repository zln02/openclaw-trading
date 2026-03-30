from __future__ import annotations

from agents.news_analyst import NewsAnalyst


def test_batch_analyze_items_returns_three_results(monkeypatch) -> None:
    analyst = NewsAnalyst(model="claude-haiku")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(analyst, "_within_budget", lambda estimated_increment_usd, now=None: True)
    monkeypatch.setattr(analyst, "_save_budget_state", lambda state: None)
    monkeypatch.setattr(analyst, "get_budget_state", lambda now=None: {"spent_usd": 0.0, "calls": 0, "estimated_tokens": 0})
    monkeypatch.setattr(
        analyst,
        "_call_llm",
        lambda prompt, max_tokens=180: """
[
  {"idx": 1, "label": "POSITIVE", "strength": 4, "reason": "good", "confidence": 0.7},
  {"idx": 2, "label": "NEGATIVE", "strength": 2, "reason": "bad", "confidence": 0.6},
  {"idx": 3, "label": "NEUTRAL", "strength": 3, "reason": "flat", "confidence": 0.5}
]
""",
    )

    out = analyst._batch_analyze_items(
        [
            {"headline": "A", "source": "x", "timestamp": "2026-01-01T00:00:00Z"},
            {"headline": "B", "source": "x", "timestamp": "2026-01-01T00:01:00Z"},
            {"headline": "C", "source": "x", "timestamp": "2026-01-01T00:02:00Z"},
        ],
        symbol="BTC",
    )

    assert len(out) == 3, "batch analysis should return one result per input item"
    assert all(item is not None for item in out), "successful batch analysis should fill all item slots"


def test_batch_analyze_items_empty_list_returns_empty(monkeypatch) -> None:
    analyst = NewsAnalyst(model="claude-haiku")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    out = analyst._batch_analyze_items([], symbol="BTC")

    assert out == [], "empty input should return an empty list"


def test_call_llm_uses_claude_for_claude_models(monkeypatch) -> None:
    analyst = NewsAnalyst(model="claude-haiku")
    called = {"claude": False}
    monkeypatch.setattr(analyst, "_call_claude", lambda prompt, max_tokens=180: called.__setitem__("claude", True) or "ok")

    result = analyst._call_llm("hello")

    assert called["claude"] is True, "Claude model should route through _call_claude()"
    assert result == "ok", "Claude result should be returned unchanged"


def test_call_llm_uses_openai_for_openai_models(monkeypatch) -> None:
    analyst = NewsAnalyst(model="gpt-4o-mini")
    called = {"openai": False}
    monkeypatch.setattr(analyst, "_call_openai", lambda prompt, max_tokens=180: called.__setitem__("openai", True) or "ok")

    result = analyst._call_llm("hello")

    assert called["openai"] is True, "OpenAI model should route through _call_openai()"
    assert result == "ok", "OpenAI result should be returned unchanged"


def test_estimate_cost_usd_positive_for_1000ish_tokens() -> None:
    analyst = NewsAnalyst(model="claude-haiku")

    usd, tokens = analyst._estimate_cost_usd("x" * 4000, completion_tokens=1)

    assert usd > 0, "estimated USD cost should be positive for a 1000-token scale prompt"
    assert tokens >= 1000, "estimated token count should reflect a roughly 1000-token input"
