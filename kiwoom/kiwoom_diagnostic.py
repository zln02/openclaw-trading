#!/usr/bin/env python3
"""
키움증권 REST API 진단 스크립트
- 토큰 발급만 테스트
- 성공/실패 + 에러코드 + 응답 전문을 brain/logs/에 저장
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# 경로 설정
ROOT = Path(__file__).resolve().parent
BRAIN_DIR = ROOT / "brain"
LOG_DIR = BRAIN_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DIAGNOSTIC_LOG = LOG_DIR / "kiwoom-diagnostic.log"


def _load_kiwoom_config() -> Dict[str, str]:
    """openclaw.json에서 키움 API 키 로드"""
    candidates = [
        Path.home() / ".openclaw" / "openclaw.json",
        Path("/home/node/.openclaw/openclaw.json"),
    ]
    
    for p in candidates:
        try:
            with p.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            env = cfg.get("env", {})
            api_key = env.get("KIWOOM_MOCK_REST_API_APP_KEY") or env.get("KIWOOM_REST_API_KEY")
            api_secret = env.get("KIWOOM_MOCK_REST_API_SECRET_KEY") or env.get("KIWOOM_REST_API_SECRET")
            trading_env = env.get("TRADING_ENV", "mock").lower()
            
            if api_key and api_secret:
                return {
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "trading_env": trading_env,
                }
        except Exception:
            continue
    
    raise RuntimeError("키움 API 키를 찾을 수 없습니다.")


def test_token_issuance() -> Dict[str, Any]:
    """토큰 발급 테스트"""
    config = _load_kiwoom_config()
    api_key = config["api_key"]
    api_secret = config["api_secret"]
    trading_env = config["trading_env"]
    
    base_url = "https://mockapi.kiwoom.com" if trading_env == "mock" else "https://api.kiwoom.com"
    url = f"{base_url}/oauth2/token"
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "environment": trading_env,
        "base_url": base_url,
        "endpoint": "/oauth2/token",
        "success": False,
        "http_status": None,
        "return_code": None,
        "return_msg": None,
        "error": None,
        "response_body": None,
    }
    
    try:
        print(f"🔍 키움 API 토큰 발급 테스트 시작...")
        print(f"   환경: {trading_env}")
        print(f"   Base URL: {base_url}")
        print(f"   Endpoint: {url}")
        
        data = {
            "grant_type": "client_credentials",
            "appkey": api_key,
            "secretkey": api_secret,
        }
        
        resp = httpx.post(url, json=data, timeout=30.0)
        result["http_status"] = resp.status_code
        
        try:
            response_body = resp.json()
            result["response_body"] = response_body
            result["return_code"] = response_body.get("return_code")
            result["return_msg"] = response_body.get("return_msg")
            
            if resp.status_code == 200 and response_body.get("return_code") == 0:
                result["success"] = True
                token = response_body.get("token", "")[:20] + "..." if response_body.get("token") else None
                print(f"✅ 토큰 발급 성공!")
                print(f"   HTTP Status: {resp.status_code}")
                print(f"   Return Code: {result.get('return_code')}")
                print(f"   Return Msg: {result.get('return_msg')}")
                if token:
                    print(f"   Token (처음 20자): {token}")
            else:
                result["success"] = False
                result["error"] = f"API 오류: {result.get('return_msg')}"
                print(f"❌ 토큰 발급 실패")
                print(f"   HTTP Status: {resp.status_code}")
                print(f"   Return Code: {result.get('return_code')}")
                print(f"   Return Msg: {result.get('return_msg')}")
        except json.JSONDecodeError:
            result["error"] = f"JSON 파싱 실패: {resp.text[:200]}"
            result["response_body"] = resp.text[:500]
            print(f"❌ 응답 파싱 실패: {resp.text[:200]}")
            
    except httpx.TimeoutException:
        result["error"] = "요청 타임아웃 (30초 초과)"
        print(f"❌ 요청 타임아웃")
    except httpx.RequestError as e:
        result["error"] = f"네트워크 오류: {str(e)}"
        print(f"❌ 네트워크 오류: {e}")
    except Exception as e:
        result["error"] = f"예기치 못한 오류: {str(e)}"
        print(f"❌ 예기치 못한 오류: {e}")
    
    # 로그 파일에 저장
    try:
        with DIAGNOSTIC_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(f"\n📝 진단 결과가 {DIAGNOSTIC_LOG}에 저장되었습니다.")
    except Exception as e:
        print(f"⚠️ 로그 저장 실패: {e}", file=sys.stderr)
    
    return result


def main():
    """메인 실행 함수"""
    result = test_token_issuance()
    
    print("\n" + "="*60)
    print("📋 진단 결과 요약:")
    print("="*60)
    print(json.dumps({
        "success": result["success"],
        "environment": result["environment"],
        "http_status": result["http_status"],
        "return_code": result["return_code"],
        "return_msg": result["return_msg"],
        "error": result["error"],
    }, ensure_ascii=False, indent=2))
    
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
