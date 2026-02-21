import json
import os
import requests
from pathlib import Path

# openclaw.json에서 Supabase 설정 로드
def _load_supabase_config():
    """openclaw.json에서 Supabase 설정 로드"""
    candidates = [
        Path.home() / ".openclaw" / "openclaw.json",
        Path("/home/node/.openclaw/openclaw.json"),
    ]
    
    for p in candidates:
        try:
            with p.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            env = cfg.get("env", {})
            supabase_url = env.get("SUPABASE_URL")
            supabase_key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_ANON_KEY")
            if supabase_url and supabase_key:
                return {"url": supabase_url, "api_key": supabase_key}
        except Exception:
            continue
    
    raise RuntimeError("SUPABASE_URL과 SUPABASE_SECRET_KEY를 찾을 수 없습니다.")

# Supabase 설정 로드
try:
    config = _load_supabase_config()
    url = f'{config["url"]}/rest/v1/stock_ohlcv'
    headers = {
        'apikey': config["api_key"],
        'Authorization': f'Bearer {config["api_key"]}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }
except RuntimeError as e:
    print(f"⚠️ 설정 로드 실패: {e}")
    print("⚠️ openclaw.json에 SUPABASE_SECRET_KEY 또는 SUPABASE_ANON_KEY를 설정해주세요.")
    exit(1)


# 데이터 삽입할 데이터 예시 (ticker 필드 필수)
data = [
    {'ticker': 'KOSPI', 'date': '2023-01-02', 'close': 2225.67, 'high': 2259.88, 'low': 2222.37, 'open': 2249.95, 'volume': 346100},
    {'ticker': 'KOSPI', 'date': '2023-01-03', 'close': 2218.68, 'high': 2230.98, 'low': 2180.67, 'open': 2230.98, 'volume': 410000},
    {'ticker': 'KOSPI', 'date': '2023-01-04', 'close': 2255.98, 'high': 2260.06, 'low': 2198.82, 'open': 2205.98, 'volume': 412700},
    {'ticker': 'KOSPI', 'date': '2023-01-05', 'close': 2264.65, 'high': 2281.39, 'low': 2252.97, 'open': 2268.20, 'volume': 430800},
    {'ticker': 'KOSPI', 'date': '2023-01-06', 'close': 2289.97, 'high': 2300.62, 'low': 2253.27, 'open': 2253.40, 'volume': 398300}
]

# 데이터 삽입 요청
for item in data:
    url_filtered = url + f'?ticker=eq.{item["ticker"]}&date=eq.{item["date"]}'
response = requests.put(url_filtered, headers=headers, json=item)

if response.status_code == 201:
    print('데이터 삽입 성공')
else:
    print('오류 발생:', response.text)