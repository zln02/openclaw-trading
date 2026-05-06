"""Tests for BTC factor_snapshot 도입 (Step 4).

save_log() 의 팩터 스냅샷 수집/저장 흐름을 단위 검증한다.
- BUY/SELL 시 factor_snapshot 페이로드 기록
- HOLD 시 factor_snapshot 미기록
- calc_all 예외 시 graceful fallback
- top5 abs 정렬 검증
- JSONB string 포맷 검증
- 1차 INSERT 실패 시 factor_snapshot 제거 후 재시도
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

# conftest.py 가 UPBIT_ACCESS_KEY/UPBIT_SECRET_KEY 등 setdefault 처리
# btc_trading_agent 모듈 레벨에서 sys.exit(1) 을 막기 위해 conftest 의존
import btc.btc_trading_agent as agent

# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture
def fake_factors():
    """calc_all 이 반환할 10-factor dict.
    abs 내림차순: bb_position(100) > rsi_14d(80) > fg_index(50) >
                  macd_signal(5) > momentum_1m(3.5) > …
    top5 keys: bb_position, rsi_14d, fg_index, macd_signal, momentum_1m
    """
    return {
        "rsi_14d": 80.0,
        "bb_position": -100.0,
        "macd_signal": 5.0,
        "momentum_1m": -3.5,
        "atr_pct": 2.0,
        "fg_index": 50.0,
        "search_trend": 1.5,
        "volume_ratio_20d": 0.8,
        "social_sentiment": 0.2,
        "orderbook_imbalance": -0.1,
    }


@pytest.fixture
def base_kwargs():
    """save_log 의 공통 호출 인자 (BUY 기본)."""
    return {
        "indicators": {
            "price": 90_000_000,
            "rsi": 68.5,
            "macd": 150.0,
        },
        "signal": {"action": "BUY", "confidence": 70, "reason": "test-buy"},
        "result": {"result": "OK"},
        "fg": {"value": 50},
        "volume": {"ratio": 1.2},
        "comp": {"bb_pct": 55.0, "trend": "UPTREND", "total": 72},
        "funding": {"rate": 0.01},
        "oi": {"ratio": 0.0},
        "ls_ratio": {"ls_ratio": 1.0},
        "kimchi": 0.5,
        "market_regime": "BULL",
    }


def _make_insert_mock(supabase_mock):
    """supabase.table("btc_trades").insert(payload).execute() 체인 설정.
    insert_mock.call_args_list 로 페이로드 검사 가능.
    """
    insert_mock = MagicMock()
    insert_mock.return_value.execute.return_value = MagicMock(data=[{"id": 1}])
    supabase_mock.table.return_value.insert = insert_mock
    return insert_mock


# ── Test 1: BUY → factor_snapshot 기록 ──────────────────────────────────────

def test_buy_records_factor_snapshot_in_payload(base_kwargs, fake_factors):
    """signal action=BUY → INSERT 페이로드에 factor_snapshot 키 존재 + JSON 파싱 가능 dict."""
    supabase_mock = MagicMock()
    insert_mock = _make_insert_mock(supabase_mock)

    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", return_value=fake_factors), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        agent.save_log(**base_kwargs)

    assert insert_mock.call_args_list, "INSERT 가 한 번 이상 호출돼야 함"
    payload = insert_mock.call_args_list[0].args[0]
    assert "factor_snapshot" in payload, "BUY 시 factor_snapshot 키가 페이로드에 있어야 함"
    parsed = json.loads(payload["factor_snapshot"])
    assert isinstance(parsed, dict), "factor_snapshot 은 JSON dict 여야 함"


# ── Test 2: SELL → factor_snapshot 기록 ─────────────────────────────────────

def test_sell_records_factor_snapshot_in_payload(base_kwargs, fake_factors):
    """signal action=SELL → INSERT 페이로드에 factor_snapshot 키 존재 + JSON 파싱 가능 dict."""
    base_kwargs["signal"] = {"action": "SELL", "confidence": 75, "reason": "test-sell"}
    supabase_mock = MagicMock()
    insert_mock = _make_insert_mock(supabase_mock)

    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", return_value=fake_factors), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        agent.save_log(**base_kwargs)

    payload = insert_mock.call_args_list[0].args[0]
    assert "factor_snapshot" in payload, "SELL 시 factor_snapshot 키가 페이로드에 있어야 함"
    parsed = json.loads(payload["factor_snapshot"])
    assert isinstance(parsed, dict)


# ── Test 3: HOLD → factor_snapshot 없음 ──────────────────────────────────────

def test_hold_does_not_record_factor_snapshot(base_kwargs, fake_factors):
    """signal action=HOLD → INSERT 페이로드에 factor_snapshot 키 없음."""
    base_kwargs["signal"] = {"action": "HOLD", "confidence": 0, "reason": "wait"}
    supabase_mock = MagicMock()
    insert_mock = _make_insert_mock(supabase_mock)

    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", return_value=fake_factors), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        agent.save_log(**base_kwargs)

    assert insert_mock.call_args_list, "INSERT 가 한 번 이상 호출돼야 함"
    payload = insert_mock.call_args_list[0].args[0]
    assert "factor_snapshot" not in payload, "HOLD 시 factor_snapshot 이 없어야 함"


# ── Test 4: calc_all 예외 → graceful fallback ─────────────────────────────

def test_calc_all_failure_falls_back_gracefully(base_kwargs):
    """calc_all 예외 raise → INSERT 호출은 일어남 + 함수 자체 예외 미전파."""
    supabase_mock = MagicMock()
    insert_mock = _make_insert_mock(supabase_mock)

    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", side_effect=RuntimeError("factor error")), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        # 예외가 전파되지 않아야 함
        agent.save_log(**base_kwargs)

    assert insert_mock.call_args_list, "calc_all 실패해도 INSERT 는 호출돼야 함"
    payload = insert_mock.call_args_list[0].args[0]
    assert "factor_snapshot" not in payload, "calc_all 실패 시 factor_snapshot 키 없어야 함"


# ── Test 5: top5 abs 정렬 검증 ───────────────────────────────────────────────

def test_factor_snapshot_top5_by_abs_value(base_kwargs, fake_factors):
    """calc_all 10개 dict 반환 → factor_snapshot json 파싱 → top5 키만, abs 내림차순."""
    supabase_mock = MagicMock()
    insert_mock = _make_insert_mock(supabase_mock)

    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", return_value=fake_factors), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        agent.save_log(**base_kwargs)

    payload = insert_mock.call_args_list[0].args[0]
    assert "factor_snapshot" in payload
    parsed = json.loads(payload["factor_snapshot"])

    # 정확히 5개 키
    assert len(parsed) == 5, f"top5 여야 함, 실제: {len(parsed)}개 — {list(parsed.keys())}"

    # abs 내림차순 정렬 검증 (순서 보장)
    abs_values = [abs(v) for v in parsed.values()]
    assert abs_values == sorted(abs_values, reverse=True), \
        f"abs 내림차순이어야 함: {list(zip(parsed.keys(), abs_values))}"

    # 예상 top5 키 포함 확인 (fake_factors 기준)
    expected_top5 = {"bb_position", "rsi_14d", "fg_index", "macd_signal", "momentum_1m"}
    assert set(parsed.keys()) == expected_top5, \
        f"예상 top5 키 불일치: {set(parsed.keys())} vs {expected_top5}"


# ── Test 6: factor_snapshot JSONB string 포맷 ────────────────────────────────

def test_factor_snapshot_jsonb_string_format(base_kwargs, fake_factors):
    """INSERT 페이로드의 factor_snapshot 이 str (json.dumps 결과) + json.loads 가능 + 한글 가능."""
    # 한글 키를 포함한 fake_factors 로 ensure_ascii=False 검증
    factors_with_korean = dict(fake_factors)
    factors_with_korean["한국어팩터"] = 99.0  # 한글 키 추가 (11개)

    supabase_mock = MagicMock()
    insert_mock = _make_insert_mock(supabase_mock)

    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", return_value=factors_with_korean), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        agent.save_log(**base_kwargs)

    payload = insert_mock.call_args_list[0].args[0]
    assert "factor_snapshot" in payload
    fs = payload["factor_snapshot"]

    # str 타입이어야 함 (json.dumps 결과)
    assert isinstance(fs, str), f"factor_snapshot 은 str 이어야 함, 실제: {type(fs)}"

    # json.loads 가능해야 함
    parsed = json.loads(fs)
    assert isinstance(parsed, dict)

    # ensure_ascii=False 검증: 한글이 escape 없이 포함돼야 함
    # (한글 키가 top5 안에 들어갈 만큼 |99.0| 이 크면 포함됨)
    if "한국어팩터" in parsed:
        assert "한국어팩터" in fs, "ensure_ascii=False 이면 한글이 escape 없이 직접 포함돼야 함"
        assert "\\u" not in fs or "한국어팩터" in fs, "한글이 유니코드 escape 되면 안 됨"


# ── Test 7: 1차 INSERT 실패 → factor_snapshot 없이 재시도 ─────────────────────

def test_insert_failure_retries_without_factor_snapshot(base_kwargs, fake_factors):
    """supabase 1차 INSERT 예외 → 2차 INSERT 시 페이로드에 factor_snapshot 없음.
    1차 + 2차 INSERT 호출 횟수 = 2.
    """
    supabase_mock = MagicMock()

    # 페이로드 캡처용
    captured_payloads: list[dict] = []

    def _insert_side_effect(payload):
        # 현재 payload 의 dict 복사본 저장 (in-place del 이 후에 일어나므로 복사 필요)
        captured_payloads.append(dict(payload))
        n = len(captured_payloads)
        mock_chain = MagicMock()
        if n == 1:
            # 1차: factor_snapshot 컬럼 미지원 에러를 execute() 시점에 raise
            mock_chain.execute.side_effect = Exception("column factor_snapshot does not exist")
        else:
            # 2차+: 성공
            mock_chain.execute.return_value = MagicMock(data=[{"id": 2}])
        return mock_chain

    insert_mock = MagicMock(side_effect=_insert_side_effect)
    supabase_mock.table.return_value.insert = insert_mock

    # calc_all mock: fake_factors 반환해야 1차 페이로드에 factor_snapshot 이 있음
    with patch.object(agent, "supabase", supabase_mock), \
         patch("quant.factors.registry.calc_all", return_value=fake_factors), \
         patch("quant.factors.registry.FactorContext", return_value=MagicMock()):
        agent.save_log(**base_kwargs)

    # 총 INSERT 호출 횟수 = 2 (1차 실패 + 2차 재시도)
    assert insert_mock.call_count == 2, \
        f"INSERT 는 정확히 2번 호출돼야 함 (1차 실패 + 2차 재시도), 실제: {insert_mock.call_count}"

    # 1차 페이로드: factor_snapshot 있어야 함 (캡처 시점 = insert 호출 시, del 이전)
    first_payload = captured_payloads[0]
    assert "factor_snapshot" in first_payload, \
        f"1차 INSERT 페이로드에는 factor_snapshot 이 있어야 함, 실제 키: {list(first_payload.keys())}"

    # 2차 페이로드: factor_snapshot 없어야 함 (del 후 재시도)
    second_payload = captured_payloads[1]
    assert "factor_snapshot" not in second_payload, \
        "2차 INSERT 페이로드에는 factor_snapshot 이 없어야 함 (del 후 재시도)"
