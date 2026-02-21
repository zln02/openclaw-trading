# OpenDART API Reference

OpenDART REST API 상세 문서.

## Base URL

```
https://opendart.fss.or.kr/api
```

## Authentication

모든 요청에 `crtfc_key` 파라미터 필수:

```bash
curl "https://opendart.fss.or.kr/api/list.json?crtfc_key=$DART_API_KEY&..."
```

## Endpoints

### 1. 공시 목록 조회 (list.json)

최근 공시 검색.

**Request:**
```
GET /list.json
```

**Parameters:**

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| crtfc_key | O | API 인증키 | - |
| corp_code | X | DART 고유번호 | 00266961 |
| bgn_de | X | 시작일 (YYYYMMDD) | 20260101 |
| end_de | X | 종료일 (YYYYMMDD) | 20260206 |
| last_reprt_at | X | 최종보고서만 | Y/N |
| pblntf_ty | X | 공시유형 | A, B, C, D, E, F, G, H, I, J, K |
| pblntf_detail_ty | X | 공시상세유형 | - |
| corp_cls | X | 법인구분 | Y(유가), K(코스닥), N(코넥스), E(기타) |
| sort | X | 정렬 | date, crp, rpt |
| sort_mth | X | 정렬방식 | asc, desc |
| page_no | X | 페이지 번호 | 1 |
| page_count | X | 페이지 당 건수 | 10~100 |

**공시유형 코드:**

| 코드 | 유형 |
|------|------|
| A | 정기공시 |
| B | 주요사항보고 |
| C | 발행공시 |
| D | 지분공시 |
| E | 기타공시 |
| F | 외부감사관련 |
| G | 펀드공시 |
| H | 자산유동화 |
| I | 거래소공시 |
| J | 공정위공시 |
| K | 수시공시 |

**Response:**
```json
{
    "status": "000",
    "message": "정상",
    "page_no": 1,
    "page_count": 10,
    "total_count": 100,
    "total_page": 10,
    "list": [
        {
            "corp_code": "00266961",
            "corp_name": "네이버",
            "stock_code": "035420",
            "corp_cls": "Y",
            "report_nm": "[기재정정]사업보고서 (2025.12)",
            "rcept_no": "20260205000123",
            "flr_nm": "네이버",
            "rcept_dt": "20260205",
            "rm": ""
        }
    ]
}
```

**Response Fields:**

| 필드 | 설명 |
|------|------|
| corp_code | DART 고유번호 |
| corp_name | 회사명 |
| stock_code | 종목코드 (상장사) |
| corp_cls | 법인구분 |
| report_nm | 공시명 |
| rcept_no | 접수번호 (공시 URL 생성용) |
| flr_nm | 제출인 |
| rcept_dt | 접수일 |
| rm | 비고 (유, 코, 채 등) |

**공시 URL 생성:**
```
https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}
```

---

### 2. 고유번호 조회 (corpCode.xml)

전체 기업 고유번호 ZIP 파일 다운로드.

**Request:**
```
GET /corpCode.xml?crtfc_key={API_KEY}
```

**Response:** ZIP 파일 (CORPCODE.xml 포함)

**XML 구조:**
```xml
<result>
    <list>
        <corp_code>00126380</corp_code>
        <corp_name>삼성전자</corp_name>
        <stock_code>005930</stock_code>
        <modify_date>20260101</modify_date>
    </list>
    ...
</result>
```

---

### 3. 재무제표 조회 (fnlttSinglAcntAll.json)

단일회사 전체 재무제표.

**Request:**
```
GET /fnlttSinglAcntAll.json
```

**Parameters:**

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| crtfc_key | O | API 인증키 | - |
| corp_code | O | DART 고유번호 | 00266961 |
| bsns_year | O | 사업연도 | 2025 |
| reprt_code | O | 보고서 코드 | 11014 |
| fs_div | X | 재무제표 구분 | OFS, CFS |

**보고서 코드:**

| 코드 | 설명 |
|------|------|
| 11011 | 1분기보고서 |
| 11012 | 반기보고서 |
| 11013 | 3분기보고서 |
| 11014 | 사업보고서 (연간) |

**재무제표 구분:**

| 코드 | 설명 |
|------|------|
| OFS | 개별재무제표 |
| CFS | 연결재무제표 |

**Response:**
```json
{
    "status": "000",
    "message": "정상",
    "list": [
        {
            "rcept_no": "20260315000123",
            "reprt_code": "11014",
            "bsns_year": "2025",
            "corp_code": "00266961",
            "sj_div": "BS",
            "sj_nm": "재무상태표",
            "account_id": "ifrs-full_Assets",
            "account_nm": "자산총계",
            "account_detail": "-",
            "thstrm_nm": "제27기",
            "thstrm_amount": "50000000000000",
            "frmtrm_nm": "제26기",
            "frmtrm_amount": "48000000000000",
            "bfefrmtrm_nm": "제25기",
            "bfefrmtrm_amount": "45000000000000",
            "ord": "1",
            "currency": "KRW"
        }
    ]
}
```

**주요 계정과목:**

| sj_div | 설명 |
|--------|------|
| BS | 재무상태표 |
| IS | 손익계산서 |
| CIS | 포괄손익계산서 |
| CF | 현금흐름표 |
| SCE | 자본변동표 |

---

### 4. 배당정보 조회 (alotMatter.json)

배당에 관한 사항.

**Request:**
```
GET /alotMatter.json
```

**Parameters:**

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| crtfc_key | O | API 인증키 |
| corp_code | O | DART 고유번호 |
| bsns_year | O | 사업연도 |
| reprt_code | O | 보고서 코드 |

**Response:**
```json
{
    "status": "000",
    "list": [
        {
            "se": "주당액면가액(원)",
            "thstrm": "100",
            "frmtrm": "100",
            "lwfr": "100"
        },
        {
            "se": "(연결)당기순이익(백만원)",
            "thstrm": "1,234,567",
            "frmtrm": "1,100,000",
            "lwfr": "900,000"
        },
        {
            "se": "현금배당금총액(백만원)",
            "thstrm": "500,000",
            "frmtrm": "450,000",
            "lwfr": "400,000"
        }
    ]
}
```

---

### 5. 대량보유 상황보고 (majorstock.json)

5% 이상 대량보유 현황.

**Request:**
```
GET /majorstock.json
```

**Parameters:**

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| crtfc_key | O | API 인증키 |
| corp_code | O | DART 고유번호 |

**Response:**
```json
{
    "status": "000",
    "list": [
        {
            "rcept_no": "20260115000456",
            "rcept_dt": "20260115",
            "corp_code": "00266961",
            "corp_name": "네이버",
            "report_tp": "대량보유상황보고",
            "repror": "국민연금공단",
            "stkqy": "10,000,000",
            "stkqy_irds": "500,000",
            "stkrt": "6.12",
            "stkrt_irds": "0.31",
            "ctr_stkqy": "10,000,000",
            "ctr_stkrt": "6.12",
            "report_resn": "단순투자"
        }
    ]
}
```

---

### 6. 임원 주요주주 소유보고 (elestock.json)

임원 및 주요주주 특정증권 소유상황.

**Request:**
```
GET /elestock.json
```

**Parameters:**

| 파라미터 | 필수 | 설명 |
|---------|------|------|
| crtfc_key | O | API 인증키 |
| corp_code | O | DART 고유번호 |

---

## Error Codes

| 코드 | 메시지 | 원인 |
|------|--------|------|
| 000 | 정상 | 성공 |
| 010 | 등록되지 않은 인증키 | API 키 오류 |
| 011 | 사용할 수 없는 인증키 | 키 비활성화 |
| 012 | 접근할 수 없는 IP | IP 제한 |
| 013 | 조회된 데이터 없음 | 결과 없음 |
| 020 | 요청 제한 초과 | 일일 10,000건 초과 |
| 100 | 필드 오류 | 파라미터 오류 |
| 800 | 시스템 점검 | 점검 중 |
| 900 | 정의되지 않은 오류 | 기타 오류 |

## Rate Limits

- **일일 호출 한도**: 10,000건
- **초당 호출 제한**: 명시되지 않음 (권장: 1초 간격)

## Best Practices

1. **캐싱 활용**: corpCode.xml은 일 1회만 갱신되므로 로컬 캐싱 권장
2. **에러 처리**: status 필드 확인 후 list 접근
3. **페이징**: 대량 조회 시 page_no, page_count 활용
4. **날짜 형식**: 모든 날짜는 YYYYMMDD 형식
