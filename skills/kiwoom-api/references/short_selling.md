# 키움 REST API - Short Selling

## 국내주식 > 공매도

### ka10014 - 공매도추이요청

**Method**: POST
**URL**: `/api/dostk/shsa`
**모의투자**: https://mockapi.kiwoom.com(KRX만 지원가능)

**Request Headers**:

| 필드 | 한글명 | 필수 | 설명 |
|------|--------|------|------|
| `authorization` | 접근토큰 | Y | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출   예) Bearer Egicyx... |
| `cont-yn` | 연속조회여부 | N | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 con |
| `next-key` | 연속조회키 | N | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 nex |

**Request Body**:

| 필드 | 한글명 | 타입 | 필수 | 설명 |
|------|--------|------|------|------|
| `tm_tp` | 시간구분 | String | N | 0:시작일, 1:기간 |
| `strt_dt` | 시작일자 | String | Y | YYYYMMDD |
| `end_dt` | 종료일자 | String | Y | YYYYMMDD |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- dt` | 일자 |  |
| `- close_pric` | 종가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락율 |  |
| `- trde_qty` | 거래량 |  |
| `- shrts_qty` | 공매도량 |  |
| `- ovr_shrts_qty` | 누적공매도량 | 설정 기간의 공매도량 합산데이터 |
| `- trde_wght` | 매매비중 |  |
| `- shrts_trde_prica` | 공매도거래대금 |  |
| `- shrts_avg_pric` | 공매도평균가 |  |

**Request Example**:
```json
{
    "stk_cd": "005930",
    "tm_tp": "1",
    "strt_dt": "20250501",
    "end_dt": "20250519"
}
```

---
