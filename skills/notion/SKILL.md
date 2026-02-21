---
name: notion_todo
description: 노션 할 일(To-do) 목록 조회·추가·완료. 노션 페이지/DB 연동.
---

# Notion 할 일 스킬

노션 할 일 요청이 오면 **exec**로 워크스페이스의 `secretary` 스크립트를 실행해 줘.

## 실행 위치

- 작업 디렉터리: `/home/node/.openclaw/workspace/secretary`
- Python: `python3 secretary_agent.py` (컨테이너에 notion-client, python-dotenv 설치 필요)
- 환경변수 NOTION_TOKEN, NOTION_PAGE_ID는 컨테이너에 설정되어 있어야 함.

## 명령 예시

| 사용자 요청 | 실행할 명령 |
|-------------|-------------|
| 노션 할 일 목록, 할 일 보여줘, 노션 조회 | `cd /home/node/.openclaw/workspace/secretary && python3 secretary_agent.py query_notion_todo` |
| 노션에 할 일 추가해줘 "밥 먹기" | `cd /home/node/.openclaw/workspace/secretary && python3 secretary_agent.py update_notion_todo --title "밥 먹기"` |
| 노션에 노트 추가 "제목" "내용" | `cd /home/node/.openclaw/workspace/secretary && python3 secretary_agent.py create_notion_note --title "제목" --content "내용"` |

## 응답 처리

- exec 출력(JSON)에서 `ok`, `items`, `error` 등을 읽어 사용자에게 짧게 요약해서 알려 줘.
- 실패 시 에러 메시지를 그대로 전달.
