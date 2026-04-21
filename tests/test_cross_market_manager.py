"""CrossMarketRiskManager 단위 테스트 — Supabase 완전 mock."""
from unittest.mock import MagicMock, patch

import pytest

from quant.risk.cross_market_manager import (CrossMarketConfig,
                                             CrossMarketRiskManager,
                                             CrossMarketRiskResult)


def _make_mock_supabase(btc_rows=None, kr_rows=None, us_rows=None):
    """Supabase 클라이언트 mock — 테이블별 데이터 주입."""
    btc_rows = btc_rows or []
    kr_rows = kr_rows or []
    us_rows = us_rows or []

    def _table_selector(table_name):
        mock_table = MagicMock()
        if table_name == "btc_position":
            mock_table.select.return_value.eq.return_value.execute.return_value.data = btc_rows
        elif table_name == "trade_executions":
            mock_table.select.return_value.eq.return_value.execute.return_value.data = kr_rows
        elif table_name == "us_trade_executions":
            mock_table.select.return_value.eq.return_value.execute.return_value.data = us_rows
        else:
            mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        return mock_table

    mock_sb = MagicMock()
    mock_sb.table.side_effect = _table_selector
    return mock_sb


@pytest.fixture
def default_config():
    return CrossMarketConfig(
        max_total_exposure_pct=0.80,
        max_single_market_pct=0.50,
        max_portfolio_mdd_pct=-0.15,
        correlation_warn_threshold=0.70,
        max_daily_loss_pct=-0.05,
    )


@pytest.fixture
def manager_factory(default_config):
    """Supabase mock을 주입한 CrossMarketRiskManager 팩토리."""
    def _factory(btc_rows=None, kr_rows=None, us_rows=None, config=None):
        mock_sb = _make_mock_supabase(btc_rows, kr_rows, us_rows)
        with patch("quant.risk.cross_market_manager.get_supabase", return_value=mock_sb):
            mgr = CrossMarketRiskManager(config=config or default_config)
        mgr._supabase = mock_sb
        return mgr
    return _factory


# ── 테스트 1: 총 노출 한도 초과 시 buy_blocked ───────────────────────────────
class TestTotalExposureLimit:
    def test_total_exposure_exceeds_limit_blocks_buy(self, manager_factory):
        """BTC+KR+US 합산 노출 > 80% → buy_blocked=True."""
        # total_capital=100M, positions=85M → exposure_pct=0.85
        btc_rows = [{"quantity": 1.0, "entry_price": 50_000_000, "highest_price": None, "status": "OPEN", "entry_krw": 50_000_000}]
        kr_rows = [{"stock_code": "005930", "quantity": 100, "price": 350_000, "result": "OPEN"}]  # 35M
        mgr = manager_factory(btc_rows=btc_rows, kr_rows=kr_rows)
        result = mgr.evaluate(total_capital=100_000_000)
        assert result.total_exposure_pct == pytest.approx(0.85, abs=0.01)
        assert result.buy_blocked is True
        assert len(result.block_reasons) > 0

    def test_total_exposure_within_limit_allows_buy(self, manager_factory):
        """총 노출 50% → buy_blocked=False."""
        kr_rows = [{"stock_code": "005930", "quantity": 100, "price": 100_000, "result": "OPEN"}]  # 10M
        mgr = manager_factory(kr_rows=kr_rows)
        result = mgr.evaluate(total_capital=100_000_000)
        assert result.total_exposure_pct == pytest.approx(0.10, abs=0.001)
        assert result.buy_blocked is False

    def test_no_positions_allows_buy(self, manager_factory):
        """포지션 없음 → buy_blocked=False."""
        mgr = manager_factory()
        result = mgr.evaluate(total_capital=100_000_000)
        assert result.buy_blocked is False
        assert result.total_exposure == 0.0


# ── 테스트 2: 마켓별 독립 비중 초과 시 경고 ──────────────────────────────────
class TestSingleMarketConcentration:
    def test_single_market_over_50pct_generates_warning(self, manager_factory):
        """BTC 단일 마켓 비중 > 50% → warnings에 해당 내용 포함."""
        btc_rows = [{"quantity": 1.0, "entry_price": 60_000_000, "highest_price": None, "status": "OPEN", "entry_krw": 60_000_000}]
        mgr = manager_factory(btc_rows=btc_rows)
        result = mgr.evaluate(total_capital=100_000_000)
        btc_warnings = [w for w in result.warnings if "btc" in w]
        assert len(btc_warnings) > 0

    def test_balanced_portfolio_no_concentration_warning(self, manager_factory):
        """BTC 30%, KR 20%, US 10% → 단일 마켓 경고 없음."""
        btc_rows = [{"quantity": 1.0, "entry_price": 30_000_000, "highest_price": None, "status": "OPEN", "entry_krw": 30_000_000}]
        kr_rows = [{"stock_code": "005930", "quantity": 100, "price": 200_000, "result": "OPEN"}]  # 20M
        us_rows = [{"symbol": "AAPL", "quantity": 10, "price": 1_000_000, "result": "OPEN"}]       # 10M
        mgr = manager_factory(btc_rows=btc_rows, kr_rows=kr_rows, us_rows=us_rows)
        result = mgr.evaluate(total_capital=100_000_000)
        assert len(result.warnings) == 0

    def test_market_weights_sum_correctly(self, manager_factory):
        """market_weights 합계가 total_exposure_pct와 일치한다."""
        btc_rows = [{"quantity": 1.0, "entry_price": 20_000_000, "highest_price": None, "status": "OPEN", "entry_krw": 20_000_000}]
        kr_rows = [{"stock_code": "005930", "quantity": 100, "price": 100_000, "result": "OPEN"}]  # 10M
        mgr = manager_factory(btc_rows=btc_rows, kr_rows=kr_rows)
        result = mgr.evaluate(total_capital=100_000_000)
        weight_sum = sum(result.market_weights.values())
        assert abs(weight_sum - result.total_exposure_pct) < 1e-4


# ── 테스트 3: evaluate() 결과 타입 및 필드 완결성 ────────────────────────────
class TestEvaluateResultStructure:
    def test_result_has_all_required_fields(self, manager_factory):
        """CrossMarketRiskResult의 필수 필드가 모두 존재한다."""
        mgr = manager_factory()
        result = mgr.evaluate(total_capital=50_000_000)
        assert hasattr(result, "total_equity")
        assert hasattr(result, "total_exposure")
        assert hasattr(result, "total_exposure_pct")
        assert hasattr(result, "buy_blocked")
        assert hasattr(result, "block_reasons")
        assert hasattr(result, "market_weights")
        assert hasattr(result, "warnings")
        assert hasattr(result, "timestamp")

    def test_market_weights_contains_all_three_markets(self, manager_factory):
        """market_weights에 btc, kr, us 모두 포함된다."""
        mgr = manager_factory()
        result = mgr.evaluate(total_capital=10_000_000)
        assert "btc" in result.market_weights
        assert "kr" in result.market_weights
        assert "us" in result.market_weights

    def test_timestamp_is_iso_format(self, manager_factory):
        """timestamp 필드가 ISO 포맷 문자열이다."""
        mgr = manager_factory()
        result = mgr.evaluate()
        assert "T" in result.timestamp  # ISO 포맷 확인


# ── 테스트 4: should_block_buy() 빠른 체크 ───────────────────────────────────
class TestShouldBlockBuy:
    def test_should_block_buy_true_when_over_exposure(self, manager_factory):
        """총 노출 초과 시 should_block_buy → True."""
        btc_rows = [{"quantity": 1.0, "entry_price": 90_000_000, "highest_price": None, "status": "OPEN", "entry_krw": 90_000_000}]
        mgr = manager_factory(btc_rows=btc_rows)
        result = mgr.should_block_buy("btc", total_capital=100_000_000)
        assert result is True

    def test_should_block_buy_false_when_within_limits(self, manager_factory):
        """노출 여유 있을 때 should_block_buy → False."""
        mgr = manager_factory()
        result = mgr.should_block_buy("kr", total_capital=100_000_000)
        assert result is False

    def test_should_block_buy_fail_open_on_exception(self, default_config):
        """evaluate 에러 발생 시 fail-open → False (매수 차단 안 함)."""
        with patch("quant.risk.cross_market_manager.get_supabase", return_value=None):
            mgr = CrossMarketRiskManager(config=default_config)
        # _load_btc_snapshot 등이 supabase=None으로 빈 snap 반환하므로 정상 동작
        # 예외를 강제로 발생시켜야 fail-open 경로 테스트
        with patch.object(mgr, "evaluate", side_effect=RuntimeError("db down")):
            result = mgr.should_block_buy("us", total_capital=100_000_000)
        assert result is False


# ── 테스트 5: Supabase None 환경(오프라인) 처리 ───────────────────────────────
class TestSupabaseNoneHandling:
    def test_no_supabase_returns_empty_snapshots(self, default_config):
        """Supabase None → 빈 snapshot, buy_blocked=False (fail-open)."""
        with patch("quant.risk.cross_market_manager.get_supabase", return_value=None):
            mgr = CrossMarketRiskManager(config=default_config)
        result = mgr.evaluate(total_capital=100_000_000)
        assert result.total_exposure == 0.0
        assert result.buy_blocked is False

    def test_supabase_error_does_not_propagate(self, default_config):
        """Supabase 쿼리 예외 → 경고 로그만, evaluate 결과 반환."""
        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("connection refused")
        with patch("quant.risk.cross_market_manager.get_supabase", return_value=mock_sb):
            mgr = CrossMarketRiskManager(config=default_config)
        # evaluate가 예외 없이 결과를 반환해야 함
        result = mgr.evaluate(total_capital=100_000_000)
        assert isinstance(result, CrossMarketRiskResult)
        assert result.buy_blocked is False
