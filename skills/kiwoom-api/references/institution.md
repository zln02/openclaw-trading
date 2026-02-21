# 키움 REST API - Institution

## 국내주식 > 기관/외국인

### ka10008 - 주식외국인종목별매매동향

**Method**: POST
**URL**: `/api/dostk/frgnistt`
**모의투자**: https://mockapi.kiwoom.com(KRX만 지원가능)

**Request Headers**:

| 필드 | 한글명 | 필수 | 설명 |
|------|--------|------|------|
| `authorization` | 접근토큰 | Y | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출   예) Bearer Egicyx... |
| `cont-yn` | 연속조회여부 | N | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 con |
| `next-key` | 연속조회키 | N | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 nex |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- dt` | 일자 |  |
| `- close_pric` | 종가 |  |
| `- pred_pre` | 전일대비 |  |
| `- trde_qty` | 거래량 |  |
| `- chg_qty` | 변동수량 |  |
| `- poss_stkcnt` | 보유주식수 |  |
| `- wght` | 비중 |  |
| `- gain_pos_stkcnt` | 취득가능주식수 |  |
| `- frgnr_limit` | 외국인한도 |  |
| `- frgnr_limit_irds` | 외국인한도증감 |  |
| `- limit_exh_rt` | 한도소진률 |  |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10009 - 주식기관요청

**Method**: POST
**URL**: `/api/dostk/frgnistt`
**모의투자**: https://mockapi.kiwoom.com(KRX만 지원가능)

**Request Headers**:

| 필드 | 한글명 | 필수 | 설명 |
|------|--------|------|------|
| `authorization` | 접근토큰 | Y | 토큰 지정시 토큰타입("Bearer") 붙혀서 호출   예) Bearer Egicyx... |
| `cont-yn` | 연속조회여부 | N | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 con |
| `next-key` | 연속조회키 | N | 응답 Header의 연속조회여부값이 Y일 경우 다음데이터 요청시 응답 Header의 nex |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `close_pric` | 종가 |  |
| `pre` | 대비 |  |
| `orgn_dt_acc` | 기관기간누적 |  |
| `orgn_daly_nettrde` | 기관일별순매매 |  |
| `frgnr_daly_nettrde` | 외국인일별순매매 |  |
| `frgnr_qota_rt` | 외국인지분율 |  |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---
