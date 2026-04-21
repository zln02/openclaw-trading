"""스모크 테스트: KR 백테스트 파이프라인 (mock 데이터)."""
from __future__ import annotations

from unittest.mock import patch

from quant.backtest_kr import (calc_composite_score, kelly_size,
                               resolve_universe, run_backtest)

# ── 샘플 데이터 생성 헬퍼 ─────────────────────────────────────────────────────


def _make_ohlcv(n: int = 60, base_price: float = 50_000.0) -> list[dict]:
    """단순 상승 추세 가짜 일봉 (2026-01-02 ~ n일)."""
    from datetime import date, timedelta

    rows = []
    start = date(2026, 1, 2)
    price = base_price
    volume = 1_000_000
    for i in range(n):
        d = start + timedelta(days=i)
        # 주말 제외 (단순화를 위해 그냥 포함)
        close = price * (1 + 0.001 * (i % 5 - 2))  # 소폭 등락
        rows.append({
            "date": d.isoformat(),
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": volume * (1.2 if i % 3 == 0 else 0.9),
        })
        price = close
    return rows


# ── 단위 테스트 ───────────────────────────────────────────────────────────────

class TestCompositeScore:
    def test_returns_float(self):
        rows = _make_ohlcv(60)
        closes = [r["close"] for r in rows]
        vols = [r["volume"] for r in rows]
        score = calc_composite_score(closes, vols)
        assert isinstance(score, float)

    def test_range_0_to_100(self):
        rows = _make_ohlcv(60)
        closes = [r["close"] for r in rows]
        vols = [r["volume"] for r in rows]
        score = calc_composite_score(closes, vols)
        assert 0.0 <= score <= 100.0

    def test_insufficient_data_returns_zero(self):
        closes = [50_000.0] * 10
        vols = [100_000.0] * 10
        score = calc_composite_score(closes, vols)
        assert score == 0.0


class TestKellySize:
    def test_positive_edge(self):
        size = kelly_size(10_000_000, win_rate=0.6, avg_win=0.1, avg_loss=0.05)
        assert size > 0

    def test_max_single_cap(self):
        # 초기자본 1억, Kelly가 아무리 커도 3% 이하
        size = kelly_size(100_000_000, win_rate=0.9, avg_win=0.5, avg_loss=0.01)
        assert size <= 100_000_000 * 0.03 + 1  # 부동소수점 여유

    def test_zero_avg_loss(self):
        size = kelly_size(10_000_000, win_rate=0.5, avg_win=0.1, avg_loss=0.0)
        assert size == 0.0


class TestResolveUniverse:
    def test_top10_returns_10_codes(self):
        codes = resolve_universe("top10")
        assert len(codes) == 10
        assert all(isinstance(c, str) and len(c) == 6 for c in codes)

    def test_csv_codes(self):
        codes = resolve_universe("005930,000660,035420")
        assert codes == ["005930", "000660", "035420"]

    def test_single_code(self):
        codes = resolve_universe("005930")
        assert codes == ["005930"]


class TestRunBacktest:
    """3종목 × 10일치 mock 데이터로 스모크 테스트."""

    CODES = ["005930", "000660", "035420"]
    START = "2026-01-10"
    END = "2026-01-24"

    def _mock_load(self, code: str, start: str, end: str) -> list[dict]:
        """load_ohlcv를 대체 — 60행 가짜 데이터 반환 (warm-up 포함)."""
        return _make_ohlcv(60, base_price=50_000.0)

    def test_backtest_returns_expected_keys(self):
        with patch("quant.backtest_kr.load_ohlcv", side_effect=self._mock_load):
            result = run_backtest(
                codes=self.CODES,
                start=self.START,
                end=self.END,
                initial_capital=10_000_000,
            )

        assert "period" in result
        assert "universe" in result
        assert "trades" in result
        assert "metrics" in result

    def test_metrics_keys_present(self):
        with patch("quant.backtest_kr.load_ohlcv", side_effect=self._mock_load):
            result = run_backtest(
                codes=self.CODES,
                start=self.START,
                end=self.END,
                initial_capital=10_000_000,
            )

        m = result["metrics"]
        for key in ("total_return", "sharpe", "max_drawdown", "win_rate", "n_trades", "avg_holding_days"):
            assert key in m, f"메트릭 키 누락: {key}"

    def test_no_data_returns_error(self):
        with patch("quant.backtest_kr.load_ohlcv", return_value=[]):
            result = run_backtest(
                codes=self.CODES,
                start=self.START,
                end=self.END,
            )
        assert "error" in result

    def test_capital_is_non_negative(self):
        with patch("quant.backtest_kr.load_ohlcv", side_effect=self._mock_load):
            result = run_backtest(
                codes=self.CODES,
                start=self.START,
                end=self.END,
                initial_capital=10_000_000,
            )
        assert result["metrics"]["final_capital"] >= 0
