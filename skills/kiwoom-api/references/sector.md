# 키움 REST API - Sector

## 국내주식 > 업종

### ka10010 - 업종프로그램요청

**Method**: POST
**URL**: `/api/dostk/sect`
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
| `dfrt_trst_sell_amt` | 차익위탁매도금액 |  |
| `dfrt_trst_buy_qty` | 차익위탁매수수량 |  |
| `dfrt_trst_buy_amt` | 차익위탁매수금액 |  |
| `dfrt_trst_netprps_qty` | 차익위탁순매수수량 |  |
| `dfrt_trst_netprps_amt` | 차익위탁순매수금액 |  |
| `ndiffpro_trst_sell_qty` | 비차익위탁매도수량 |  |
| `ndiffpro_trst_sell_amt` | 비차익위탁매도금액 |  |
| `ndiffpro_trst_buy_qty` | 비차익위탁매수수량 |  |
| `ndiffpro_trst_buy_amt` | 비차익위탁매수금액 |  |
| `ndiffpro_trst_netprps_qty` | 비차익위탁순매수수량 |  |
| `ndiffpro_trst_netprps_amt` | 비차익위탁순매수금액 |  |
| `all_dfrt_trst_sell_qty` | 전체차익위탁매도수량 |  |
| `all_dfrt_trst_sell_amt` | 전체차익위탁매도금액 |  |
| `all_dfrt_trst_buy_qty` | 전체차익위탁매수수량 |  |
| `all_dfrt_trst_buy_amt` | 전체차익위탁매수금액 |  |
| ... | (2개 추가 필드) | |

**Request Example**:
```json
{
    "stk_cd": "005930"
}
```

---
