# 텔레그램 봇 명령어 확장 설계 문서
작성일: 2026-02-28
대상 파일: `stocks/telegram_bot.py`

---

## 현재 구현된 명령어

| 명령어 | 상태 | 설명 |
|--------|------|------|
| `/status` | ✅ 구현됨 | KR 계좌 현황 + 보유종목 |
| `/stop` | ✅ 구현됨 | 자동매매 중지 플래그 설정 |
| `/resume` (`/start`) | ✅ 구현됨 | 자동매매 중지 플래그 해제 |
| `/sell_all` | ✅ 구현됨 | 전량 매도 (2단계 확인) |
| `/CONFIRM_SELL_ALL` | ✅ 구현됨 | 전량 매도 확인 |
| `/CANCEL_SELL_ALL` | ✅ 구현됨 | 전량 매도 취소 |

---

## 추가 설계: 신규 명령어

### 1. `/status` — 현재 구현 확장

**현재 문제점:**
- KR 계좌만 표시 (BTC, US 주식 미포함)
- 계좌 조회 실패 시 에러 메시지만 반환

**확장 설계:**
```
/status          # 전체 시장 요약 (BTC + KR + US)
/status kr       # KR 주식 상세 (현재 동작)
/status btc      # BTC 포지션 + 복합 스코어
/status us       # US 주식 드라이런 포지션
```

**응답 포맷 (전체 요약):**
```
📊 OpenClaw 전체 현황
─────────────────────
🪙 BTC
  포지션: 보유 / 미보유
  복합 스코어: 52.3 / 100
  현재가: 98,500,000원
  손익: +2.3% (+230,000원)

📈 KR 주식 (키움 모의)
  예수금: 5,230,000원
  보유: 3종목
  평가손익: +1.2% (+62,000원)

🌍 US 주식 (DRY-RUN)
  가상자본: $10,000
  보유: 2종목
  평가손익: +0.8% (+$80)

⏱ 2026-02-28 16:30:00 KST
```

---

### 2. `/pause` — 매매 일시정지 (개선된 /stop)

**목적:** 현재 `/stop`은 플래그만 설정하고 에이전트 연동이 미완성. `/pause`는 명확한 일시정지를 의미.

**동작 설계:**
1. `PAUSE_TRADING` 파일 생성 (`/home/wlsdud5035/.openclaw/workspace/PAUSE_TRADING`)
2. 각 에이전트(btc_trading_agent, stock_trading_agent, us_stock_trading_agent)가 사이클 시작 시 파일 존재 여부 확인
3. 파일 존재 시 → 매매 스킵, 텔레그램 알림 없이 다음 사이클 대기

**응답:**
```
⏸ 자동매매 일시정지
─────────────────────
BTC 에이전트: 정지 예약
KR 에이전트:  정지 예약
US 에이전트:  정지 예약

※ 현재 진행 중인 사이클은 완료 후 정지됩니다.
재개: /resume
```

**에이전트 연동 코드 (각 에이전트 사이클 시작부에 추가):**
```python
PAUSE_FLAG = Path("/home/wlsdud5035/.openclaw/workspace/PAUSE_TRADING")
if PAUSE_FLAG.exists():
    log.info("Trading paused by telegram command. Skipping cycle.")
    return
```

---

### 3. `/resume` — 매매 재개 (기존 구현 개선)

**현재 문제점:**
- `/resume`이 구현되어 있지만 실제 에이전트 연동 없음
- `/start`와 동일 처리 (텔레그램 `/start`와 충돌 가능)

**개선 설계:**
1. `PAUSE_TRADING` + `STOP_TRADING` 두 파일 모두 삭제
2. 확인 메시지에 현재 에이전트 상태 포함

**응답:**
```
▶ 자동매매 재개
─────────────────────
PAUSE 플래그: 해제 ✅
STOP 플래그:  해제 ✅

다음 크론 사이클부터 자동매매가 재개됩니다.
BTC: 5분 후
KR:  다음 10분 사이클
US:  다음 분석 사이클
```

---

### 4. `/health` — 시스템 헬스체크

**목적:** 각 컴포넌트의 생존 여부를 확인하는 종합 헬스체크

**확인 항목:**
1. Supabase 연결 상태
2. 각 에이전트 마지막 실행 시간 (log 파일 기준)
3. 텔레그램 봇 응답성
4. API 연결 상태 (Upbit ping, 키움 토큰 유효성)
5. 매매 정지 플래그 상태

**구현 설계:**
```python
def get_health_text() -> str:
    from common.config import (
        BTC_LOG, STOCK_TRADING_LOG, US_TRADING_LOG,
        OPENCLAW_ROOT
    )
    import time, os

    def check_log_freshness(log_path: Path, threshold_minutes: int = 15) -> str:
        """로그 파일의 마지막 수정 시간으로 에이전트 생존 여부 확인"""
        if not log_path.exists():
            return "❌ 로그 없음"
        age_minutes = (time.time() - log_path.stat().st_mtime) / 60
        if age_minutes < threshold_minutes:
            return f"✅ {age_minutes:.0f}분 전"
        return f"⚠️ {age_minutes:.0f}분 전 (미활성)"

    pause_flag = Path(".../PAUSE_TRADING")
    stop_flag = Path(".../STOP_TRADING")

    lines = [
        "🏥 <b>시스템 헬스체크</b>",
        "",
        "📊 에이전트 상태:",
        f"  BTC:      {check_log_freshness(BTC_LOG, threshold_minutes=10)}",
        f"  KR 주식:  {check_log_freshness(STOCK_TRADING_LOG, threshold_minutes=15)}",
        f"  US 주식:  {check_log_freshness(US_TRADING_LOG, threshold_minutes=60)}",
        "",
        "🚦 제어 플래그:",
        f"  PAUSE: {'⏸ 설정됨' if pause_flag.exists() else '▶ 없음'}",
        f"  STOP:  {'⏹ 설정됨' if stop_flag.exists() else '▶ 없음'}",
        "",
        "💾 DB 연결:",
        # supabase.table("...").select("count(*)") 로 핑
        f"  Supabase: (연결 테스트 결과)",
    ]
    return "\n".join(lines)
```

**응답 예시:**
```
🏥 시스템 헬스체크
─────────────────────
📊 에이전트 상태:
  BTC:      ✅ 3분 전
  KR 주식:  ✅ 8분 전
  US 주식:  ⚠️ 45분 전 (미활성)

🚦 제어 플래그:
  PAUSE: ▶ 없음
  STOP:  ▶ 없음

💾 DB 연결:
  Supabase: ✅ 응답 정상

🖥 서버:
  CPU: 23%
  MEM: 45%
  디스크: 12GB 여유

⏱ 2026-02-28 16:30:00 KST
```

**구현 의존성:**
```python
import psutil  # requirements.txt에 이미 포함
```

---

### 5. `/force_sell` — 강제 매도 (안전장치 강화된 버전)

**현재 `/sell_all`과의 차이점:**
- `/sell_all` → KR 주식만 전량 매도
- `/force_sell` → 마켓(BTC/KR/US) 선택 가능, 개별 종목 선택 가능

**설계:**
```
/force_sell          # 시장 선택 메뉴 표시
/force_sell btc      # BTC 포지션 청산
/force_sell kr       # KR 전량 매도 (현재 /sell_all과 동일)
/force_sell kr 005930  # KR 특정 종목(삼성전자) 매도
```

**동작 흐름:**
```
사용자: /force_sell kr

봇: ⚠️ KR 전량 매도 확인
    ─────────────────────
    대상 종목:
      삼성전자: 10주 (평단 72,000원)
      SK하이닉스: 5주 (평단 185,000원)

    예상 시장가 청산가:
      삼성전자: ~720,000원
      SK하이닉스: ~925,000원

    [🔴 전량 매도 실행] [취소]

사용자: 전량 매도 실행 클릭

봇: ✅ 삼성전자 10주 매도 완료
    ✅ SK하이닉스 5주 매도 완료
    ─────────────────────
    총 청산금액: ~1,645,000원
```

**안전장치:**
1. 2단계 확인 (현재와 동일하게 유지)
2. 마지막 확인 시 실시간 현재가 재표시
3. BTC 청산 시 추가 30초 대기 + 재확인 메시지
4. US 주식은 DRY-RUN이므로 실제 주문 없음 (가상 청산만)

---

## 인라인 키보드 확장 설계

현재 키보드:
```
[⏹ 자동매매 중지] [💥 전량 매도]
[📊 상태 확인]
```

확장 키보드:
```
[📊 전체 상태]  [🏥 헬스체크]
[⏸ 일시정지]   [▶ 재개]
[💥 강제매도▼]
```

`/force_sell` 선택 시 하위 메뉴:
```
[🪙 BTC 청산]  [📈 KR 전량]  [🌍 US 청산]
[← 뒤로]
```

---

## 구현 파일 수정 계획

**수정 대상:** `stocks/telegram_bot.py`

**추가할 함수 목록:**
```python
def get_full_status_text() -> str: ...          # 전체 시장 요약
def get_btc_status_text() -> str: ...           # BTC 상태
def get_us_status_text() -> str: ...            # US 상태
def get_health_text() -> str: ...               # 헬스체크
def set_pause_flag() -> None: ...               # PAUSE 플래그 설정
def clear_pause_flag() -> None: ...             # PAUSE 플래그 해제
def handle_force_sell(market: str, code: str | None, chat_id: str) -> None: ...
def handle_force_sell_btc(chat_id: str) -> None: ...
def build_extended_keyboard() -> dict: ...      # 확장 인라인 키보드
```

**`handle_command()` 확장:**
```python
elif cmd.startswith("/health"):
    text = get_health_text()
    send_message(text, chat_id, reply_markup=build_extended_keyboard())
elif cmd.startswith("/pause"):
    set_pause_flag()
    send_message("⏸ 자동매매 일시정지 설정 완료", chat_id, ...)
elif cmd.startswith("/force_sell"):
    parts = cmd.split()
    market = parts[1] if len(parts) > 1 else None
    code = parts[2] if len(parts) > 2 else None
    handle_force_sell(market, code, chat_id)
```

---

## 주의사항 및 리스크

1. **BTC 강제청산** — 실거래이므로 반드시 3단계 확인 (기존 2단계보다 강화)
2. **US 강제청산** — DRY-RUN이므로 Supabase 가상 포지션만 CLOSED 처리, 실주문 없음
3. **`/pause` vs `/stop`** — 기존 `/stop`은 유지하되 deprecated 표시. 신규 구현은 `/pause`로 통일
4. **동시성 문제** — 에이전트가 매매 중일 때 `/force_sell` 실행 시 충돌 가능. 플래그 파일 방식으로 해결
5. **권한 관리** — 현재 `TG_CHAT` 화이트리스트 방식 유지. `/force_sell`, `/force_sell btc` 는 추가 PIN 확인 고려

---

## 다음 단계

- [ ] `handle_command()`에 신규 명령어 분기 추가
- [ ] `get_health_text()` 구현 (psutil + 로그 파일 freshness 체크)
- [ ] 각 에이전트(btc, kr, us)에 `PAUSE_TRADING` 플래그 파일 체크 로직 추가
- [ ] `/force_sell btc` 구현 (Upbit API pyupbit.sell_market_order 활용)
- [ ] 인라인 키보드 확장 (`build_extended_keyboard()`)
- [ ] 통합 테스트: `tests/test_phase18_monitoring.py`에 텔레그램 명령어 테스트 추가
