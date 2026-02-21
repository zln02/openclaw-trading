# 키움 REST API - Misc

## OAuth 인증 > 접근토큰발급

### au10001 - 접근토큰 발급

**Method**: POST
**URL**: `/oauth2/token`
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
| `appkey` | 앱키 | String | Y |  |
| `secretkey` | 시크릿키 | String | Y |  |

**Response Body** (주요 필드):

| 필드 | 한글명 | 설명 |
|------|--------|------|
| `token_type` | 토큰타입 |  |
| `token` | 접근토큰 |  |

**Request Example**:
```json
{
    "grant_type": "client_credentials",
    "appkey": "AxserEsdcredca.....",
    "secretkey": "SEefdcwcforehDre2fdvc...."
}
```

---

## OAuth 인증 > 접근토큰폐기

### au10002 - 접근토큰폐기

**Method**: POST
**URL**: `/oauth2/revoke`
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
| `secretkey` | 시크릿키 | String | Y |  |
| `token` | 접근토큰 | String | Y |  |

**Request Example**:
```json
{
    "appkey": "AxserEsdcredca.....",
    "secretkey": "SEefdcwcforehDre2fdvc....",
    "token": "WQJCwyqInphKnR3bSRtB9NE1lv..."
}
```

---
