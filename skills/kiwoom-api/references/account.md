# 키움 REST API - Account

## 국내주식 > 계좌

### ka01690 - 일별잔고수익률

**Method**: POST
**URL**: `/api/dostk/acnt`
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
| `tot_buy_amt` | 총 매입가 |  |
| `tot_evlt_amt` | 총 평가금액 |  |
| `tot_evltv_prft` | 총 평가손익 |  |
| `tot_prft_rt` | 수익률 |  |
| `dbst_bal` | 예수금 |  |
| `day_stk_asst` | 추정자산 |  |
| `buy_wght` | 현금비중 |  |
| `day_bal_rt` | 일별잔고수익률 |  |
| `- cur_prc` | 현재가 |  |
| `- stk_cd` | 종목코드 |  |
| `- stk_nm` | 종목명 |  |
| `- rmnd_qty` | 보유 수량 |  |
| `- buy_uv` | 매입 단가 |  |
| `- buy_wght` | 매수비중 |  |
| `- evltv_prft` | 평가손익 |  |
| ... | (3개 추가 필드) | |

**Request Example**:
```json
{
    "qry_dt": "20250825"
}
```

---
