# PDF 폼 작업 가이드

마케팅 문서 및 계약서의 PDF 폼 작업을 위한 가이드입니다.

## Overview

PDF 폼 작업은 두 가지 방식으로 구분됩니다:

| 방식 | 설명 | 사용 스크립트 |
|------|------|--------------|
| **Fillable Fields** | PDF에 내장된 폼 필드 (AcroForm) | `fill_fillable_fields.py` |
| **Annotations** | 텍스트 주석으로 오버레이 | `fill_pdf_form_with_annotations.py` |

## Workflow

### Fillable Fields (AcroForm)

```
[PDF 확인] → [필드 추출] → [JSON 작성] → [필드 채우기] → [검증]
```

### Non-Fillable (Annotations)

```
[PDF → 이미지] → [바운딩 박스 정의] → [JSON 작성] → [주석 추가] → [검증]
```

## Fillable Fields 방식

### 1. 필드 정보 추출

```bash
python scripts/extract_form_field_info.py input.pdf > fields_info.json
```

**출력 예시**:
```json
[
  {
    "field_id": "/CustomerName",
    "page": 1,
    "type": "text",
    "rect": [100, 700, 300, 720]
  },
  {
    "field_id": "/AgreeTerms",
    "page": 1,
    "type": "checkbox",
    "checked_value": "/Yes",
    "unchecked_value": "/Off"
  },
  {
    "field_id": "/PaymentMethod",
    "page": 2,
    "type": "radio_group",
    "radio_options": [
      {"value": "/Card", "label": "신용카드"},
      {"value": "/Bank", "label": "계좌이체"}
    ]
  },
  {
    "field_id": "/Region",
    "page": 2,
    "type": "choice",
    "choice_options": [
      {"value": "seoul", "label": "서울"},
      {"value": "busan", "label": "부산"}
    ]
  }
]
```

### 2. 필드 값 JSON 작성

**fields_values.json**:
```json
[
  {
    "field_id": "/CustomerName",
    "page": 1,
    "value": "김단테"
  },
  {
    "field_id": "/AgreeTerms",
    "page": 1,
    "value": "/Yes"
  },
  {
    "field_id": "/PaymentMethod",
    "page": 2,
    "value": "/Card"
  },
  {
    "field_id": "/Region",
    "page": 2,
    "value": "seoul"
  }
]
```

### 3. 필드 채우기

```bash
python scripts/fill_fillable_fields.py input.pdf fields_values.json output.pdf
```

### 필드 타입별 값 형식

| 필드 타입 | 값 형식 | 예시 |
|----------|--------|------|
| `text` | 문자열 | `"김단테"` |
| `checkbox` | checked/unchecked 값 | `"/Yes"`, `"/Off"` |
| `radio_group` | 옵션 값 | `"/Card"` |
| `choice` | 선택 값 | `"seoul"` |

## Annotations 방식 (Non-Fillable)

### 1. PDF를 이미지로 변환

```bash
python scripts/convert_pdf_to_images.py input.pdf ./images/
```

**결과**: `images/page_1.png`, `images/page_2.png`, ...

### 2. 바운딩 박스 확인

이미지를 확인하여 텍스트를 넣을 위치 좌표를 파악합니다.

```bash
python scripts/check_bounding_boxes.py input.pdf fields.json validation.png
```

### 3. 필드 JSON 작성

**fields.json**:
```json
{
  "pages": [
    {
      "page_number": 1,
      "image_width": 2480,
      "image_height": 3508
    }
  ],
  "form_fields": [
    {
      "page_number": 1,
      "field_name": "고객명",
      "entry_bounding_box": [200, 500, 600, 540],
      "entry_text": {
        "text": "김단테",
        "font": "Pretendard",
        "font_size": 14,
        "font_color": "000000"
      }
    },
    {
      "page_number": 1,
      "field_name": "연락처",
      "entry_bounding_box": [200, 560, 600, 600],
      "entry_text": {
        "text": "010-1234-5678",
        "font": "Pretendard",
        "font_size": 14,
        "font_color": "000000"
      }
    }
  ]
}
```

### 바운딩 박스 형식

```
[x1, y1, x2, y2]
 │    │   │   └── 우하단 y (이미지 좌표)
 │    │   └────── 우하단 x
 │    └────────── 좌상단 y
 └─────────────── 좌상단 x
```

**좌표계**:
- 이미지 좌표: 좌상단 원점, y축 아래로 증가
- PDF 좌표: 좌하단 원점, y축 위로 증가
- 스크립트가 자동 변환

### 4. 주석 추가

```bash
python scripts/fill_pdf_form_with_annotations.py input.pdf fields.json output.pdf
```

### 5. 검증 이미지 생성

```bash
python scripts/create_validation_image.py output.pdf validation.png
```

## 마케팅 문서 사용 예시

### 견적서 자동 채우기

**1. 필드 정보 구조화**:
```json
{
  "pages": [{"page_number": 1, "image_width": 2480, "image_height": 3508}],
  "form_fields": [
    {
      "page_number": 1,
      "field_name": "회사명",
      "entry_bounding_box": [300, 200, 800, 240],
      "entry_text": {"text": "Dante Coffee", "font": "Pretendard", "font_size": 16}
    },
    {
      "page_number": 1,
      "field_name": "견적일자",
      "entry_bounding_box": [1800, 200, 2200, 240],
      "entry_text": {"text": "2024년 1월 15일", "font": "Pretendard", "font_size": 12}
    },
    {
      "page_number": 1,
      "field_name": "담당자",
      "entry_bounding_box": [300, 260, 600, 300],
      "entry_text": {"text": "마케팅팀 김단테", "font": "Pretendard", "font_size": 12}
    }
  ]
}
```

### 계약서 서명 영역

```json
{
  "pages": [{"page_number": 3, "image_width": 2480, "image_height": 3508}],
  "form_fields": [
    {
      "page_number": 3,
      "field_name": "서명일",
      "entry_bounding_box": [200, 2800, 500, 2840],
      "entry_text": {"text": "2024. 01. 15", "font": "Pretendard", "font_size": 14}
    },
    {
      "page_number": 3,
      "field_name": "서명자",
      "entry_bounding_box": [600, 2800, 1000, 2840],
      "entry_text": {"text": "김단테 (인)", "font": "Pretendard", "font_size": 14}
    }
  ]
}
```

## 스크립트 요약

| 스크립트 | 용도 | 입력 | 출력 |
|---------|------|------|------|
| `extract_form_field_info.py` | Fillable 필드 정보 추출 | PDF | JSON |
| `check_fillable_fields.py` | Fillable 필드 존재 확인 | PDF | 터미널 출력 |
| `fill_fillable_fields.py` | Fillable 필드 채우기 | PDF, JSON | PDF |
| `convert_pdf_to_images.py` | PDF → 이미지 변환 | PDF | PNG 파일들 |
| `check_bounding_boxes.py` | 바운딩 박스 시각화 | PDF, JSON | PNG |
| `fill_pdf_form_with_annotations.py` | 주석으로 텍스트 추가 | PDF, JSON | PDF |
| `create_validation_image.py` | 결과 검증 이미지 | PDF | PNG |

## 에러 대응

| 에러 메시지 | 원인 | 해결 |
|------------|------|------|
| `field_id is not valid` | 잘못된 필드 ID | `extract_form_field_info.py`로 재확인 |
| `Incorrect page number` | 페이지 번호 불일치 | 필드 정보 JSON 확인 |
| `Invalid value for checkbox` | 체크박스 값 오류 | checked/unchecked 값 사용 |
| `Invalid value for radio` | 라디오 옵션 오류 | 유효한 옵션 값 사용 |

## 주의사항

1. **페이지 번호**: 1부터 시작 (0-based 아님)
2. **필드 ID**: 슬래시(/)로 시작하는 경우 그대로 사용
3. **폰트**: 시스템에 설치된 폰트만 지원
4. **좌표**: 이미지 해상도에 따라 스케일 조정 필요

## 파일 저장 위치

```
{project}/
├── reports/documents/           # 최종 PDF
├── assets/pdf-resources/        # PDF 리소스
│   ├── templates/               # 원본 PDF 템플릿
│   ├── images/                  # 변환된 이미지
│   └── fields/                  # 필드 JSON
└── tmp/pdf-work/                # 작업 파일
```

## 의존성

```bash
pip install pypdf pdfplumber pdf2image Pillow
```

**시스템 요구사항**:
- poppler-utils (pdf2image용)

```bash
# macOS
brew install poppler

# Ubuntu/Debian
apt-get install poppler-utils
```

## 참고

- [pypdf Documentation](https://pypdf.readthedocs.io/)
- [pdfplumber Documentation](https://github.com/jsvine/pdfplumber)
- 스크립트 위치: `plugins/common/skills/pdf/scripts/`
