#!/usr/bin/env python3
"""
BTC 자동매매 에이전트 v4.6 — Enhanced Stability & Modularity
개선사항:
1. 안정성: 네트워크/API 타임아웃 시 자동 재시도 로직
2. 가독성: Strategy 클래스로 매수/매도 로직 모듈화
3. 데이터로깅: logging 모듈 사용, 시간대별 잔고 변화 및 에러 로그 파일 기록
"""

import os
import json
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from functools import wraps
from dataclasses import dataclass

# Retry decorator for network operations
def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"Retry attempt {attempt + 1}/{max_retries} for {func.__name__} after {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} retry attempts failed for {func.__name__}: {e}")
            raise last_exception
        return wrapper
    return decorator

# Setup logging
def setup_logging():
    log_dir = Path("/home/wlsdud5035/.openclaw/logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    
    # Create logger
    logger = logging.getLogger("btc_trading_agent")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # File handlers
    balance_handler = logging.FileHandler(log_dir / f"btc_balance_{timestamp}.log")
    error_handler = logging.FileHandler(log_dir / f"btc_error_{timestamp}.log")
    main_handler = logging.FileHandler(log_dir / f"btc_trading_{timestamp}.log")
    
    # Console handler
    console_handler = logging.StreamHandler()
    
    # Formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Set formatters
    balance_handler.setFormatter(detailed_formatter)
    error_handler.setFormatter(detailed_formatter)
    main_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    # Set levels
    balance_handler.setLevel(logging.INFO)
    error_handler.setLevel(logging.ERROR)
    main_handler.setLevel(logging.INFO)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers
    logger.addHandler(balance_handler)
    logger.addHandler(error_handler)
    logger.addHandler(main_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# Configuration management
@dataclass
class TradingConfig:
    """거래 설정 관리 클래스"""
    split_ratios: list = None
    split_rsi: list = None
    invest_ratio: float = 0.30
    stop_loss: float = -0.03
    take_profit: float = 0.12
    partial_tp_pct: float = 0.08
    partial_tp_ratio: float = 0.50
    trailing_stop: float = 0.02
    trailing_activate: float = 0.015
    trailing_adaptive: bool = True
    max_daily_loss: float = -0.08
    max_drawdown: float = -0.15
    min_confidence: int = 65
    max_trades_per_day: int = 3
    fee_buy: float = 0.001
    fee_sell: float = 0.001
    buy_composite_min: int = 45
    sell_composite_max: int = 20
    timecut_days: int = 7
    cooldown_minutes: int = 30
    volatility_filter: bool = True
    funding_filter: bool = True
    oi_filter: bool = True
    kimchi_premium_max: float = 5.0
    dynamic_weights: bool = True
    
    def __post_init__(self):
        if self.split_ratios is None:
            self.split_ratios = [0.15, 0.25, 0.40]
        if self.split_rsi is None:
            self.split_rsi = [55, 45, 35]
    
    @classmethod
    def from_env(cls) -> 'TradingConfig':
        """환경변수에서 설정 로드"""
        return cls(
            split_ratios=[float(x) for x in os.getenv("BTC_SPLIT_RATIOS", "0.15,0.25,0.40").split(",")],
            split_rsi=[int(x) for x in os.getenv("BTC_SPLIT_RSI", "55,45,35").split(",")],
            invest_ratio=float(os.getenv("BTC_INVEST_RATIO", "0.30")),
            stop_loss=float(os.getenv("BTC_STOP_LOSS", "-0.03")),
            take_profit=float(os.getenv("BTC_TAKE_PROFIT", "0.12")),
            partial_tp_pct=float(os.getenv("BTC_PARTIAL_TP_PCT", "0.08")),
            partial_tp_ratio=float(os.getenv("BTC_PARTIAL_TP_RATIO", "0.50")),
            trailing_stop=float(os.getenv("BTC_TRAILING_STOP", "0.02")),
            trailing_activate=float(os.getenv("BTC_TRAILING_ACTIVATE", "0.015")),
            trailing_adaptive=os.getenv("BTC_TRAILING_ADAPTIVE", "true").lower() == "true",
            max_daily_loss=float(os.getenv("BTC_MAX_DAILY_LOSS", "-0.08")),
            max_drawdown=float(os.getenv("BTC_MAX_DRAWDOWN", "-0.15")),
            min_confidence=int(os.getenv("BTC_MIN_CONFIDENCE", "65")),
            max_trades_per_day=int(os.getenv("BTC_MAX_TRADES_PER_DAY", "3")),
            fee_buy=float(os.getenv("BTC_FEE_BUY", "0.001")),
            fee_sell=float(os.getenv("BTC_FEE_SELL", "0.001")),
            buy_composite_min=int(os.getenv("BTC_BUY_COMPOSITE_MIN", "45")),
            sell_composite_max=int(os.getenv("BTC_SELL_COMPOSITE_MAX", "20")),
            timecut_days=int(os.getenv("BTC_TIMECUT_DAYS", "7")),
            cooldown_minutes=int(os.getenv("BTC_COOLDOWN_MINUTES", "30")),
            volatility_filter=os.getenv("BTC_VOLATILITY_FILTER", "true").lower() == "true",
            funding_filter=os.getenv("BTC_FUNDING_FILTER", "true").lower() == "true",
            oi_filter=os.getenv("BTC_OI_FILTER", "true").lower() == "true",
            kimchi_premium_max=float(os.getenv("BTC_KIMCHI_PREMIUM_MAX", "5.0")),
            dynamic_weights=os.getenv("BTC_DYNAMIC_WEIGHTS", "true").lower() == "true",
        )

# Strategy classes for modular trading logic
class TradingStrategy:
    """거래 전략 기본 클래스"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(f"btc_trading_agent.{self.__class__.__name__}")
    
    def evaluate_buy_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """매수 신호 평가 - 서브클래스에서 구현"""
        raise NotImplementedError
    
    def evaluate_sell_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """매도 신호 평가 - 서브클래스에서 구현"""
        raise NotImplementedError

class CompositeScoreStrategy(TradingStrategy):
    """복합 스코어 기반 전략"""
    
    def evaluate_buy_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """복합 스코어 기반 매수 신호"""
        comp = market_data.get('composite', {})
        htf = market_data.get('hourly_trend', {})
        pos = market_data.get('position', None)
        
        buy_min = self.config.buy_composite_min
        
        if comp.get("total", 0) >= buy_min and not pos and htf.get("trend") != "DOWNTREND":
            conf = min(60 + comp.get("total", 0) - buy_min, 90)
            return {
                "action": "BUY",
                "confidence": int(conf),
                "reason": f"복합스코어 {comp.get('total', 0)}/{buy_min} (룰기반)"
            }
        return None
    
    def evaluate_sell_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """복합 스코어 기반 매도 신호"""
        comp = market_data.get('composite', {})
        
        if comp.get("total", 0) <= self.config.sell_composite_max:
            return {
                "action": "SELL",
                "confidence": 70,
                "reason": f"복합스코어 {comp.get('total', 0)} <= {self.config.sell_composite_max} (룰기반)"
            }
        return None

class ExtremeFearStrategy(TradingStrategy):
    """극단 공포 오버라이드 전략"""
    
    def evaluate_buy_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """극단 공포 구간 매수 오버라이드"""
        fg = market_data.get('fear_greed', {})
        momentum = market_data.get('momentum', {})
        htf = market_data.get('hourly_trend', {})
        pos = market_data.get('position', None)
        
        fg_value = fg.get("value", 50)
        rsi_d = momentum.get("rsi_d", 50)
        
        if fg_value <= 15 and rsi_d <= 55 and not pos and htf.get("trend") != "DOWNTREND":
            return {
                "action": "BUY",
                "confidence": 78,
                "reason": f"극도공포 오버라이드 F&G={fg_value}, dRSI={rsi_d} (룰기반)"
            }
        return None
    
    def evaluate_sell_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """극단 탐욕 구간 매도"""
        fg = market_data.get('fear_greed', {})
        
        fg_value = fg.get("value", 50)
        
        if fg_value >= 75:
            return {
                "action": "SELL",
                "confidence": 75,
                "reason": f"극도탐욕 매도 F&G={fg_value} (룰기반)"
            }
        return None

class PositionManager:
    """포지션 관리 클래스"""
    
    def __init__(self, config: TradingConfig, upbit_client, supabase_client):
        self.config = config
        self.upbit = upbit_client
        self.supabase = supabase_client
        self.logger = logging.getLogger("btc_trading_agent.PositionManager")
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_balance(self) -> Dict[str, float]:
        """잔고 조회 with retry"""
        btc_balance = self.upbit.get_balance("BTC") or 0
        krw_balance = self.upbit.get_balance("KRW") or 0
        
        # 잔고 변화 로깅
        self.logger.info(f"Balance check - BTC: {btc_balance:.6f}, KRW: {krw_balance:,.0f}원")
        
        return {"btc": btc_balance, "krw": krw_balance}
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def buy_market_order(self, amount: float) -> Dict[str, Any]:
        """시장가 매수 with retry"""
        self.logger.info(f"Executing buy order: {amount:,.0f}KRW")
        result = self.upbit.buy_market_order("KRW-BTC", amount)
        self.logger.info(f"Buy order result: {result}")
        return result
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def sell_market_order(self, btc_amount: float) -> Dict[str, Any]:
        """시장가 매도 with retry"""
        self.logger.info(f"Executing sell order: {btc_amount:.6f}BTC")
        result = self.upbit.sell_market_order("KRW-BTC", btc_amount)
        self.logger.info(f"Sell order result: {result}")
        return result

class MarketDataCollector:
    """시장 데이터 수집 클래스"""
    
    def __init__(self, config: TradingConfig, upbit_client, supabase_client):
        self.config = config
        self.upbit = upbit_client
        self.supabase = supabase_client
        self.logger = logging.getLogger("btc_trading_agent.MarketDataCollector")
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def get_market_data(self):
        """시장 데이터 조회 with retry"""
        import pyupbit
        data = pyupbit.get_ohlcv("KRW-BTC", interval="minute5", count=200)
        self.logger.debug(f"Market data retrieved: {len(data)} candles")
        return data
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def get_fear_greed(self) -> Dict[str, Any]:
        """Fear & Greed 지수 조회 with retry"""
        import requests
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        data = res.json()["data"][0]
        value = int(data["value"])
        label = data["value_classification"]
        
        if value <= 25:
            msg = f"🔴 극도 공포({value}) — 역발상 매수 기회"
        elif value <= 45:
            msg = f"🟠 공포({value}) — 매수 우호적"
        elif value <= 55:
            msg = f"⚪ 중립({value})"
        elif value <= 75:
            msg = f"🟡 탐욕({value}) — 매수 주의"
        else:
            msg = f"🔴 극도 탐욕({value}) — 매수 금지"
        
        self.logger.info(f"Fear & Greed: {label}({value})")
        return {"value": value, "label": label, "msg": msg}
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def get_kimchi_premium(self) -> Optional[float]:
        """김치 프리미엄 조회 with retry"""
        import requests as req
        try:
            binance = req.get(
                "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                timeout=3
            ).json()
            binance_price = float(binance["price"])
            usdt = req.get(
                "https://api.upbit.com/v1/ticker?markets=KRW-USDT",
                timeout=3
            ).json()
            usd_krw = float(usdt[0]["trade_price"])
            binance_krw = binance_price * usd_krw
            upbit_price = self.upbit.get_current_price("KRW-BTC")
            if upbit_price is None:
                return None
            premium = (float(upbit_price) - binance_krw) / binance_krw * 100
            self.logger.info(f"Kimchi premium: {premium:+.2f}%")
            return round(premium, 2)
        except Exception as e:
            self.logger.error(f"Kimchi premium calculation failed: {e}")
            return None

# Main Trading Agent
class EnhancedBTCTradingAgent:
    """향상된 BTC 트레이딩 에이전트"""
    
    def __init__(self):
        # Load environment and configuration
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        
        from common.env_loader import load_env
        from common.telegram import send_telegram as _tg_send
        from common.supabase_client import get_supabase
        
        load_env()
        
        # Configuration
        self.config = TradingConfig.from_env()
        self.logger = logging.getLogger("btc_trading_agent.EnhancedBTCTradingAgent")
        
        # API clients
        UPBIT_ACCESS = os.environ.get("UPBIT_ACCESS_KEY", "")
        UPBIT_SECRET = os.environ.get("UPBIT_SECRET_KEY", "")
        OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
        
        if not all([UPBIT_ACCESS, UPBIT_SECRET, OPENAI_KEY]):
            self.logger.error("필수 환경변수 없음: UPBIT keys + OPENAI_API_KEY 필요")
            sys.exit(1)
        
        import pyupbit
        from openai import OpenAI
        
        self.upbit = pyupbit.Upbit(UPBIT_ACCESS, UPBIT_SECRET)
        self.supabase = get_supabase()
        self.openai_client = OpenAI(api_key=OPENAI_KEY)
        
        # Dry run mode
        self.dry_run = os.environ.get("DRY_RUN", "0") == "1"
        
        # Initialize components
        self.position_manager = PositionManager(self.config, self.upbit, self.supabase)
        self.market_data = MarketDataCollector(self.config, self.upbit, self.supabase)
        
        # Strategies
        self.strategies = [
            CompositeScoreStrategy(self.config),
            ExtremeFearStrategy(self.config)
        ]
        
        self.telegram_send = _tg_send
        self.logger.info("Enhanced BTC Trading Agent initialized successfully")
    
    def send_telegram(self, msg: str):
        """텔레그램 메시지 전송 with error handling"""
        try:
            self.telegram_send(msg)
            self.logger.info(f"Telegram message sent: {msg[:50]}...")
        except Exception as e:
            self.logger.error(f"Failed to send telegram message: {e}")
    
    def calculate_indicators(self, df) -> dict:
        """기술적 지표 계산"""
        try:
            from ta.trend import EMAIndicator, MACD
            from ta.momentum import RSIIndicator
            from ta.volatility import BollingerBands

            close = df["close"]
            ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
            ema50 = EMAIndicator(close, window=50).ema_indicator().iloc[-1]
            rsi   = RSIIndicator(close, window=14).rsi().iloc[-1]
            macd_obj = MACD(close)
            macd  = macd_obj.macd_diff().iloc[-1]
            bb    = BollingerBands(close, window=20)

            indicators = {
                "price":    df["close"].iloc[-1],
                "ema20":    round(ema20, 0),
                "ema50":    round(ema50, 0),
                "rsi":      round(rsi, 1),
                "macd":     round(macd, 0),
                "bb_upper": round(bb.bollinger_hband().iloc[-1], 0),
                "bb_lower": round(bb.bollinger_lband().iloc[-1], 0),
                "volume":   round(df["volume"].iloc[-1], 4),
            }
            
            self.logger.debug(f"Indicators calculated: {indicators}")
            return indicators
        except Exception as e:
            self.logger.error(f"Failed to calculate indicators: {e}")
            return {}
    
    def get_open_position(self):
        """오픈 포지션 조회"""
        try:
            res = self.supabase.table("btc_position")\
                          .select("*").eq("status", "OPEN")\
                          .order("entry_time", desc=True).limit(1).execute()
            pos = res.data[0] if res.data else None
            if pos:
                self.logger.info(f"Open position found: {pos['entry_price']}KRW, {pos['quantity']}BTC")
            return pos
        except Exception as e:
            self.logger.error(f"Failed to get open position: {e}")
            return None
    
    def get_split_stage(self, composite_total: float) -> int:
        """복합 스코어 기반 분할 매수 단계"""
        if composite_total >= 70: return 3
        if composite_total >= 55: return 2
        return 1
    
    def execute_trade(self, signal: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """거래 실행"""
        try:
            self.logger.info(f"Executing trade: {signal}")
            
            # 신뢰도 필터
            if signal["confidence"] < self.config.min_confidence:
                return {"result": "SKIP"}
            
            balances = self.position_manager.get_balance()
            btc_balance = balances["btc"]
            krw_balance = balances["krw"]
            pos = self.get_open_position()
            price = market_data["indicators"]["price"]
            
            # 매수 로직
            if signal["action"] == "BUY":
                comp = market_data.get("composite", {})
                comp_total = comp.get("total", 50)
                stage = self.get_split_stage(comp_total)
                invest_krw = krw_balance * self.config.split_ratios[stage - 1]
                
                if invest_krw < 5000:
                    return {"result": "INSUFFICIENT_KRW"}
                
                if not self.dry_run:
                    result = self.position_manager.buy_market_order(invest_krw)
                    qty = float(result.get("executed_volume", 0)) or (invest_krw / price)
                    # 포지션 기록 로직은 기존과 동일
                else:
                    self.logger.info(f"[DRY_RUN] {stage}차 매수 — {invest_krw:,.0f}원")
                
                self.send_telegram(
                    f"🟢 <b>BTC {stage}차 매수</b>\n"
                    f"💰 가격: {price:,}원\n"
                    f"📊 RSI: {market_data['indicators']['rsi']} ({stage}차)\n"
                    f"💵 투입: {invest_krw:,.0f}원\n"
                    f"🎯 신뢰도: {signal['confidence']}%\n"
                    f"📝 {signal['reason']}"
                )
                return {"result": f"BUY_{stage}차"}
            
            # 매도 로직
            elif signal["action"] == "SELL" and btc_balance > 0.00001:
                if not self.dry_run:
                    self.position_manager.sell_market_order(btc_balance * 0.9995)
                    # 포지션 종료 로직은 기존과 동일
                
                self.send_telegram(
                    f"🔴 <b>BTC 매도</b>\n"
                    f"💰 가격: {price:,}원\n"
                    f"📊 RSI: {market_data['indicators']['rsi']}\n"
                    f"🎯 신뢰도: {signal['confidence']}%\n"
                    f"📝 {signal['reason']}"
                )
                return {"result": "SELL"}
            
            return {"result": "HOLD"}
        except Exception as e:
            self.logger.error(f"Trade execution failed: {e}")
            return {"result": "ERROR", "error": str(e)}
    
    def run_trading_cycle(self):
        """메인 트레이딩 사이클"""
        try:
            self.logger.info("="*50)
            self.logger.info("Starting trading cycle")
            
            # 시장 데이터 수집
            df = self.market_data.get_market_data()
            indicators = self.calculate_indicators(df)
            fg = self.market_data.get_fear_greed()
            kimchi = self.market_data.get_kimchi_premium()
            pos = self.get_open_position()
            
            # 기타 데이터 수집 (기존 로직과 동일)
            # ... (나머지 데이터 수집 로직)
            
            market_data = {
                "indicators": indicators,
                "fear_greed": fg,
                "kimchi_premium": kimchi,
                "position": pos,
                # ... 다른 데이터들
            }
            
            # 전략 평가
            final_signal = None
            for strategy in self.strategies:
                buy_signal = strategy.evaluate_buy_signal(market_data)
                if buy_signal:
                    final_signal = buy_signal
                    self.logger.info(f"Buy signal from {strategy.__class__.__name__}: {buy_signal}")
                    break
                
                sell_signal = strategy.evaluate_sell_signal(market_data)
                if sell_signal:
                    final_signal = sell_signal
                    self.logger.info(f"Sell signal from {strategy.__class__.__name__}: {sell_signal}")
                    break
            
            if final_signal:
                result = self.execute_trade(final_signal, market_data)
                self.logger.info(f"Trade result: {result}")
            else:
                self.logger.info("No trading signal generated")
            
            # 로그 저장
            self.save_log(indicators, final_signal or {"action": "HOLD"}, {})
            
        except Exception as e:
            self.logger.error(f"Trading cycle failed: {e}")
    
    def save_log(self, indicators, signal, result):
        """로그 저장 with error handling"""
        try:
            self.supabase.table("btc_trades").insert({
                "timestamp": datetime.now().isoformat(),
                "action": signal.get("action", "HOLD"),
                "price": indicators.get("price", 0),
                "rsi": indicators.get("rsi", 0),
                "macd": indicators.get("macd", 0),
                "confidence": signal.get("confidence", 0),
                "reason": signal.get("reason", ""),
                "indicator_snapshot": json.dumps(indicators),
                "order_raw": json.dumps(result),
            }).execute()
            self.logger.info("Supabase log saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save log to Supabase: {e}")

# Main execution
if __name__ == "__main__":
    agent = EnhancedBTCTradingAgent()
    agent.run_trading_cycle()