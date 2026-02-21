# 키움 REST API - Market Price

## 국내주식 > 시세

### ka10004 - 주식호가요청

**Method**: POST
**URL**: `/api/dostk/mrkcond`
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
| `sel_10th_pre_req_pre` | 매도10차선잔량대비 | 매도호가직전대비10 |
| `sel_10th_pre_req` | 매도10차선잔량 | 매도호가수량10 |
| `sel_10th_pre_bid` | 매도10차선호가 | 매도호가10 |
| `sel_9th_pre_req_pre` | 매도9차선잔량대비 | 매도호가직전대비9 |
| `sel_9th_pre_req` | 매도9차선잔량 | 매도호가수량9 |
| `sel_9th_pre_bid` | 매도9차선호가 | 매도호가9 |
| `sel_8th_pre_req_pre` | 매도8차선잔량대비 | 매도호가직전대비8 |
| `sel_8th_pre_req` | 매도8차선잔량 | 매도호가수량8 |
| `sel_8th_pre_bid` | 매도8차선호가 | 매도호가8 |
| `sel_7th_pre_req_pre` | 매도7차선잔량대비 | 매도호가직전대비7 |
| `sel_7th_pre_req` | 매도7차선잔량 | 매도호가수량7 |
| `sel_7th_pre_bid` | 매도7차선호가 | 매도호가7 |
| `sel_6th_pre_req_pre` | 매도6차선잔량대비 | 매도호가직전대비6 |
| `sel_6th_pre_req` | 매도6차선잔량 | 매도호가수량6 |
| `sel_6th_pre_bid` | 매도6차선호가 | 매도호가6 |
| ... | (53개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10005 - 주식일주월시분요청

**Method**: POST
**URL**: `/api/dostk/mrkcond`
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
| `- date` | 날짜 |  |
| `- open_pric` | 시가 |  |
| `- high_pric` | 고가 |  |
| `- low_pric` | 저가 |  |
| `- close_pric` | 종가 |  |
| `- pre` | 대비 |  |
| `- flu_rt` | 등락률 |  |
| `- trde_qty` | 거래량 |  |
| `- trde_prica` | 거래대금 |  |
| `- for_poss` | 외인보유 |  |
| `- for_wght` | 외인비중 |  |
| `- for_netprps` | 외인순매수 |  |
| `- orgn_netprps` | 기관순매수 |  |
| `- ind_netprps` | 개인순매수 |  |
| `- frgn` | 외국계 |  |
| ... | (2개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10006 - 주식시분요청

**Method**: POST
**URL**: `/api/dostk/mrkcond`
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
| `open_pric` | 시가 |  |
| `high_pric` | 고가 |  |
| `low_pric` | 저가 |  |
| `close_pric` | 종가 |  |
| `pre` | 대비 |  |
| `flu_rt` | 등락률 |  |
| `trde_qty` | 거래량 |  |
| `trde_prica` | 거래대금 |  |
| `cntr_str` | 체결강도 |  |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10007 - 시세표성정보요청

**Method**: POST
**URL**: `/api/dostk/mrkcond`
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
| `stk_cd` | 종목코드 |  |
| `date` | 날짜 |  |
| `tm` | 시간 |  |
| `pred_close_pric` | 전일종가 |  |
| `pred_trde_qty` | 전일거래량 |  |
| `upl_pric` | 상한가 |  |
| `lst_pric` | 하한가 |  |
| `pred_trde_prica` | 전일거래대금 |  |
| `flo_stkcnt` | 상장주식수 |  |
| `cur_prc` | 현재가 |  |
| `smbol` | 부호 |  |
| `flu_rt` | 등락률 |  |
| `pred_rt` | 전일비 |  |
| `open_pric` | 시가 |  |
| `high_pric` | 고가 |  |
| ... | (108개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10011 - 신주인수권전체시세요청

**Method**: POST
**URL**: `/api/dostk/mrkcond`
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
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락율 |  |
| `- fpr_sel_bid` | 최우선매도호가 |  |
| `- fpr_buy_bid` | 최우선매수호가 |  |
| `- acc_trde_qty` | 누적거래량 |  |
| `- open_pric` | 시가 |  |
| `- high_pric` | 고가 |  |
| `- low_pric` | 저가 |  |

**Request Example**:
```json
{
    "newstk_recvrht_tp": "00"
}
```

---
