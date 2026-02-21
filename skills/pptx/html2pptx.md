# HTML to PowerPoint Conversion Guide

마케팅 프레젠테이션 제작을 위한 HTML → PPTX 변환 가이드입니다.

## Overview

HTML 슬라이드를 PowerPoint 슬라이드로 변환합니다. `html2pptx.js` 스크립트를 사용합니다.

## Workflow

```
[콘텐츠 기획] → [HTML 작성] → [html2pptx 변환] → [검증]
```

## HTML Slide Rules

### 1. 문서 구조

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 960px;   /* 10인치 × 96 DPI */
      height: 540px;  /* 5.625인치 × 96 DPI (16:9) */
      margin: 0;
      padding: 0;
    }
  </style>
</head>
<body>
  <!-- 슬라이드 콘텐츠 -->
</body>
</html>
```

### 2. 슬라이드 크기 (16:9 기준)

| 단위 | 너비 | 높이 |
|------|------|------|
| 인치 | 10" | 5.625" |
| 픽셀 (96 DPI) | 960px | 540px |
| 포인트 | 720pt | 405pt |

### 3. 지원되는 요소

| HTML 요소 | PowerPoint 변환 |
|-----------|----------------|
| `<h1>` - `<h6>` | 텍스트 박스 |
| `<p>` | 텍스트 박스 |
| `<ul>`, `<ol>` | 글머리 기호 목록 |
| `<img>` | 이미지 |
| `<div>` (배경/테두리) | 도형 |

### 4. 지원되는 CSS 속성

```css
/* 텍스트 스타일 */
font-family: 'Pretendard', sans-serif;
font-size: 24pt;
font-weight: bold;        /* bold 지원 */
font-style: italic;       /* italic 지원 */
text-decoration: underline;
text-transform: uppercase;
color: #1a365d;
text-align: center;

/* 레이아웃 */
position: absolute;
left: 100px;
top: 50px;
width: 400px;
height: auto;

/* 도형 (div만 지원) */
background-color: #f7fafc;
border: 2px solid #e2e8f0;
border-radius: 10px;
box-shadow: 2px 2px 8px rgba(0,0,0,0.3);
```

### 5. 주의사항

**금지되는 패턴:**
- CSS 그라디언트 (`linear-gradient`, `radial-gradient`) - 이미지로 대체
- 텍스트 요소(`<p>`, `<h1>` 등)에 `background`, `border`, `box-shadow`
- `<div>` 내 직접 텍스트 (반드시 `<p>`, `<h1>` 등으로 감싸야 함)
- 수동 글머리 기호 (`•`, `-`, `*` 등) - `<ul>`, `<ol>` 사용

**인라인 요소 제한:**
- `<span>`, `<b>`, `<i>`, `<u>`, `<strong>`, `<em>`에 margin 사용 불가

## 마케팅 슬라이드 템플릿

### 표지 슬라이드

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 960px;
      height: 540px;
      margin: 0;
      background-color: #1a365d;
    }
    .title {
      position: absolute;
      left: 80px;
      top: 200px;
      width: 800px;
      font-family: 'Pretendard', sans-serif;
      font-size: 48pt;
      font-weight: bold;
      color: white;
      text-align: center;
    }
    .subtitle {
      position: absolute;
      left: 80px;
      top: 300px;
      width: 800px;
      font-family: 'Pretendard', sans-serif;
      font-size: 24pt;
      color: #ed8936;
      text-align: center;
    }
    .date {
      position: absolute;
      right: 80px;
      bottom: 40px;
      font-family: 'Pretendard', sans-serif;
      font-size: 14pt;
      color: rgba(255,255,255,0.7);
    }
  </style>
</head>
<body>
  <h1 class="title">브랜드 캠페인 제안서</h1>
  <p class="subtitle">2024년 1분기 마케팅 전략</p>
  <p class="date">2024.01</p>
</body>
</html>
```

### 섹션 구분 슬라이드

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 960px;
      height: 540px;
      margin: 0;
      background-color: #2b6cb0;
    }
    .section-number {
      position: absolute;
      left: 80px;
      top: 180px;
      font-family: 'Pretendard', sans-serif;
      font-size: 72pt;
      font-weight: bold;
      color: white;
    }
    .section-title {
      position: absolute;
      left: 80px;
      top: 300px;
      font-family: 'Pretendard', sans-serif;
      font-size: 36pt;
      font-weight: bold;
      color: white;
    }
    .divider {
      position: absolute;
      left: 80px;
      top: 280px;
      width: 100px;
      height: 4px;
      background-color: #ed8936;
    }
  </style>
</head>
<body>
  <p class="section-number">01</p>
  <div class="divider"></div>
  <h2 class="section-title">브랜드 분석</h2>
</body>
</html>
```

### 2분할 콘텐츠 슬라이드

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 960px;
      height: 540px;
      margin: 0;
      background-color: white;
    }
    .title {
      position: absolute;
      left: 60px;
      top: 40px;
      font-family: 'Pretendard', sans-serif;
      font-size: 28pt;
      font-weight: bold;
      color: #1a365d;
    }
    .left-panel {
      position: absolute;
      left: 60px;
      top: 100px;
      width: 420px;
      height: 380px;
      background-color: #f7fafc;
      border-radius: 10px;
    }
    .right-panel {
      position: absolute;
      left: 500px;
      top: 100px;
      width: 400px;
    }
    .bullet-list {
      position: absolute;
      left: 500px;
      top: 100px;
      font-family: 'Pretendard', sans-serif;
      font-size: 18pt;
      color: #2d3748;
      line-height: 2;
    }
  </style>
</head>
<body>
  <h1 class="title">핵심 전략</h1>
  <div class="left-panel"></div>
  <ul class="bullet-list">
    <li>타겟 오디언스 재정의</li>
    <li>채널 믹스 최적화</li>
    <li>콘텐츠 전략 수립</li>
  </ul>
</body>
</html>
```

### 데이터 시각화 슬라이드

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      width: 960px;
      height: 540px;
      margin: 0;
      background-color: white;
    }
    .title {
      position: absolute;
      left: 60px;
      top: 40px;
      font-family: 'Pretendard', sans-serif;
      font-size: 28pt;
      font-weight: bold;
      color: #1a365d;
    }
    .metric-box {
      position: absolute;
      width: 260px;
      height: 120px;
      background-color: #f7fafc;
      border-radius: 8px;
      border-left: 4px solid #ed8936;
    }
    .metric-value {
      position: absolute;
      font-family: 'Pretendard', sans-serif;
      font-size: 36pt;
      font-weight: bold;
      color: #1a365d;
    }
    .metric-label {
      position: absolute;
      font-family: 'Pretendard', sans-serif;
      font-size: 14pt;
      color: #718096;
    }
    .chart-placeholder {
      position: absolute;
      left: 60px;
      top: 280px;
      width: 840px;
      height: 220px;
      background-color: #edf2f7;
      border-radius: 8px;
    }
  </style>
</head>
<body>
  <h1 class="title">캠페인 성과</h1>

  <!-- 지표 박스들 -->
  <div class="metric-box" style="left: 60px; top: 100px;"></div>
  <p class="metric-value" style="left: 80px; top: 115px;">45%</p>
  <p class="metric-label" style="left: 80px; top: 175px;">전환율</p>

  <div class="metric-box" style="left: 350px; top: 100px;"></div>
  <p class="metric-value" style="left: 370px; top: 115px;">128K</p>
  <p class="metric-label" style="left: 370px; top: 175px;">도달 수</p>

  <div class="metric-box" style="left: 640px; top: 100px;"></div>
  <p class="metric-value" style="left: 660px; top: 115px;">+23%</p>
  <p class="metric-label" style="left: 660px; top: 175px;">성장률</p>

  <!-- 차트 영역 (placeholder) -->
  <div class="chart-placeholder placeholder" id="chart-area"></div>
</body>
</html>
```

## 스크립트 사용법

### html2pptx.js

```javascript
const pptxgen = require('pptxgenjs');
const html2pptx = require('./scripts/html2pptx');

async function createPresentation() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';

  // HTML 슬라이드 변환
  const { slide, placeholders } = await html2pptx('slide1.html', pptx);

  // placeholder 영역에 차트 추가
  if (placeholders.length > 0) {
    slide.addChart(pptx.charts.LINE, chartData, placeholders[0]);
  }

  await pptx.writeFile('output.pptx');
}
```

### 차트/테이블 추가 (PptxGenJS)

```javascript
// 차트 추가
slide.addChart(pptx.charts.BAR, [
  { name: 'Q1', labels: ['Jan', 'Feb', 'Mar'], values: [10, 20, 30] },
  { name: 'Q2', labels: ['Jan', 'Feb', 'Mar'], values: [15, 25, 35] }
], {
  x: placeholders[0].x,
  y: placeholders[0].y,
  w: placeholders[0].w,
  h: placeholders[0].h,
  showTitle: false,
  chartColors: ['#1a365d', '#ed8936']
});

// 테이블 추가
slide.addTable([
  ['항목', 'Q1', 'Q2', 'Q3'],
  ['매출', '100M', '120M', '150M'],
  ['비용', '80M', '90M', '100M']
], {
  x: 0.5,
  y: 2,
  w: 9,
  colW: [2, 2.3, 2.3, 2.3],
  color: '2d3748',
  border: { type: 'solid', color: 'e2e8f0' },
  fontFace: 'Pretendard'
});
```

## 검증

### 변환 전 체크리스트

- [ ] body 크기가 슬라이드 레이아웃과 일치
- [ ] 모든 텍스트가 `<p>`, `<h1>`-`<h6>`, `<ul>`, `<ol>` 내에 있음
- [ ] `<div>`에 직접 텍스트 없음
- [ ] CSS 그라디언트 사용 안함
- [ ] 텍스트 요소에 background/border 사용 안함
- [ ] 하단 여백 0.5인치 이상 확보

### 에러 대응

| 에러 메시지 | 원인 | 해결 |
|------------|------|------|
| "HTML content overflows body" | 콘텐츠가 body 크기 초과 | 요소 위치/크기 조정 |
| "CSS gradients are not supported" | 그라디언트 사용 | PNG 이미지로 대체 |
| "contains unwrapped text" | div 내 직접 텍스트 | p/h 태그로 감싸기 |

## 파일 저장 위치

```
{project}/
├── reports/presentations/           # 최종 PPTX
│   └── campaign-proposal-20240115.pptx
├── assets/pptx-resources/           # 슬라이드 리소스
│   ├── html/                        # HTML 슬라이드 소스
│   ├── images/                      # 삽입 이미지
│   └── templates/                   # 템플릿
└── tmp/pptx-work/                   # 작업 파일
```

## 참고

- [PptxGenJS Documentation](https://gitbrent.github.io/PptxGenJS/)
- 스크립트 위치: `plugins/common/skills/pptx/scripts/html2pptx.js`
