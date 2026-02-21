# 키움 REST API - Stock Info

## 국내주식 > 종목정보

### ka00198 - 실시간종목조회순위

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `- stk_nm` | 종목명 |  |
| `- bigd_rank` | 빅데이터 순위 |  |
| `- rank_chg` | 순위 등락 |  |
| `- rank_chg_sign` | 순위 등락 부호 |  |
| `- past_curr_prc` | 과거 현재가 |  |
| `- base_comp_sign` | 기준가 대비 부호 |  |
| `- base_comp_chgr` | 기준가 대비 등락율 |  |
| `- prev_base_sign` | 직전 기준 대비 부호 |  |
| `- prev_base_chgr` | 직전 기준 대비 등락율 |  |
| `- dt` | 일자 |  |
| `- tm` | 시간 |  |
| `- stk_cd` | 종목코드 |  |

**Request Example**:
```json
{
    "qry_tp": "1"
}
```

---

### ka10001 - 주식기본정보요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `stk_nm` | 종목명 |  |
| `setl_mm` | 결산월 |  |
| `fav` | 액면가 |  |
| `cap` | 자본금 |  |
| `flo_stk` | 상장주식 |  |
| `crd_rt` | 신용비율 |  |
| `oyr_hgst` | 연중최고 |  |
| `oyr_lwst` | 연중최저 |  |
| `mac` | 시가총액 |  |
| `mac_wght` | 시가총액비중 |  |
| `for_exh_rt` | 외인소진률 |  |
| `repl_pric` | 대용가 |  |
| `per` | PER | [ 주의 ] PER, ROE 값들은 외부벤더사에서 제공되는 데이터이며 일 |
| `eps` | EPS |  |
| `roe` | ROE | [ 주의 ]  PER, ROE 값들은 외부벤더사에서 제공되는 데이터이며  |
| ... | (29개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10002 - 주식거래원요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `stk_nm` | 종목명 |  |
| `cur_prc` | 현재가 |  |
| `flu_smbol` | 등락부호 |  |
| `base_pric` | 기준가 |  |
| `pred_pre` | 전일대비 |  |
| `flu_rt` | 등락율 |  |
| `sel_trde_ori_nm_1` | 매도거래원명1 |  |
| `sel_trde_ori_1` | 매도거래원1 |  |
| `sel_trde_qty_1` | 매도거래량1 |  |
| `buy_trde_ori_nm_1` | 매수거래원명1 |  |
| `buy_trde_ori_1` | 매수거래원1 |  |
| `buy_trde_qty_1` | 매수거래량1 |  |
| `sel_trde_ori_nm_2` | 매도거래원명2 |  |
| `sel_trde_ori_2` | 매도거래원2 |  |
| `sel_trde_qty_2` | 매도거래량2 |  |
| ... | (21개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10003 - 체결정보요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `- tm` | 시간 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre` | 전일대비 |  |
| `- pre_rt` | 대비율 |  |
| `- pri_sel_bid_unit` | 우선매도호가단위 |  |
| `- pri_buy_bid_unit` | 우선매수호가단위 |  |
| `- cntr_trde_qty` | 체결거래량 |  |
| `- sign` | sign |  |
| `- acc_trde_qty` | 누적거래량 |  |
| `- acc_trde_prica` | 누적거래대금 |  |
| `- cntr_str` | 체결강도 |  |
| `- stex_tp` | 거래소구분 | KRX , NXT , 통합 |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---

### ka10013 - 신용매매동향요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `dt` | 일자 | String | Y | YYYYMMDD  |
| `qry_tp` | 조회구분 | String | Y | 1:융자, 2:대주 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- dt` | 일자 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- trde_qty` | 거래량 |  |
| `- new` | 신규 |  |
| `- rpya` | 상환 |  |
| `- remn` | 잔고 |  |
| `- amt` | 금액 |  |
| `- pre` | 대비 |  |
| `- shr_rt` | 공여율 |  |
| `- remn_rt` | 잔고율 |  |

**Request Example**:
```json
{
    "stk_cd": "005930",
    "dt": "20241104",
    "qry_tp": "1"
}
```

---

### ka10015 - 일별거래상세요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `strt_dt` | 시작일자 | String | Y | YYYYMMDD |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- dt` | 일자 |  |
| `- close_pric` | 종가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락율 |  |
| `- trde_qty` | 거래량 |  |
| `- trde_prica` | 거래대금 |  |
| `- bf_mkrt_trde_qty` | 장전거래량 |  |
| `- bf_mkrt_trde_wght` | 장전거래비중 |  |
| `- opmr_trde_qty` | 장중거래량 |  |
| `- opmr_trde_wght` | 장중거래비중 |  |
| `- af_mkrt_trde_qty` | 장후거래량 |  |
| `- af_mkrt_trde_wght` | 장후거래비중 |  |
| `- tot_3` | 합계3 |  |
| `- prid_trde_qty` | 기간중거래량 |  |
| ... | (15개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930",
    "strt_dt": "20241105"
}
```

---

### ka10016 - 신고저가요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `ntl_tp` | 신고저구분 | String | Y | 1:신고가,2:신저가 |
| `high_low_close_tp` | 고저종구분 | String | Y | 1:고저기준, 2:종가기준 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회,1:관리종목제외, 3:우선주제외, 5:증100제외, 6:증1 |
| `trde_qty_tp` | 거래량구분 | String | Y | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 001 |
| `crd_cnd` | 신용조건 | String | Y | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4: |
| `updown_incls` | 상하한포함 | String | Y | 0:미포함, 1:포함 |
| `dt` | 기간 | String | Y | 5:5일, 10:10일, 20:20일, 60:60일, 250:250일,  |
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
| `- trde_qty` | 거래량 |  |
| `- pred_trde_qty_pre_rt` | 전일거래량대비율 |  |
| `- sel_bid` | 매도호가 |  |
| `- buy_bid` | 매수호가 |  |
| `- high_pric` | 고가 |  |
| `- low_pric` | 저가 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "ntl_tp": "1",
    "high_low_close_tp": "1",
    "stk_cnd": "0",
    "trde_qty_tp": "00000",
    "crd_cnd": "0",
    "updown_incls": "0",
    "dt": "5",
    "stex_tp": "1"
}
```

---

### ka10017 - 상하한가요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `updown_tp` | 상하한구분 | String | Y | 1:상한, 2:상승, 3:보합, 4: 하한, 5:하락, 6:전일상한, 7 |
| `sort_tp` | 정렬구분 | String | Y | 1:종목코드순, 2:연속횟수순(상위100개), 3:등락률순 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회,1:관리종목제외, 3:우선주제외, 4:우선주+관리종목제외,  |
| `trde_qty_tp` | 거래량구분 | String | Y | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 001 |
| `crd_cnd` | 신용조건 | String | Y | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4: |
| `trde_gold_tp` | 매매금구분 | String | Y | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~3천원, 4 |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_infr` | 종목정보 |  |
| `- stk_nm` | 종목명 |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락률 |  |
| `- trde_qty` | 거래량 |  |
| `- pred_trde_qty` | 전일거래량 |  |
| `- sel_req` | 매도잔량 |  |
| `- sel_bid` | 매도호가 |  |
| `- buy_bid` | 매수호가 |  |
| `- buy_req` | 매수잔량 |  |
| `- cnt` | 횟수 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "updown_tp": "1",
    "sort_tp": "1",
    "stk_cnd": "0",
    "trde_qty_tp": "0000",
    "crd_cnd": "0",
    "trde_gold_tp": "0",
    "stex_tp": "1"
}
```

---

### ka10018 - 고저가근접요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `alacc_rt` | 근접율 | String | Y | 05:0.5 10:1.0, 15:1.5, 20:2.0. 25:2.5, 3 |
| `mrkt_tp` | 시장구분 | String | Y | 000:전체, 001:코스피, 101:코스닥 |
| `trde_qty_tp` | 거래량구분 | String | Y | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 001 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회,1:관리종목제외, 3:우선주제외, 5:증100제외, 6:증1 |
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
| `- flu_rt` | 등락률 |  |
| `- trde_qty` | 거래량 |  |
| `- sel_bid` | 매도호가 |  |
| `- buy_bid` | 매수호가 |  |
| `- tdy_high_pric` | 당일고가 |  |
| `- tdy_low_pric` | 당일저가 |  |

**Request Example**:
```json
{
    "high_low_tp": "1",
    "alacc_rt": "05",
    "mrkt_tp": "000",
    "trde_qty_tp": "0000",
    "stk_cnd": "0",
    "crd_cnd": "0",
    "stex_tp": "1"
}
```

---

### ka10019 - 가격급등락요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `flu_tp` | 등락구분 | String | Y | 1:급등, 2:급락 |
| `tm_tp` | 시간구분 | String | Y | 1:분전, 2:일전 |
| `tm` | 시간 | String | Y | 분 혹은 일입력 |
| `trde_qty_tp` | 거래량구분 | String | Y | 00000:전체조회, 00010:만주이상, 00050:5만주이상, 001 |
| `stk_cnd` | 종목조건 | String | Y | 0:전체조회,1:관리종목제외, 3:우선주제외, 5:증100제외, 6:증1 |
| `crd_cnd` | 신용조건 | String | Y | 0:전체조회, 1:신용융자A군, 2:신용융자B군, 3:신용융자C군, 4: |
| `pric_cnd` | 가격조건 | String | Y | 0:전체조회, 1:1천원미만, 2:1천원~2천원, 3:2천원~3천원, 4 |
| `updown_incls` | 상하한포함 | String | Y | 0:미포함, 1:포함 |
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_cls` | 종목분류 |  |
| `- stk_nm` | 종목명 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락률 |  |
| `- base_pric` | 기준가 |  |
| `- cur_prc` | 현재가 |  |
| `- base_pre` | 기준대비 |  |
| `- trde_qty` | 거래량 |  |
| `- jmp_rt` | 급등률 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "flu_tp": "1",
    "tm_tp": "1",
    "tm": "60",
    "trde_qty_tp": "0000",
    "stk_cnd": "0",
    "crd_cnd": "0",
    "pric_cnd": "0",
    "updown_incls": "1",
    "stex_tp": "1"
}
```

---

### ka10024 - 거래량갱신요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `cycle_tp` | 주기구분 | String | Y | 5:5일, 10:10일, 20:20일, 60:60일, 250:250일 |
| `trde_qty_tp` | 거래량구분 | String | Y | 5:5천주이상, 10:만주이상, 50:5만주이상, 100:10만주이상,  |
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
| `- sel_bid` | 매도호가 |  |
| `- buy_bid` | 매수호가 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "cycle_tp": "5",
    "trde_qty_tp": "5",
    "stex_tp": "3"
}
```

---

### ka10025 - 매물대집중요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `prps_cnctr_rt` | 매물집중비율 | String | Y | 0~100 입력 |
| `cur_prc_entry` | 현재가진입 | String | Y | 0:현재가 매물대 진입 포함안함, 1:현재가 매물대 진입포함 |
| `prpscnt` | 매물대수 | String | Y | 숫자입력 |
| `cycle_tp` | 주기구분 | String | Y | 50:50일, 100:100일, 150:150일, 200:200일, 25 |
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
| `- now_trde_qty` | 현재거래량 |  |
| `- pric_strt` | 가격대시작 |  |
| `- pric_end` | 가격대끝 |  |
| `- prps_qty` | 매물량 |  |
| `- prps_rt` | 매물비 |  |

**Request Example**:
```json
{
    "mrkt_tp": "000",
    "prps_cnctr_rt": "50",
    "cur_prc_entry": "0",
    "prpscnt": "10",
    "cycle_tp": "50",
    "stex_tp": "3"
}
```

---

### ka10026 - 고저PER요청

**Method**: POST
**URL**: `/api/dostk/stkinfo`
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
| `stex_tp` | 거래소구분 | String | Y | 1:KRX, 2:NXT 3.통합 |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- per` | PER |  |
| `- cur_prc` | 현재가 |  |
| `- pred_pre_sig` | 전일대비기호 |  |
| `- pred_pre` | 전일대비 |  |
| `- flu_rt` | 등락률 |  |
| `- now_trde_qty` | 현재거래량 |  |
| `- sel_bid` | 매도호가 |  |

**Request Example**:
```json
{
    "pertp": "1",
    "stex_tp": "3"
}
```

---
