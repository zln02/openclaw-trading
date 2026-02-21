---
name: pdf
description: 마케팅 PDF 문서 제작 및 처리를 위한 종합 도구
version: 1.0.0
author: Dante Labs
tags:
  - pdf
  - document
  - marketing
  - report
---

# Marketing PDF Toolkit

마케팅 리포트, 브로슈어, 제안서 등 전문 PDF 문서를 제작하고 처리하는 도구입니다.

## 주요 기능

| 기능 | 설명 | 용도 |
|------|------|------|
| 텍스트 추출 | PDF → 텍스트/마크다운 | 경쟁사 자료 분석 |
| 테이블 추출 | PDF 테이블 → CSV/DataFrame | 데이터 분석 |
| PDF 병합 | 여러 PDF → 하나로 | 캠페인 패키지 |
| PDF 분할 | 하나 → 여러 PDF | 섹션별 배포 |
| PDF 생성 | 텍스트/HTML → PDF | 리포트 생성 |

## Workflow 1: 텍스트 추출

### 기본 텍스트 추출

```python
import pdfplumber

def extract_text(pdf_path):
    """PDF에서 텍스트 추출"""
    text_content = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_content.append(text)

    return "\n\n".join(text_content)

# 사용
text = extract_text("competitor_report.pdf")
```

### 마크다운 변환

```python
def pdf_to_markdown(pdf_path, output_path):
    """PDF를 구조화된 마크다운으로 변환"""
    with pdfplumber.open(pdf_path) as pdf:
        markdown_lines = []

        for i, page in enumerate(pdf.pages, 1):
            markdown_lines.append(f"## Page {i}\n")

            # 텍스트 추출
            text = page.extract_text() or ""
            markdown_lines.append(text)

            # 테이블 추출
            tables = page.extract_tables()
            for table in tables:
                markdown_lines.append(table_to_markdown(table))

            markdown_lines.append("\n---\n")

    with open(output_path, 'w') as f:
        f.write("\n".join(markdown_lines))
```

## Workflow 2: 테이블 추출

### CSV로 테이블 추출

```python
import pdfplumber
import pandas as pd

def extract_tables(pdf_path, output_dir):
    """PDF의 모든 테이블을 CSV로 추출"""
    with pdfplumber.open(pdf_path) as pdf:
        table_count = 0

        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()

            for idx, table in enumerate(tables):
                if table and len(table) > 1:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    output_path = f"{output_dir}/table_p{page_num}_{idx+1}.csv"
                    df.to_csv(output_path, index=False, encoding='utf-8-sig')
                    table_count += 1

    return table_count
```

## Workflow 3: PDF 병합/분할

### PDF 병합

```python
from pypdf import PdfReader, PdfWriter

def merge_pdfs(pdf_list, output_path):
    """여러 PDF를 하나로 병합"""
    writer = PdfWriter()

    for pdf_path in pdf_list:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)

    with open(output_path, 'wb') as f:
        writer.write(f)

    return output_path

# 캠페인 패키지 생성 예시
merge_pdfs([
    "brand_intro.pdf",
    "campaign_proposal.pdf",
    "budget_breakdown.pdf"
], "campaign_package.pdf")
```

### PDF 분할

```python
def split_pdf(pdf_path, output_dir, pages_per_file=1):
    """PDF를 여러 파일로 분할"""
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    outputs = []
    for start in range(0, total_pages, pages_per_file):
        writer = PdfWriter()
        end = min(start + pages_per_file, total_pages)

        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])

        output_path = f"{output_dir}/section_{start//pages_per_file + 1}.pdf"
        with open(output_path, 'wb') as f:
            writer.write(f)
        outputs.append(output_path)

    return outputs
```

## Workflow 4: 마케팅 PDF 생성

### ReportLab을 사용한 PDF 생성

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.colors import HexColor

def create_marketing_report(content, output_path):
    """마케팅 리포트 PDF 생성"""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm
    )

    # 스타일 정의
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=HexColor('#1a365d')
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=HexColor('#2b6cb0')
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        textColor=HexColor('#2d3748')
    )

    # 콘텐츠 구성
    story = []

    # 제목
    story.append(Paragraph(content['title'], title_style))
    story.append(Spacer(1, 20))

    # 섹션들
    for section in content['sections']:
        story.append(Paragraph(section['heading'], heading_style))
        story.append(Paragraph(section['body'], body_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    return output_path
```

### Markdown → PDF 변환

```python
import markdown
from weasyprint import HTML

def markdown_to_pdf(md_path, output_path):
    """마크다운을 스타일링된 PDF로 변환"""
    # 마크다운 읽기
    with open(md_path, 'r') as f:
        md_content = f.read()

    # HTML 변환
    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code']
    )

    # 스타일 추가
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

            body {{
                font-family: 'Noto Sans KR', sans-serif;
                line-height: 1.6;
                color: #2d3748;
                max-width: 210mm;
                padding: 20mm;
            }}

            h1 {{
                color: #1a365d;
                border-bottom: 2px solid #ed8936;
                padding-bottom: 10px;
            }}

            h2 {{
                color: #2b6cb0;
                margin-top: 30px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}

            th, td {{
                border: 1px solid #e2e8f0;
                padding: 10px;
                text-align: left;
            }}

            th {{
                background-color: #f7fafc;
                color: #1a365d;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    # PDF 생성
    HTML(string=styled_html).write_pdf(output_path)
    return output_path
```

## 마케팅 PDF 디자인 가이드

### 컬러 팔레트

#### 리포트용 (공식적/전문적)
```
Header:     #1a365d (Navy)
Accent:     #ed8936 (Orange)
Body Text:  #2d3748 (Dark Gray)
Background: #ffffff (White)
Borders:    #e2e8f0 (Light Gray)
```

#### 브로슈어용 (활기찬/매력적)
```
Primary:    #2b6cb0 (Blue)
Accent:     #38a169 (Green)
Highlight:  #f6e05e (Yellow)
Text:       #1a202c (Black)
```

### 레이아웃 원칙

```
┌─────────────────────────────────────┐
│  [로고]              마케팅 리포트  │ ← 헤더
├─────────────────────────────────────┤
│                                     │
│  Executive Summary                  │
│  ─────────────────                  │
│                                     │
│  요약 내용...                        │
│                                     │
├─────────────────────────────────────┤
│  1. 분석 개요                        │
│                                     │
│  상세 내용...                        │
│                                     │
│  [데이터 테이블]                     │
│  ┌───────┬───────┬───────┐         │
│  │       │       │       │         │
│  └───────┴───────┴───────┘         │
│                                     │
├─────────────────────────────────────┤
│           Page 1                    │ ← 푸터
└─────────────────────────────────────┘
```

### 타이포그래피

| 요소 | 폰트 | 크기 | 색상 |
|------|------|------|------|
| 문서 제목 | Noto Sans KR Bold | 24pt | #1a365d |
| 섹션 제목 | Noto Sans KR Bold | 16pt | #2b6cb0 |
| 소제목 | Noto Sans KR Medium | 13pt | #4a5568 |
| 본문 | Noto Sans KR Regular | 11pt | #2d3748 |
| 캡션 | Noto Sans KR Light | 9pt | #718096 |

## 마케팅 PDF 유형별 템플릿

### 1. 캠페인 리포트

```markdown
# 캠페인 성과 리포트

## Executive Summary
- 주요 성과 지표
- 핵심 인사이트

## 캠페인 개요
- 목표
- 기간
- 예산

## 채널별 성과
| 채널 | 도달 | 참여 | 전환 |
|------|------|------|------|
| ... | ... | ... | ... |

## 인사이트 및 제언

## 다음 단계
```

### 2. 브랜드 브로슈어

```markdown
# [브랜드명]

## 우리의 스토리
브랜드 탄생 배경...

## 핵심 가치
- 가치 1
- 가치 2
- 가치 3

## 제품/서비스
[이미지 + 설명]

## 연락처
```

### 3. 경쟁사 분석 리포트

```markdown
# 경쟁사 분석 리포트

## 분석 대상
- 경쟁사 A
- 경쟁사 B
- 경쟁사 C

## 포지셔닝 맵
[차트]

## 상세 분석
### 경쟁사 A
- 강점
- 약점
- 위협 요소

## 전략적 시사점
```

## File Storage

PDF 문서는 프로젝트의 표준 디렉토리 구조에 저장합니다.

```
{project}/
├── reports/
│   ├── pdf/                 # 최종 PDF 문서
│   │   ├── campaign-report-20240115.pdf
│   │   ├── brand-brochure-20240115.pdf
│   │   └── competitor-analysis-20240115.pdf
│   └── exports/             # PDF에서 추출한 데이터
│       ├── tables/          # 추출된 테이블 (CSV)
│       └── text/            # 추출된 텍스트
├── assets/
│   └── pdf-resources/       # PDF 리소스
│       ├── templates/       # PDF 템플릿
│       └── images/          # 삽입용 이미지
└── tmp/
    └── pdf-drafts/          # 초안 및 작업 파일
```

### 파일 명명 규칙

```
{project}/reports/pdf/{type}-{subject}-{date}.pdf

예시:
reports/pdf/campaign-report-q1-20240115.pdf
reports/pdf/brand-brochure-dante-coffee-20240115.pdf
reports/pdf/competitor-analysis-20240115.pdf
```

## 패키지 설치

```bash
# 필수 패키지
pip install pypdf pdfplumber reportlab

# 선택적 패키지 (고급 기능)
pip install weasyprint markdown  # MD → PDF 변환
pip install pytesseract pdf2image  # OCR
```

## 스크립트 및 레퍼런스

### 레퍼런스 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| PDF 폼 가이드 | `forms.md` | Fillable Fields 및 Annotations 폼 작업 가이드 |

### 스크립트

| 스크립트 | 경로 | 설명 |
|---------|------|------|
| extract_form_field_info.py | `scripts/` | Fillable 필드 정보 추출 |
| check_fillable_fields.py | `scripts/` | Fillable 필드 존재 확인 |
| fill_fillable_fields.py | `scripts/` | Fillable 필드 값 채우기 |
| fill_pdf_form_with_annotations.py | `scripts/` | 주석으로 텍스트 오버레이 |
| convert_pdf_to_images.py | `scripts/` | PDF → 이미지 변환 |
| check_bounding_boxes.py | `scripts/` | 바운딩 박스 시각화 |
| create_validation_image.py | `scripts/` | 결과 검증 이미지 생성 |

## Usage

이 스킬은 `brand-strategist`, `competitive-analyst` 에이전트가 리포트 생성 및 경쟁사 자료 분석 시 참조합니다.
