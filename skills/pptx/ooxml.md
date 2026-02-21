# PowerPoint OOXML 편집 가이드

마케팅 프레젠테이션의 직접 XML 편집을 위한 OOXML 가이드입니다.

## Overview

PPTX 파일은 ZIP 압축된 XML 파일 모음입니다. 세밀한 수정이 필요할 때 직접 XML을 편집합니다.

## Workflow

```
[원본 PPTX] → [unpack] → [XML 편집] → [validate] → [pack] → [최종 PPTX]
```

## PPTX 파일 구조

```
presentation.pptx/
├── [Content_Types].xml          # 콘텐츠 타입 정의
├── _rels/
│   └── .rels                    # 최상위 관계
├── docProps/
│   ├── app.xml                  # 응용 프로그램 속성
│   └── core.xml                 # 핵심 속성 (제목, 작성자)
└── ppt/
    ├── presentation.xml         # 프레젠테이션 정의
    ├── presProps.xml            # 프레젠테이션 속성
    ├── tableStyles.xml          # 테이블 스타일
    ├── viewProps.xml            # 보기 속성
    ├── _rels/
    │   └── presentation.xml.rels
    ├── slideLayouts/            # 슬라이드 레이아웃
    │   ├── slideLayout1.xml
    │   └── _rels/
    ├── slideMasters/            # 슬라이드 마스터
    │   ├── slideMaster1.xml
    │   └── _rels/
    ├── slides/                  # 실제 슬라이드
    │   ├── slide1.xml
    │   ├── slide2.xml
    │   └── _rels/
    ├── theme/                   # 테마
    │   └── theme1.xml
    └── media/                   # 이미지, 비디오 등
        ├── image1.png
        └── image2.jpg
```

## 스크립트 사용법

### 1. PPTX 언팩 (XML 추출)

```bash
python ooxml/scripts/unpack.py presentation.pptx ./unpacked_pptx/
```

**결과**: XML 파일들이 pretty-print 되어 편집 가능한 형태로 추출됩니다.

### 2. XML 편집

편집할 주요 파일:
- `ppt/slides/slideN.xml` - 개별 슬라이드 내용
- `ppt/presentation.xml` - 슬라이드 순서, 크기
- `ppt/slideMasters/slideMaster1.xml` - 마스터 스타일
- `ppt/theme/theme1.xml` - 색상, 폰트 테마

### 3. 검증

```bash
python ooxml/scripts/validate.py ./unpacked_pptx/ --original presentation.pptx
```

### 4. PPTX 리팩 (XML → PPTX)

```bash
python ooxml/scripts/pack.py ./unpacked_pptx/ output.pptx
```

`--force` 옵션: 검증 건너뛰기 (권장하지 않음)

## 주요 네임스페이스

```xml
xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
```

| 접두사 | 네임스페이스 | 용도 |
|--------|-------------|------|
| `p:` | PresentationML | 프레젠테이션 구조 |
| `a:` | DrawingML | 도형, 텍스트, 이미지 |
| `r:` | Relationships | 리소스 참조 |

## 마케팅 슬라이드 XML 예시

### 텍스트 박스 수정

**파일**: `ppt/slides/slide1.xml`

```xml
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="2" name="Title 1"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm>
      <a:off x="457200" y="274638"/>  <!-- 위치 (EMU 단위) -->
      <a:ext cx="8229600" cy="1143000"/>  <!-- 크기 -->
    </a:xfrm>
  </p:spPr>
  <p:txBody>
    <a:bodyPr/>
    <a:lstStyle/>
    <a:p>
      <a:r>
        <a:rPr lang="ko-KR" sz="4400" b="1">  <!-- 폰트 크기: 44pt -->
          <a:solidFill>
            <a:srgbClr val="1A365D"/>  <!-- 색상 -->
          </a:solidFill>
          <a:latin typeface="Pretendard"/>
        </a:rPr>
        <a:t>브랜드 캠페인 제안서</a:t>
      </a:r>
    </a:p>
  </p:txBody>
</p:sp>
```

### 이미지 추가

**1단계**: 이미지 파일을 `ppt/media/`에 추가

**2단계**: `ppt/slides/_rels/slideN.xml.rels`에 관계 추가
```xml
<Relationship
  Id="rId2"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
  Target="../media/image1.png"/>
```

**3단계**: 슬라이드 XML에 이미지 도형 추가
```xml
<p:pic>
  <p:nvPicPr>
    <p:cNvPr id="4" name="Picture 1"/>
    <p:cNvPicPr/>
    <p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="rId2"/>
    <a:stretch>
      <a:fillRect/>
    </a:stretch>
  </p:blipFill>
  <p:spPr>
    <a:xfrm>
      <a:off x="914400" y="1524000"/>
      <a:ext cx="4572000" cy="3429000"/>
    </a:xfrm>
    <a:prstGeom prst="rect"/>
  </p:spPr>
</p:pic>
```

### 도형 (사각형)

```xml
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="5" name="Rectangle 1"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm>
      <a:off x="914400" y="914400"/>
      <a:ext cx="3657600" cy="2743200"/>
    </a:xfrm>
    <a:prstGeom prst="rect"/>
    <a:solidFill>
      <a:srgbClr val="F7FAFC"/>
    </a:solidFill>
    <a:ln w="25400">  <!-- 테두리 두께: 2pt -->
      <a:solidFill>
        <a:srgbClr val="E2E8F0"/>
      </a:solidFill>
    </a:ln>
  </p:spPr>
</p:sp>
```

## 단위 변환

PowerPoint OOXML은 EMU(English Metric Units) 사용:

| 단위 | EMU 변환 |
|------|----------|
| 1 인치 | 914,400 EMU |
| 1 포인트 | 12,700 EMU |
| 1 픽셀 (96 DPI) | 9,525 EMU |
| 1 센티미터 | 360,000 EMU |

**변환 공식**:
```python
def inches_to_emu(inches):
    return int(inches * 914400)

def pt_to_emu(points):
    return int(points * 12700)

def px_to_emu(pixels, dpi=96):
    return int(pixels * 914400 / dpi)
```

## 슬라이드 재배열

`scripts/rearrange.py` 사용:

```bash
python scripts/rearrange.py template.pptx output.pptx 0,3,1,2,4
```

**설명**:
- 0번 슬라이드 → 첫 번째
- 3번 슬라이드 → 두 번째
- 1번 슬라이드 → 세 번째
- ...

**슬라이드 복제**: 같은 인덱스 반복
```bash
python scripts/rearrange.py template.pptx output.pptx 0,1,1,2  # 1번 슬라이드 2번 사용
```

## 마케팅 템플릿 수정 패턴

### 브랜드 컬러 일괄 변경

`ppt/theme/theme1.xml`에서 색상 스킴 수정:

```xml
<a:clrScheme name="Dante Coffee">
  <a:dk1><a:srgbClr val="1A365D"/></a:dk1>  <!-- 진한 네이비 -->
  <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>  <!-- 흰색 -->
  <a:dk2><a:srgbClr val="2D3748"/></a:dk2>  <!-- 다크 그레이 -->
  <a:lt2><a:srgbClr val="F7FAFC"/></a:lt2>  <!-- 라이트 그레이 -->
  <a:accent1><a:srgbClr val="ED8936"/></a:accent1>  <!-- 오렌지 강조 -->
  <a:accent2><a:srgbClr val="2B6CB0"/></a:accent2>  <!-- 블루 강조 -->
</a:clrScheme>
```

### 폰트 일괄 변경

`ppt/theme/theme1.xml`에서 폰트 스킴 수정:

```xml
<a:fontScheme name="Dante Coffee Fonts">
  <a:majorFont>
    <a:latin typeface="Pretendard"/>
    <a:ea typeface="Pretendard"/>
    <a:cs typeface="Pretendard"/>
  </a:majorFont>
  <a:minorFont>
    <a:latin typeface="Pretendard"/>
    <a:ea typeface="Pretendard"/>
    <a:cs typeface="Pretendard"/>
  </a:minorFont>
</a:fontScheme>
```

### 슬라이드 크기 변경

`ppt/presentation.xml`에서:

```xml
<!-- 16:9 (기본) -->
<p:sldSz cx="9144000" cy="5143500"/>

<!-- 4:3 -->
<p:sldSz cx="9144000" cy="6858000"/>

<!-- A4 -->
<p:sldSz cx="9906000" cy="6858000"/>
```

## Content_Types.xml 관리

새 미디어 타입 추가 시 `[Content_Types].xml` 수정:

```xml
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="gif" ContentType="image/gif"/>
  <Default Extension="mp4" ContentType="video/mp4"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <!-- 슬라이드별 오버라이드 -->
  <Override PartName="/ppt/slides/slide1.xml"
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>
```

## 검증 체크리스트

- [ ] 모든 `r:embed` 참조가 유효한 관계 ID를 가리킴
- [ ] `[Content_Types].xml`에 모든 파일 타입 등록
- [ ] 슬라이드 번호가 `presentation.xml`의 `p:sldIdLst`와 일치
- [ ] 네임스페이스 선언 완전함
- [ ] XML 구문 유효함 (닫는 태그 등)

## 에러 대응

| 에러 | 원인 | 해결 |
|------|------|------|
| "Part not found" | 관계 파일에서 참조된 파일 없음 | `_rels/` 파일 확인 |
| "Invalid XML" | XML 구문 오류 | pretty-print 후 수정 |
| "Corrupt file" | Content_Types 누락 | 확장자 등록 확인 |

## 파일 저장 위치

```
{project}/
├── reports/presentations/           # 최종 PPTX
├── assets/pptx-resources/           # 리소스
│   └── unpacked/                    # 언팩된 XML
└── tmp/pptx-work/                   # 작업 파일
```

## 참고

- [ECMA-376 (OOXML 표준)](https://www.ecma-international.org/publications-and-standards/standards/ecma-376/)
- 스크립트 위치: `plugins/common/skills/pptx/ooxml/scripts/`
