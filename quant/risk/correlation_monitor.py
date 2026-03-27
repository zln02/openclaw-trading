#!/usr/bin/env python3
"""포트폴리오 상관관계 모니터.

3개 시장(BTC/KR/US) 포지션의 방향성 상관관계를 추적하고,
과도한 집중 시 텔레그램 경고를 보낸다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from common.env_loader import load_env
from common.logger import get_logger
from common.supabase_client import get_supabase

load_env()
log = get_logger("correlation_monitor")

KST = timezone(timedelta(hours=9))


def get_btc_exposure() -> dict:
    """BTC 포지션 노출도 조회."""
    try:
        sb = get_supabase()
        if not sb:
            return {"market": "BTC", "exposed": False, "direction": "NONE", "size_pct": 0.0}
        res = sb.table("btc_position").select("*").eq("status", "OPEN").execute()
        if res.data:
            pos = res.data[0]
            return {
                "market": "BTC",
                "exposed": True,
                "direction": "LONG",
                "size_pct": float(pos.get("invest_ratio", 0.3) or 0.3) * 100,
                "entry_price": pos.get("entry_price"),
            }
        return {"market": "BTC", "exposed": False, "direction": "NONE", "size_pct": 0.0}
    except Exception as e:
        log.warning(f"BTC 노출도 조회 실패: {e}")
        return {"market": "BTC", "exposed": False, "direction": "NONE", "size_pct": 0.0}


def get_kr_exposure() -> dict:
    """KR 주식 포지션 노출도 조회."""
    try:
        sb = get_supabase()
        if not sb:
            return {"market": "KR", "exposed": False, "count": 0, "total_pct": 0.0, "sectors": []}
        res = (
            sb.table("trade_executions")
            .select("stock_name,sector,quantity,entry_price,result,market")
            .eq("result", "OPEN")
            .eq("market", "KR")
            .execute()
        )
        positions = res.data or []
        sectors = list(set(p.get("sector", "unknown") for p in positions))
        total_value = sum(
            float(p.get("quantity", 0) or 0) * float(p.get("entry_price", 0) or 0)
            for p in positions
        )
        return {
            "market": "KR",
            "exposed": len(positions) > 0,
            "count": len(positions),
            "direction": "LONG" if positions else "NONE",
            "total_value": total_value,
            "sectors": sectors,
        }
    except Exception as e:
        log.warning(f"KR 노출도 조회 실패: {e}")
        return {"market": "KR", "exposed": False, "count": 0, "total_pct": 0.0, "sectors": []}


def get_us_exposure() -> dict:
    """US 주식 포지션 노출도 조회."""
    try:
        sb = get_supabase()
        if not sb:
            return {"market": "US", "exposed": False, "count": 0, "sectors": []}
        res = (
            sb.table("trade_executions")
            .select("stock_name,sector,quantity,entry_price,result,market")
            .eq("result", "OPEN")
            .eq("market", "US")
            .execute()
        )
        positions = res.data or []
        sectors = list(set(p.get("sector", "unknown") for p in positions))
        return {
            "market": "US",
            "exposed": len(positions) > 0,
            "count": len(positions),
            "direction": "LONG" if positions else "NONE",
            "sectors": sectors,
        }
    except Exception as e:
        log.warning(f"US 노출도 조회 실패: {e}")
        return {"market": "US", "exposed": False, "count": 0, "sectors": []}


def check_concentration_risk() -> dict[str, Any]:
    """포트폴리오 집중도 리스크 체크."""
    btc = get_btc_exposure()
    kr = get_kr_exposure()
    us = get_us_exposure()

    exposures = [btc, kr, us]
    long_count = sum(1 for exposure in exposures if exposure.get("direction") == "LONG")
    warnings: list[str] = []

    if long_count == 3:
        warnings.append("⚠️ 3개 시장(BTC/KR/US) 모두 LONG — 상관관계 리스크 높음")

    kr_sectors = kr.get("sectors", [])
    if len(kr_sectors) > 0 and kr.get("count", 0) > 2 and len(kr_sectors) == 1:
        warnings.append(f"⚠️ KR 포지션 {kr['count']}개 모두 같은 섹터: {kr_sectors[0]}")

    result = {
        "timestamp": datetime.now(KST).isoformat(),
        "btc": btc,
        "kr": kr,
        "us": us,
        "long_count": long_count,
        "warnings": warnings,
        "risk_level": "HIGH" if long_count == 3 else ("MEDIUM" if long_count == 2 else "LOW"),
    }

    if warnings:
        log.warning(f"상관관계 경고: {warnings}")
        try:
            from common.telegram import send_telegram

            msg = "🔴 포트폴리오 집중도 경고\n" + "\n".join(warnings)
            msg += f"\n\nBTC: {'LONG' if btc['exposed'] else 'FLAT'}"
            msg += f"\nKR: {kr.get('count', 0)}종목 {'LONG' if kr['exposed'] else 'FLAT'}"
            msg += f"\nUS: {us.get('count', 0)}종목 {'LONG' if us['exposed'] else 'FLAT'}"
            send_telegram(msg)
        except Exception as e:
            log.warning(f"텔레그램 알림 실패: {e}")
    else:
        log.info(f"상관관계 정상: {long_count}개 시장 노출")

    return result


if __name__ == "__main__":
    result = check_concentration_risk()
    print(result)
