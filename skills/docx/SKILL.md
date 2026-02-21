---
name: docx
description: 마케팅 문서 제작을 위한 Word 문서 생성/편집 도구
version: 1.0.0
author: Dante Labs
tags:
  - document
  - word
  - marketing
  - report
---

# Marketing Document Toolkit

마케팅 기획서, 브랜드 가이드, 제안서 등 전문 Word 문서를 제작하고 편집하는 도구입니다.

## 주요 기능

| 기능 | 설명 | 용도 |
|------|------|------|
| 새 문서 생성 | 마크다운 → DOCX | 기획서, 가이드 작성 |
| 기존 문서 편집 | OOXML 편집 | 텍스트/스타일 수정 |
| 텍스트 추출 | DOCX → 텍스트 | 문서 분석 |
| 변경 추적 | Redlining | 협업 및 검토 |

## Workflow 1: 새 문서 생성 (Markdown → DOCX)

### Pandoc을 사용한 변환

```bash
# 기본 변환
pandoc input.md -o output.docx

# 스타일 템플릿 적용
pandoc input.md --reference-doc=template.docx -o output.docx

# 목차 포함
pandoc input.md --toc --toc-depth=3 -o output.docx
```

### Python-docx를 사용한 생성

```python
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE

def create_marketing_document(content, output_path):
    """마케팅 문서 생성"""
    doc = Document()

    # 스타일 설정
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Malgun Gothic'
    font.size = Pt(11)

    # 제목 스타일
    title_style = doc.styles['Title']
    title_style.font.size = Pt(28)
    title_style.font.color.rgb = RGBColor(0x1a, 0x36, 0x5d)

    # 제목 추가
    title = doc.add_heading(content['title'], 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 부제목
    subtitle = doc.add_paragraph(content['subtitle'])
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_page_break()

    # 목차 (수동)
    doc.add_heading('목차', level=1)
    for i, section in enumerate(content['sections'], 1):
        doc.add_paragraph(f"{i}. {section['title']}", style='List Number')

    doc.add_page_break()

    # 본문 섹션
    for section in content['sections']:
        doc.add_heading(section['title'], level=1)

        for para in section['paragraphs']:
            doc.add_paragraph(para)

        # 테이블이 있는 경우
        if 'table' in section:
            add_styled_table(doc, section['table'])

    doc.save(output_path)
    return output_path

def add_styled_table(doc, table_data):
    """스타일링된 테이블 추가"""
    rows = len(table_data)
    cols = len(table_data[0])

    table = doc.add_table(rows=rows, cols=cols)
    table.style = 'Table Grid'

    # 헤더 행 스타일링
    header_row = table.rows[0]
    for i, cell in enumerate(header_row.cells):
        cell.text = str(table_data[0][i])
        cell.paragraphs[0].runs[0].font.bold = True
        shading = cell._element.get_or_add_tcPr()

    # 데이터 행
    for row_idx in range(1, rows):
        for col_idx in range(cols):
            table.rows[row_idx].cells[col_idx].text = str(table_data[row_idx][col_idx])

    return table
```

## Workflow 2: 기존 문서 편집 (OOXML)

### DOCX 구조 이해

```
document.docx (ZIP)
├── [Content_Types].xml
├── _rels/
├── docProps/
│   ├── app.xml
│   └── core.xml
└── word/
    ├── document.xml      # 본문 내용
    ├── styles.xml        # 스타일 정의
    ├── settings.xml      # 문서 설정
    ├── fontTable.xml     # 폰트 테이블
    ├── numbering.xml     # 번호 매기기
    └── _rels/
```

### 텍스트 교체 스크립트

```python
from docx import Document
import re

def replace_text_in_docx(docx_path, replacements, output_path):
    """문서 전체에서 텍스트 교체"""
    doc = Document(docx_path)

    # 본문 단락
    for para in doc.paragraphs:
        for old_text, new_text in replacements.items():
            if old_text in para.text:
                for run in para.runs:
                    run.text = run.text.replace(old_text, new_text)

    # 테이블 내 텍스트
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for old_text, new_text in replacements.items():
                        if old_text in para.text:
                            for run in para.runs:
                                run.text = run.text.replace(old_text, new_text)

    doc.save(output_path)
    return output_path

# 사용 예시
replacements = {
    "{{브랜드명}}": "Dante Coffee",
    "{{날짜}}": "2024년 1월 15일",
    "{{담당자}}": "김마케팅"
}
replace_text_in_docx("template.docx", replacements, "output.docx")
```

## Workflow 3: 변경 추적 (Redlining)

### 변경 사항 추출

```bash
# pandoc을 사용한 tracked changes 추출
pandoc input.docx --track-changes=all -o output.md

# 변경 사항만 추출
pandoc input.docx --track-changes=accept -o accepted.md
pandoc input.docx --track-changes=reject -o original.md
```

### 변경 추적 활성화

```python
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def enable_track_changes(docx_path, output_path):
    """변경 추적 활성화"""
    doc = Document(docx_path)

    settings = doc.settings.element
    trackChanges = OxmlElement('w:trackRevisions')
    settings.append(trackChanges)

    doc.save(output_path)
```

## 마케팅 문서 디자인 가이드

### 컬러 팔레트

```
제목:        #1a365d (Navy)
부제목:      #2b6cb0 (Blue)
강조:        #ed8936 (Orange)
본문:        #2d3748 (Dark Gray)
배경:        #ffffff (White)
테이블 헤더: #f7fafc (Light Gray)
```

### 타이포그래피

| 요소 | 폰트 | 크기 | 스타일 |
|------|------|------|--------|
| 문서 제목 | 맑은 고딕 | 28pt | Bold |
| 장 제목 (H1) | 맑은 고딕 | 18pt | Bold |
| 절 제목 (H2) | 맑은 고딕 | 14pt | Bold |
| 소제목 (H3) | 맑은 고딕 | 12pt | Bold |
| 본문 | 맑은 고딕 | 11pt | Regular |
| 캡션 | 맑은 고딕 | 9pt | Italic |

### 페이지 레이아웃

```
┌─────────────────────────────────────┐
│  [로고]          마케팅 기획서       │ ← 헤더 (15mm)
├─────────────────────────────────────┤
│                                     │
│  ← 좌측 여백 25mm    우측 여백 25mm →│
│                                     │
│  # 1. 프로젝트 개요                  │
│                                     │
│  Lorem ipsum dolor sit amet...      │
│                                     │
│  ## 1.1 배경                        │
│                                     │
│  [본문 내용]                         │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      테이블 / 도표           │    │
│  └─────────────────────────────┘    │
│                                     │
├─────────────────────────────────────┤
│  Dante Labs    Confidential    p.1  │ ← 푸터 (15mm)
└─────────────────────────────────────┘
```

### 스타일 가이드

#### 리스트 스타일
```
• 1단계 글머리 기호 (원형)
  ◦ 2단계 글머리 기호 (빈 원형)
    ▪ 3단계 글머리 기호 (사각형)

1. 1단계 번호
   a. 2단계 영문
      i. 3단계 로마자
```

#### 인용구
```
┌────────────────────────────────────┐
│  "핵심 인사이트나 중요한 인용구를    │
│   강조할 때 사용합니다."            │
│                        - 출처      │
└────────────────────────────────────┘
```

## 마케팅 문서 유형별 템플릿

### 1. 마케팅 기획서

```markdown
# 마케팅 기획서

## 1. Executive Summary
- 핵심 목표
- 예상 성과
- 필요 예산

## 2. 현황 분석
### 2.1 시장 현황
### 2.2 경쟁 환경
### 2.3 SWOT 분석

## 3. 마케팅 전략
### 3.1 목표 설정
### 3.2 타겟 정의
### 3.3 포지셔닝

## 4. 실행 계획
### 4.1 채널 전략
### 4.2 콘텐츠 계획
### 4.3 일정표

## 5. 예산
| 항목 | 금액 | 비고 |
|------|------|------|

## 6. KPI 및 평가
```

### 2. 브랜드 가이드라인

```markdown
# 브랜드 가이드라인

## 1. 브랜드 소개
### 1.1 브랜드 스토리
### 1.2 미션 & 비전
### 1.3 핵심 가치

## 2. 로고 사용 가이드
### 2.1 로고 버전
### 2.2 최소 크기
### 2.3 금지 사항

## 3. 컬러 시스템
### 3.1 Primary Colors
### 3.2 Secondary Colors
### 3.3 사용 비율

## 4. 타이포그래피
### 4.1 한글 서체
### 4.2 영문 서체
### 4.3 사용 지침

## 5. 적용 사례
```

### 3. 캠페인 브리프

```markdown
# 캠페인 브리프

## 1. 프로젝트 개요
| 항목 | 내용 |
|------|------|
| 프로젝트명 | |
| 기간 | |
| 담당자 | |
| 예산 | |

## 2. 배경 및 목적

## 3. 타겟 오디언스
### 3.1 인구통계
### 3.2 심리특성
### 3.3 행동패턴

## 4. 핵심 메시지

## 5. 채널 및 포맷

## 6. 일정

## 7. 성과 지표
```

## 템플릿 변수 시스템

### 표준 변수

```
{{브랜드명}}      - 브랜드 이름
{{프로젝트명}}    - 프로젝트 명칭
{{날짜}}          - 문서 작성일
{{버전}}          - 문서 버전
{{담당자}}        - 담당자 이름
{{부서}}          - 부서명
{{기간_시작}}     - 프로젝트 시작일
{{기간_종료}}     - 프로젝트 종료일
{{예산}}          - 예산 금액
```

### 자동 치환 스크립트

```python
import re
from datetime import datetime

STANDARD_REPLACEMENTS = {
    "{{날짜}}": datetime.now().strftime("%Y년 %m월 %d일"),
    "{{연도}}": datetime.now().strftime("%Y"),
}

def apply_template_variables(docx_path, custom_vars, output_path):
    """템플릿 변수 적용"""
    # 표준 변수 + 사용자 정의 변수
    all_vars = {**STANDARD_REPLACEMENTS, **custom_vars}
    return replace_text_in_docx(docx_path, all_vars, output_path)
```

## File Storage

Word 문서는 프로젝트의 표준 디렉토리 구조에 저장합니다.

```
{project}/
├── reports/
│   ├── documents/           # 최종 Word 문서
│   │   ├── marketing-plan-20240115.docx
│   │   ├── brand-guidelines-20240115.docx
│   │   └── campaign-brief-20240115.docx
│   └── drafts/              # 초안 및 검토 중 문서
│       └── marketing-plan-draft-v2.docx
├── assets/
│   └── docx-resources/      # 문서 리소스
│       ├── templates/       # 템플릿 파일
│       └── images/          # 삽입용 이미지
└── tmp/
    └── docx-work/           # 작업 파일
```

### 파일 명명 규칙

```
{project}/reports/documents/{type}-{subject}-{date}.docx

예시:
reports/documents/marketing-plan-q1-20240115.docx
reports/documents/brand-guidelines-dante-coffee-20240115.docx
reports/documents/campaign-brief-spring-20240115.docx
```

### 버전 관리

```
{filename}-v{version}.docx
{filename}-draft-v{version}.docx
{filename}-final.docx

예시:
marketing-plan-v1.docx
marketing-plan-v2.docx
marketing-plan-final.docx
```

## 패키지 설치

```bash
# 필수 패키지
pip install python-docx

# 선택적 패키지
# pandoc (시스템 설치 필요)
brew install pandoc  # macOS
apt install pandoc   # Ubuntu
```

## 스크립트 및 레퍼런스

### 레퍼런스 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| OOXML 편집 가이드 | `ooxml.md` | Word XML 편집 및 Tracked Changes 가이드 |

### 스크립트

| 스크립트 | 경로 | 설명 |
|---------|------|------|
| document.py | `scripts/` | Document 클래스 (댓글, 변경 추적) |
| utilities.py | `scripts/` | XMLEditor 유틸리티 |

### OOXML 도구

| 스크립트 | 경로 | 설명 |
|---------|------|------|
| unpack.py | `ooxml/scripts/unpack.py` | DOCX → XML 추출 (RSID 생성) |
| pack.py | `ooxml/scripts/pack.py` | XML → DOCX 패킹 |
| validate.py | `ooxml/scripts/validate.py` | XML 스키마 및 Redlining 검증 |

### 템플릿 파일

| 파일 | 경로 | 설명 |
|-----|------|------|
| comments.xml | `scripts/templates/` | 댓글 템플릿 |
| commentsExtended.xml | `scripts/templates/` | 확장 댓글 템플릿 |
| commentsExtensible.xml | `scripts/templates/` | 확장 가능 댓글 템플릿 |
| commentsIds.xml | `scripts/templates/` | 댓글 ID 템플릿 |
| people.xml | `scripts/templates/` | 작성자 정보 템플릿 |

## Usage

이 스킬은 `brand-strategist`, `copy-strategist`, `campaign-director` 에이전트가 마케팅 문서 제작 시 참조합니다.
