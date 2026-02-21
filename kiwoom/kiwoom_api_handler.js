const fs = require("fs");

// 요청 간격 (밀리초)
const REQUEST_INTERVAL = 2000; // 2초
let lastRequestTime = 0;

function loadConfigEnv() {
  const candidates = [
    "/home/node/.openclaw/openclaw.json",          // 컨테이너 안
    "/home/wlsdud5035/.openclaw/openclaw.json",    // 호스트 직접 실행용
  ];

  for (const p of candidates) {
    try {
      const raw = fs.readFileSync(p, "utf8");
      const cfg = JSON.parse(raw);
      return cfg.env || {};
    } catch {
      // 다음 경로 시도
    }
  }

  return {};
}

async function getMockToken(env) {
  const appKey = env.KIWOOM_MOCK_REST_API_APP_KEY;
  const secretKey = env.KIWOOM_MOCK_REST_API_SECRET_KEY;

  if (!appKey || !secretKey) {
    throw new Error(
      "KIWOOM_MOCK_REST_API_APP_KEY / KIWOOM_MOCK_REST_API_SECRET_KEY가 설정되어 있지 않습니다."
    );
  }

  const url = "https://mockapi.kiwoom.com/oauth2/token";

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json;charset=UTF-8",
    },
    body: JSON.stringify({
      grant_type: "client_credentials",
      appkey: appKey,
      secretkey: secretKey,
    }),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok || data.return_code !== 0) {
    throw new Error(
      `토큰 발급 실패 (http=${res.status}, code=${data.return_code}, msg=${data.return_msg})`
    );
  }

  return data.token;
}

// 특정 종목의 정보를 가져오는 함수 (ka10001 - 주식기본정보요청)
async function fetchStockInfo(stockCode) {
  const currentTime = Date.now();
  if (currentTime - lastRequestTime < REQUEST_INTERVAL) {
    console.log("요청 간격(2초)을 지켜줘.");
    return null;
  }
  lastRequestTime = currentTime;

  try {
    const env = loadConfigEnv();
    const token = await getMockToken(env);

    const url = "https://mockapi.kiwoom.com/api/dostk/stkinfo";
    const body = { stk_cd: stockCode };

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json;charset=UTF-8",
        "api-id": "ka10001",
        authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok || data.return_code !== 0) {
      console.error("키움 주식기본정보 API 오류:", {
        http_status: res.status,
        return_code: data.return_code,
        return_msg: data.return_msg,
      });
      return null;
    }

    return data;
  } catch (error) {
    console.error("API 호출 중 오류 발생:", error.message);
    return null;
  }
}

// 상위 50 종목 정보를 가져오는 함수
// 키움 공식 REST API에는 "상위 50 종목" 엔드포인트가 없으므로,
// 대표 종목 코드 리스트를 직접 조회하는 방식으로 변경
async function fetchTop50Stocks() {
  // 대표 종목 코드 리스트 (코스피/코스닥 주요 종목)
  const topStockCodes = [
    "005930", // 삼성전자
    "000660", // SK하이닉스
    "035420", // NAVER
    "035720", // 카카오
    "051910", // LG화학
    "006400", // 삼성SDI
    "028260", // 삼성물산
    "005380", // 현대차
    "012330", // 현대모비스
    "105560", // KB금융
    "055550", // 신한지주
    "032830", // 삼성생명
    "003550", // LG
    "034730", // SK
    "017670", // SK텔레콤
    "096770", // SK이노베이션
    "066570", // LG전자
    "207940", // 삼성바이오로직스
    "068270", // 셀트리온
    "251270", // 넷마블
  ];

  const results = [];
  for (const code of topStockCodes) {
    const info = await fetchStockInfo(code);
    if (info) {
      results.push({
        stk_cd: info.stk_cd,
        stk_nm: info.stk_nm,
        cur_prc: info.cur_prc,
        flu_rt: info.flu_rt,
      });
    }
    // 요청 간격 유지
    await new Promise((resolve) => setTimeout(resolve, REQUEST_INTERVAL));
  }

  return results;
}

// 실행 예시
async function main() {
  try {
    const topStocks = await fetchTop50Stocks();
    if (topStocks && topStocks.length > 0) {
      console.log(`✅ ${topStocks.length}개 종목 조회 성공:`);
      topStocks.forEach((stock) => {
        console.log(`  ${stock.stk_nm} (${stock.stk_cd}): ${stock.cur_prc}원 (${stock.flu_rt}%)`);
      });
    } else {
      console.log("❌ 조회된 종목이 없습니다.");
    }
  } catch (error) {
    console.error("❌ 실행 중 오류:", error.message);
  }
}

// 직접 실행 시에만 main 실행
if (require.main === module) {
  main();
}

module.exports = { fetchStockInfo, fetchTop50Stocks };

