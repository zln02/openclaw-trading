# Word OOXML 편집 가이드

마케팅 문서의 Word OOXML 직접 편집 및 추적된 변경 사항 작업을 위한 가이드입니다.

## Overview

DOCX 파일은 ZIP 압축된 XML 파일 모음입니다. 추적된 변경 사항, 댓글, 세밀한 수정이 필요할 때 직접 XML을 편집합니다.

## Workflow

### 기본 편집 워크플로우

```
[원본 DOCX] → [unpack] → [XML 편집] → [validate] → [pack] → [최종 DOCX]
```

### Tracked Changes 워크플로우

```
[DOCX] → [unpack] → [Document 클래스로 편집] → [validate] → [pack] → [DOCX]
```

## DOCX 파일 구조

```
document.docx/
├── [Content_Types].xml          # 콘텐츠 타입 정의
├── _rels/
│   └── .rels                    # 최상위 관계
├── docProps/
│   ├── app.xml                  # 응용 프로그램 속성
│   └── core.xml                 # 핵심 속성 (제목, 작성자)
└── word/
    ├── document.xml             # 본문 콘텐츠
    ├── styles.xml               # 스타일 정의
    ├── settings.xml             # 문서 설정
    ├── fontTable.xml            # 폰트 테이블
    ├── webSettings.xml          # 웹 설정
    ├── comments.xml             # 댓글 (있는 경우)
    ├── commentsExtended.xml     # 확장 댓글
    ├── commentsExtensible.xml   # 확장 가능 댓글
    ├── commentsIds.xml          # 댓글 ID
    ├── people.xml               # 작성자 정보
    ├── numbering.xml            # 번호 매기기
    ├── footnotes.xml            # 각주
    ├── endnotes.xml             # 미주
    ├── _rels/
    │   └── document.xml.rels    # 문서 관계
    ├── theme/
    │   └── theme1.xml           # 테마
    └── media/                   # 이미지
        └── image1.png
```

## 스크립트 사용법

### 1. DOCX 언팩

```bash
python ooxml/scripts/unpack.py document.docx ./unpacked_docx/
```

**결과**:
- XML 파일들이 pretty-print 되어 추출
- RSID 제안 출력 (예: `Suggested RSID for edit session: A1B2C3D4`)

### 2. Document 클래스로 편집

```python
from scripts.document import Document

# 초기화
doc = Document('unpacked_docx', author="마케팅팀", initials="MK")

# 노드 찾기
node = doc["word/document.xml"].get_node(tag="w:p", line_number=10)

# 댓글 추가
doc.add_comment(start=node, end=node, text="검토가 필요합니다")

# 변경 사항 제안
doc["word/document.xml"].suggest_deletion(node)  # 삭제 제안

# 저장
doc.save()
```

### 3. 검증

```bash
python ooxml/scripts/validate.py ./unpacked_docx/ --original document.docx
```

**검증 항목**:
- XSD 스키마 검증
- Redlining(추적된 변경) 일관성 검증

### 4. DOCX 리팩

```bash
python ooxml/scripts/pack.py ./unpacked_docx/ output.docx
```

## 주요 네임스페이스

```xml
xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
xmlns:w16cex="http://schemas.microsoft.com/office/word/2018/wordml/cex"
xmlns:w16du="http://schemas.microsoft.com/office/word/2023/wordml/word16du"
```

| 접두사 | 네임스페이스 | 용도 |
|--------|-------------|------|
| `w:` | WordprocessingML | 문서 구조 |
| `r:` | Relationships | 리소스 참조 |
| `w14:` | Word 2010 확장 | paraId, textId |
| `w16cex:` | 댓글 확장 | 확장 댓글 |
| `w16du:` | Word 2023 확장 | dateUtc |

## 추적된 변경 사항 (Tracked Changes)

### 삽입 (Insertion)

```xml
<w:ins w:id="0" w:author="마케팅팀" w:date="2024-01-15T10:30:00Z">
  <w:r w:rsidR="A1B2C3D4">
    <w:t>새로 추가된 텍스트</w:t>
  </w:r>
</w:ins>
```

### 삭제 (Deletion)

```xml
<w:del w:id="1" w:author="마케팅팀" w:date="2024-01-15T10:30:00Z">
  <w:r w:rsidDel="A1B2C3D4">
    <w:delText>삭제된 텍스트</w:delText>
  </w:r>
</w:del>
```

### Document 클래스 메서드

```python
# 삭제 제안 (콘텐츠를 w:del로 감싸기)
doc["word/document.xml"].suggest_deletion(node)

# 삽입 취소 (w:ins 제거하고 콘텐츠 삭제)
doc["word/document.xml"].revert_insertion(ins_node)

# 삭제 취소 (w:del 제거하고 콘텐츠 복원)
doc["word/document.xml"].revert_deletion(del_node)
```

## 댓글 (Comments)

### 댓글 구조

**word/comments.xml**:
```xml
<w:comments>
  <w:comment w:id="0" w:author="마케팅팀" w:date="2024-01-15T10:30:00Z" w:initials="MK">
    <w:p>
      <w:r>
        <w:t>이 부분 수정이 필요합니다.</w:t>
      </w:r>
    </w:p>
  </w:comment>
</w:comments>
```

**word/document.xml** (댓글 범위 표시):
```xml
<w:commentRangeStart w:id="0"/>
<w:r>
  <w:t>댓글이 달린 텍스트</w:t>
</w:r>
<w:commentRangeEnd w:id="0"/>
<w:r>
  <w:commentReference w:id="0"/>
</w:r>
```

### Document 클래스로 댓글 추가

```python
from scripts.document import Document

doc = Document('unpacked_docx', author="마케팅팀", initials="MK")

# 노드 찾기
para = doc["word/document.xml"].get_node(tag="w:p", line_number=15)

# 댓글 추가
comment_id = doc.add_comment(start=para, end=para, text="검토 필요")

# 댓글에 답글
doc.reply_to_comment(parent_comment_id=comment_id, text="확인했습니다")

doc.save()
```

## RSID (Revision Session ID)

RSID는 편집 세션을 식별하는 8자리 16진수입니다.

### RSID 속성

| 속성 | 용도 |
|------|------|
| `w:rsidR` | 이 런(run)이 생성된 세션 |
| `w:rsidRDefault` | 기본 RSID |
| `w:rsidP` | 단락 속성이 마지막으로 수정된 세션 |
| `w:rsidDel` | 삭제가 발생한 세션 |

### RSID 생성

```python
import random
rsid = "".join(random.choices("0123456789ABCDEF", k=8))
# 예: "A1B2C3D4"
```

## 마케팅 문서 XML 예시

### 제목 단락

```xml
<w:p w:rsidR="00000000" w:rsidRDefault="A1B2C3D4" w:rsidP="A1B2C3D4">
  <w:pPr>
    <w:pStyle w:val="Heading1"/>
  </w:pPr>
  <w:r w:rsidR="A1B2C3D4">
    <w:t>2024년 마케팅 전략 보고서</w:t>
  </w:r>
</w:p>
```

### 글머리 기호 목록

```xml
<w:p w:rsidR="A1B2C3D4">
  <w:pPr>
    <w:pStyle w:val="ListParagraph"/>
    <w:numPr>
      <w:ilvl w:val="0"/>
      <w:numId w:val="1"/>
    </w:numPr>
  </w:pPr>
  <w:r>
    <w:t>첫 번째 항목</w:t>
  </w:r>
</w:p>
```

### 볼드/이탤릭 텍스트

```xml
<w:r>
  <w:rPr>
    <w:b/>           <!-- 볼드 -->
    <w:i/>           <!-- 이탤릭 -->
    <w:color w:val="ED8936"/>  <!-- 색상 -->
    <w:sz w:val="28"/>  <!-- 폰트 크기 (14pt = 28 half-points) -->
  </w:rPr>
  <w:t>강조된 텍스트</w:t>
</w:r>
```

### 하이퍼링크

**word/document.xml**:
```xml
<w:hyperlink r:id="rId5">
  <w:r>
    <w:rPr>
      <w:rStyle w:val="Hyperlink"/>
    </w:rPr>
    <w:t>링크 텍스트</w:t>
  </w:r>
</w:hyperlink>
```

**word/_rels/document.xml.rels**:
```xml
<Relationship Id="rId5"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
  Target="https://example.com"
  TargetMode="External"/>
```

## 단위 변환

Word OOXML은 다양한 단위 사용:

| 속성 | 단위 | 설명 |
|------|------|------|
| `w:sz` | half-points | 폰트 크기 (12pt = 24) |
| `w:w` | twips | 너비 (1인치 = 1440) |
| `w:space` | twips | 간격 |

**변환 공식**:
```python
def pt_to_half_points(pt):
    return int(pt * 2)

def inches_to_twips(inches):
    return int(inches * 1440)

def cm_to_twips(cm):
    return int(cm * 567)
```

## 스타일 수정

**word/styles.xml**:
```xml
<w:style w:type="paragraph" w:styleId="DanteCoffeeHeading">
  <w:name w:val="Dante Coffee Heading"/>
  <w:basedOn w:val="Heading1"/>
  <w:rPr>
    <w:rFonts w:ascii="Pretendard" w:hAnsi="Pretendard"/>
    <w:color w:val="1A365D"/>
    <w:sz w:val="48"/>
  </w:rPr>
  <w:pPr>
    <w:spacing w:after="240"/>
  </w:pPr>
</w:style>
```

## 검증 체크리스트

- [ ] 모든 `w:id` 속성이 고유함
- [ ] `w:commentRangeStart`와 `w:commentRangeEnd` 쌍이 일치
- [ ] `w:ins`, `w:del` 요소에 `w:author`, `w:date` 있음
- [ ] RSID가 `word/settings.xml`의 `w:rsids`에 등록됨
- [ ] 모든 `r:id` 참조가 유효함

## 에러 대응

| 에러 | 원인 | 해결 |
|------|------|------|
| "Cannot open file" | XML 구문 오류 | pretty-print 후 수정 |
| "Unmatched comment range" | 댓글 범위 불일치 | start/end ID 확인 |
| "Invalid RSID" | RSID 형식 오류 | 8자리 16진수 사용 |
| "Schema validation failed" | XSD 위반 | validate.py로 상세 확인 |

## 파일 저장 위치

```
{project}/
├── reports/documents/           # 최종 DOCX
├── assets/docx-resources/       # 리소스
│   └── unpacked/                # 언팩된 XML
└── tmp/docx-work/               # 작업 파일
```

## 의존성

```bash
pip install defusedxml lxml
```

## 참고

- [ECMA-376 (OOXML 표준)](https://www.ecma-international.org/publications-and-standards/standards/ecma-376/)
- [Office Open XML - WordprocessingML](http://officeopenxml.com/WPcontentOverview.php)
- 스크립트 위치: `plugins/common/skills/docx/scripts/`, `plugins/common/skills/docx/ooxml/scripts/`
