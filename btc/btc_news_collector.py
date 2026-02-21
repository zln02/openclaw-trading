# btc_news_collector.py
import requests
import os


def get_news_summary() -> str:
    """CryptoPanic v2 API로 BTC 실시간 뉴스 수집"""
    api_key = os.environ.get("CRYPTOPANIC_API_KEY", "")

    if not api_key:
        return "뉴스 API 키 없음 — 지표만으로 판단"

    try:
        res = requests.get(
            "https://cryptopanic.com/api/developer/v2/posts/",
            params={
                "auth_token": api_key,
                "currencies": "BTC",
                "public": "true",
            },
            timeout=5,
        )
        if res.status_code != 200:
            return f"뉴스 API 오류: HTTP {res.status_code}"
        data = res.json()
        posts = data.get("results", [])[:5]

        if not posts:
            return "최근 BTC 뉴스 없음"

        # 긍정/부정 키워드로 간단 감정 분석
        POS_KEYWORDS = [
            "surge", "rally", "bullish", "gain", "rise", "high",
            "adoption", "approval", "buy", "support", "breakthrough",
            "상승", "급등", "호재", "매수", "승인", "돌파",
        ]
        NEG_KEYWORDS = [
            "drop", "fall", "bearish", "crash", "fear", "ban",
            "sell", "decline", "warning", "risk", "hack", "fraud",
            "하락", "급락", "악재", "매도", "규제", "해킹", "사기",
        ]

        positive, negative = 0, 0
        headlines = []

        for p in posts:
            title = p.get("title", "")
            desc = p.get("description", "")
            text = (title + " " + desc).lower()

            pos = sum(1 for k in POS_KEYWORDS if k in text)
            neg = sum(1 for k in NEG_KEYWORDS if k in text)
            positive += pos
            negative += neg

            if pos > neg:
                emoji = "🟢"
            elif neg > pos:
                emoji = "🔴"
            else:
                emoji = "⚪"

            headlines.append(f"{emoji} {title}")

        # 전체 감정
        if positive > negative + 2:
            sentiment = f"🟢 긍정적 (긍정{positive} vs 부정{negative})"
        elif negative > positive + 2:
            sentiment = f"🔴 부정적 (긍정{positive} vs 부정{negative})"
        else:
            sentiment = f"⚪ 중립 (긍정{positive} vs 부정{negative})"

        return f"[뉴스 감정: {sentiment}]\n" + "\n".join(headlines)

    except Exception as e:
        return f"뉴스 수집 실패: {e}"


# btc_trading_agent.py 호환용
collect_news_summary = get_news_summary
