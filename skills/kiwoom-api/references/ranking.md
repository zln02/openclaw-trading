# 키움 REST API - Ranking

## 국내주식 > 순위정보

### ka10020 - 호가잔량상위요청

**Method**: POST
**URL**: `/api/dostk/rkinfo`
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
| `sort_tp` | 정렬구분 | String | Y | 1:순매수잔량순, 2:순매도잔량순, 3:매수비율순, 4:매도비율순 |
| `trde_qty_tp` | 거래량구분 | String | Y | 0000:장시작전(0주이상), 0010:만주이상, 0050:5만주이상,  |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7 |
| `crd_cnd` | 신용조건 | String | Y | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4: |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- trde_qty` | 거래량 |  |
| `- tot_sel_req` | 총매도잔량 |  |
| `- tot_buy_req` | 총매수잔량 |  |
| `- netprps_req` | 순매수잔량 |  |
| `- buy_rt` | 매수비율 |  |

**Request Example**:
```json
{
    "mrkt_tp": "001",
    "sort_tp": "1",
    "trde_qty_tp": "0000",
    "stk_cnd": "0",
    "crd_cnd": "0",
    "stex_tp": "1"
}
```

---

### ka10021 - 호가잔량급증요청

**Method**: POST
**URL**: `/api/dostk/rkinfo`
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
| `trde_tp` | 매매구분 | String | Y | 1:매수잔량, 2:매도잔량 |
| `sort_tp` | 정렬구분 | String | Y | 1:급증량, 2:급증률 |
| `tm_tp` | 시간구분 | String | Y | 분 입력 |
| `trde_qty_tp` | 거래량구분 | String | Y | 1:천주이상, 5:5천주이상, 10:만주이상, 50:5만주이상, 100: |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7 |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- int` | 기준률 |  |
| `- now` | 현재 |  |
| `- sdnin_qty` | 급증수량 |  |
| `- sdnin_rt` | 급증률 |  |
| `- tot_buy_qty` | 총매수량 |  |

**Request Example**:
```json
{
    "mrkt_tp": "001",
    "trde_tp": "1",
    "sort_tp": "1",
    "tm_tp": "30",
    "trde_qty_tp": "1",
    "stk_cnd": "0",
    "stex_tp": "3"
}
```

---

### ka10022 - 잔량율급증요청

**Method**: POST
**URL**: `/api/dostk/rkinfo`
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
| `rt_tp` | 비율구분 | String | Y | 1:매수/매도비율, 2:매도/매수비율 |
| `tm_tp` | 시간구분 | String | Y | 분 입력 |
| `trde_qty_tp` | 거래량구분 | String | Y | 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회, 1:관리종목제외, 5:증100제외, 6:증100만보기, 7 |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- int` | 기준률 |  |
| `- now_rt` | 현재비율 |  |
| `- sdnin_rt` | 급증률 |  |
| `- tot_sel_req` | 총매도잔량 |  |
| `- tot_buy_req` | 총매수잔량 |  |

**Request Example**:
```json
{
    "mrkt_tp": "001",
    "rt_tp": "1",
    "tm_tp": "1",
    "trde_qty_tp": "5",
    "stk_cnd": "0",
    "stex_tp": "3"
}
```

---

### ka10023 - 거래량급증요청

**Method**: POST
**URL**: `/api/dostk/rkinfo`
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
| `sort_tp` | 정렬구분 | String | Y | 1:급증량, 2:급증률, 3:급감량, 4:급감률 |
| `tm_tp` | 시간구분 | String | Y | 1:분, 2:전일 |
| `trde_qty_tp` | 거래량구분 | String | Y | 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상,  |
| `tm` | 시간 | String | N | 분 입력 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회, 1:관리종목제외, 3:우선주제외, 11:정리매매종목제외,  |
| `pric_tp` | 가격구분 | String | Y | 0:전체조회, 2:5만원이상, 5:1만원이상, 6:5천원이상, 8:1천원 |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락률 |  |
| `- prev_trde_qty` | 이전거래량 |  |
| `- now_trde_qty` | 현재거래량 |  |
| `- sdnin_qty` | 급증량 |  |
| `- sdnin_rt` | 급증률 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "sort_tp": "1",
    "tm_tp": "2",
    "trde_qty_tp": "5",
    "tm": "",
    "stk_cnd": "0",
    "pric_tp": "0",
    "stex_tp": "3"
}
```

---

### ka10027 - 전일대비등락률상위요청

**Method**: POST
**URL**: `/api/dostk/rkinfo`
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
| `sort_tp` | 정렬구분 | String | Y | 1:상승률, 2:상승폭, 3:하락률, 4:하락폭, 5:보합 |
| `trde_qty_cnd` | 거래량조건 | String | Y | 0000:전체조회, 0010:만주이상, 0050:5만주이상, 0100:1 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회, 1:관리종목제외, 4:우선주+관리주제외, 3:우선주제외,  |
| `crd_cnd` | 신용조건 | String | Y | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4: |
| `updown_incls` | 상하한포함 | String | Y | 0:불 포함, 1:포함 |
| `pric_cnd` | 가격조건 | String | Y | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~5천원, 4 |
| `trde_prica_cnd` | 거래대금조건 | String | Y | 0:전체조회, 3:3천만원이상, 5:5천만원이상, 10:1억원이상, 30 |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cls` | 종목분류 |  |
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락률 |  |
| `- sel_req` | 매도잔량 |  |
| `- buy_req` | 매수잔량 |  |
| `- now_trde_qty` | 현재거래량 |  |
| `- cntr_str` | 체결강도 |  |
| `- cnt` | 횟수 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "sort_tp": "1",
    "trde_qty_cnd": "0000",
    "stk_cnd": "0",
    "crd_cnd": "0",
    "updown_incls": "1",
    "pric_cnd": "0",
    "trde_prica_cnd": "0",
    "stex_tp": "3"
}
```

---
