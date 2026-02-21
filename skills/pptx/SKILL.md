---
name: pptx
description: 마케팅 프레젠테이션 제작을 위한 PowerPoint 생성/편집 도구
version: 1.0.0
author: Dante Labs
tags:
  - presentation
  - powerpoint
  - marketing
  - design
---

# Marketing Presentation Toolkit

마케팅 캠페인, 브랜드 소개, 제안서 등 전문 프레젠테이션을 제작하기 위한 도구입니다.

## 주요 기능

| 기능 | 설명 | 용도 |
|------|------|------|
| 새 프레젠테이션 생성 | HTML → PPTX 변환 | 캠페인 제안서, 브랜드 소개 |
| 기존 파일 편집 | OOXML 직접 편집 | 텍스트 수정, 레이아웃 조정 |
| 템플릿 기반 생성 | 기업 템플릿 활용 | 일관된 브랜드 가이드 적용 |
| 썸네일 생성 | 슬라이드 미리보기 | 검증 및 승인 |

## Workflow 1: 새 프레젠테이션 생성 (HTML → PPTX)

### 단계별 프로세스

```
[콘텐츠 기획] → [HTML 작성] → [PPTX 변환] → [검증]
```

### 1. HTML 파일 작성

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    /* 브랜드 컬러 정의 */
    :root {
      --primary: #1a365d;
      --accent: #ed8936;
      --text: #2d3748;
    }
    .slide { page-break-after: always; }
    h1 { color: var(--primary); font-size: 36pt; }
    h2 { color: var(--accent); font-size: 28pt; }
  </style>
</head>
<body>
  <div class="slide">
    <h1>브랜드 소개</h1>
    <p>우리 브랜드의 핵심 가치</p>
  </div>
  <div class="slide">
    <h2>캠페인 전략</h2>
    <ul>
      <li>타겟 오디언스</li>
      <li>채널 믹스</li>
      <li>예상 KPI</li>
    </ul>
  </div>
</body>
</html>
```

### 2. PPTX 변환

```bash
# html2pptx 설치
pip install html2pptx

# 변환 실행
python -c "
from html2pptx import Html2Pptx

with open('presentation.html', 'r') as f:
    html_content = f.read()

pptx = Html2Pptx(html_content)
pptx.save('presentation.pptx')
"
```

## Workflow 2: 기존 PPTX 편집 (OOXML)

### PPTX 구조 이해

```
presentation.pptx (ZIP)
├── [Content_Types].xml
├── _rels/
├── docProps/
├── ppt/
│   ├── presentation.xml
│   ├── slides/
│   │   ├── slide1.xml
│   │   ├── slide2.xml
│   │   └── ...
│   ├── slideLayouts/
│   ├── slideMasters/
│   └── theme/
└── ...
```

### 편집 스크립트 예시

```python
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil

def edit_slide_text(pptx_path, slide_num, old_text, new_text):
    """슬라이드 텍스트 교체"""
    temp_dir = Path('temp_pptx')

    # PPTX 압축 해제
    with zipfile.ZipFile(pptx_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # 슬라이드 XML 수정
    slide_path = temp_dir / f'ppt/slides/slide{slide_num}.xml'
    tree = ET.parse(slide_path)

    for elem in tree.iter():
        if elem.text and old_text in elem.text:
            elem.text = elem.text.replace(old_text, new_text)

    tree.write(slide_path, xml_declaration=True, encoding='UTF-8')

    # 새 PPTX 생성
    output_path = pptx_path.replace('.pptx', '_edited.pptx')
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in temp_dir.rglob('*'):
            if file.is_file():
                zipf.write(file, file.relative_to(temp_dir))

    shutil.rmtree(temp_dir)
    return output_path
```

## 마케팅 디자인 가이드

### 컬러 팔레트

#### 1. 프로페셔널 (B2B/기업)
```
Primary:   #1a365d (Navy)
Secondary: #2b6cb0 (Blue)
Accent:    #ed8936 (Orange)
Text:      #2d3748 (Dark Gray)
Background:#f7fafc (Light Gray)
```

#### 2. 모던 & 트렌디 (스타트업)
```
Primary:   #553c9a (Purple)
Secondary: #805ad5 (Violet)
Accent:    #38b2ac (Teal)
Text:      #1a202c (Black)
Background:#ffffff (White)
```

#### 3. 따뜻함 & 친근함 (F&B/라이프스타일)
```
Primary:   #744210 (Brown)
Secondary: #c05621 (Orange)
Accent:    #2f855a (Green)
Text:      #1a202c (Black)
Background:#fffaf0 (Warm White)
```

#### 4. 럭셔리 & 프리미엄
```
Primary:   #1a202c (Black)
Secondary: #b7791f (Gold)
Accent:    #c53030 (Red)
Text:      #2d3748 (Dark Gray)
Background:#f7fafc (Off-White)
```

### 타이포그래피

| 용도 | 추천 폰트 | 크기 |
|------|----------|------|
| 제목 | Pretendard Bold, Noto Sans KR Bold | 36-48pt |
| 부제목 | Pretendard SemiBold | 24-32pt |
| 본문 | Pretendard Regular | 18-24pt |
| 캡션 | Pretendard Light | 14-16pt |

### 슬라이드 구성 템플릿

#### 표지 슬라이드
```
┌─────────────────────────────────────┐
│                                     │
│         [로고]                       │
│                                     │
│    ████████████████████            │
│         메인 제목                    │
│    ────────────────────            │
│         부제목                       │
│                                     │
│                    2024.01          │
└─────────────────────────────────────┘
```

#### 섹션 구분 슬라이드
```
┌─────────────────────────────────────┐
│                                     │
│         01                          │
│    ════════════                    │
│    BRAND ANALYSIS                   │
│    브랜드 분석                       │
│                                     │
└─────────────────────────────────────┘
```

#### 2분할 레이아웃
```
┌─────────────────────────────────────┐
│  제목                               │
├────────────────┬────────────────────┤
│                │                    │
│   [이미지]      │   • 포인트 1       │
│                │   • 포인트 2       │
│                │   • 포인트 3       │
│                │                    │
└────────────────┴────────────────────┘
```

#### 데이터 시각화 슬라이드
```
┌─────────────────────────────────────┐
│  핵심 지표                           │
├───────────┬───────────┬─────────────┤
│           │           │             │
│   45%     │   128K    │   +23%      │
│  전환율    │   도달     │   성장률    │
│           │           │             │
├───────────┴───────────┴─────────────┤
│                                     │
│        [차트/그래프]                 │
│                                     │
└─────────────────────────────────────┘
```

## 마케팅 프레젠테이션 유형별 구조

### 1. 캠페인 제안서

```
1. 표지
2. 목차
3. 현황 분석 (As-Is)
4. 목표 설정
5. 타겟 정의
6. 전략 개요
7. 채널 믹스
8. 콘텐츠 계획
9. 예산 및 일정
10. 기대 효과
11. Q&A
```

### 2. 브랜드 소개서

```
1. 표지
2. 브랜드 스토리
3. 미션 & 비전
4. 핵심 가치
5. 제품/서비스 라인업
6. 차별화 포인트
7. 고객 사례
8. 연락처
```

### 3. 분석 리포트

```
1. 표지
2. Executive Summary
3. 분석 배경
4. 데이터 개요
5. 주요 발견 (Insights)
6. 상세 분석
7. 시사점
8. 액션 플랜
```

## 검증 프로세스

### 썸네일 생성

```python
from pptx import Presentation
from pdf2image import convert_from_path
import subprocess

def generate_thumbnails(pptx_path, output_dir):
    """슬라이드 썸네일 생성"""
    # PPTX → PDF 변환 (LibreOffice)
    subprocess.run([
        'soffice', '--headless', '--convert-to', 'pdf',
        '--outdir', output_dir, pptx_path
    ])

    pdf_path = pptx_path.replace('.pptx', '.pdf')

    # PDF → 이미지
    images = convert_from_path(pdf_path, dpi=150)

    for i, image in enumerate(images, 1):
        image.save(f'{output_dir}/slide_{i:02d}.png', 'PNG')
```

## File Storage

프레젠테이션 파일은 프로젝트의 표준 디렉토리 구조에 저장합니다.

```
{project}/
├── reports/
│   └── presentations/       # 최종 프레젠테이션
│       ├── campaign-proposal-20240115.pptx
│       ├── brand-intro-20240115.pptx
│       └── analysis-report-20240115.pptx
├── assets/
│   └── pptx-resources/      # 프레젠테이션 리소스
│       ├── templates/       # 템플릿 파일
│       ├── images/          # 삽입용 이미지
│       └── thumbnails/      # 썸네일 미리보기
└── tmp/
    └── pptx-drafts/         # 초안 및 작업 파일
```

### 파일 명명 규칙

```
{project}/reports/presentations/{type}-{subject}-{date}.pptx

예시:
reports/presentations/campaign-proposal-dante-coffee-20240115.pptx
reports/presentations/brand-intro-dante-coffee-20240115.pptx
reports/presentations/monthly-report-january-20240115.pptx
```

## 스크립트 및 레퍼런스

### 레퍼런스 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| HTML → PPTX 가이드 | `html2pptx.md` | HTML을 PPTX로 변환하는 상세 가이드 |
| OOXML 편집 가이드 | `ooxml.md` | PowerPoint XML 직접 편집 가이드 |

### 스크립트

| 스크립트 | 경로 | 설명 |
|---------|------|------|
| html2pptx.js | `scripts/html2pptx.js` | HTML → PPTX 변환 (Playwright + PptxGenJS) |
| replace.py | `scripts/replace.py` | 텍스트 일괄 교체 |
| thumbnail.py | `scripts/thumbnail.py` | 슬라이드 썸네일 생성 |
| inventory.py | `scripts/inventory.py` | 슬라이드 인벤토리 |
| rearrange.py | `scripts/rearrange.py` | 슬라이드 재배열 |

### OOXML 도구

| 스크립트 | 경로 | 설명 |
|---------|------|------|
| unpack.py | `ooxml/scripts/unpack.py` | PPTX → XML 추출 |
| pack.py | `ooxml/scripts/pack.py` | XML → PPTX 패킹 |
| validate.py | `ooxml/scripts/validate.py` | XML 스키마 검증 |

## Usage

이 스킬은 `creative-director` 및 `copy-strategist` 에이전트가 마케팅 프레젠테이션 제작 시 참조합니다.
