# 과제 요구사항 검증

필수 기능과 제출 자료의 구현 근거 및 확인 방법을 정리합니다.

## 기능 요구 사항

| 요구사항 | 구현 근거 | 확인 방법 |
| --- | --- | --- |
| 웹 UI (질문 입력 인터페이스) | `InteriorScene.jsx`, `useChat.js` | 로그인 후 질문 입력 → 같은 화면에서 답변 확인 |
| 사용자 인증 및 접근 제어 | 인증 API, `get_current_user()` | 가입·로그인·로그아웃, 비로그인 보호 API 요청 시 401 확인 |
| AI 챗봇 처리 (FastAPI 백엔드) | `app/routers/chat.py`, `app/services/ai.py` | 서버 AI 호출, 본인 최근 5개 Q/A의 시간순 전달 확인 |
| 대화 로그 저장 및 조회/추적 | Chat 모델, `GET /api/me/chats` | 사용자 식별·생성 시각·질문·응답 저장, 사용자별 조회 확인 |
| 운영 및 유지보수 (로그/예외/입력 검증) | 입력 스키마·예외 처리·서버 로그 | 아래 실패 상황별 검증 확인 |
| 배포 및 접근성 | [공개 서비스](https://codyssey1-termproject-production.up.railway.app) | 외부 네트워크 접속 → 로그인·질문·답변 확인 |
| 협업 및 형상관리 | [작업 PR](TEAM.md#주요-pr), [Git 규칙](DEVELOPMENT.md#git-작업-흐름) | 기능 브랜치·PR Merge 이력·팀원별 유의미한 커밋 10회 이상 확인 |

## 실패 상황 및 데이터 검증

테스트 파일은 `tests/`에 있습니다. AI 오류는 외부 전송을 mock으로 재현합니다.

| 검증 항목 | 확인 내용 | 근거 |
| --- | --- | --- |
| 인증·사용자 분리 | 미인증 401, 다른 사용자의 기록·문맥 제외 | `test_auth_access_control.py`, `test_history_routes.py` |
| 입력 검증 | 누락·타입 오류·빈 값·공백·길이 위반 시 400 | `test_auth_schemas.py`, `test_chat_router.py` |
| 문맥 유지 | 본인 최근 최대 5개 Q/A를 시간순 구성 | `test_ai_messages.py`, `test_chat_service.py` |
| AI 키 누락·호출 실패 | 502 안내, 대화 미저장, 서버 유지 | `test_ai_missing_key_startup.py`, `test_ai_service.py` |
| AI timeout | 504 안내, 대화 미저장, 후속 요청 가능 | `test_auth_access_control.py` |
| DB 저장 실패 | 500 안내, rollback, 성공으로 응답하지 않음 | `test_chat_service.py`, `test_auth_access_control.py` |
| 서버 로그 | 요청 수신·AI 호출/응답/실패·DB 저장 성공/실패 기록 | `test_main.py`, `test_auth_access_control.py` |
| DB 확인 | 사용자별 기록·건수·정렬 조회 | [읽기 전용 SQL·스크립트](DATABASE.md#사용자별-기록-조회-sql) |
| 사용자 오류 안내 | 내부 오류 대신 한국어 안내 표시 | `frontend/tests/conversation.test.jsx` |

## 검증 실행

[환경 준비](DEPLOYMENT.md) 후 **저장소 루트**에서 실행합니다.

```sh
python -m unittest discover -s tests -v
npm ci --prefix frontend --include=dev
npm test --prefix frontend
npm run build --prefix frontend
```

- 백엔드: 임시 DB로 인증·AI·저장·조회 검증.
- 프론트: jsdom으로 화면 상태·오류 안내 검증.
- 공개 서비스 접근과 실제 AI 응답은 배포 환경에서 확인.

## 제출 자료

| 요구사항 | 문서·파일 |
| --- | --- |
| GitHub Repository 링크 | [저장소](https://github.com/peachily/codyssey1-termproject) |
| 프로젝트 개요(문제 정의, 타겟 사용자, 핵심 시나리오) | [README](../README.md) |
| 시스템 구조(간단 아키텍처, 주요 컴포넌트 역할) | [ARCHITECTURE](ARCHITECTURE.md) |
| API 명세(요청/응답 예시 포함) | [API](API.md) |
| DB 구조(ERD 또는 테이블/필드 설명) | [DATABASE](DATABASE.md) |
| 배포/실행 방법(환경 변수 설정 포함) | [DEPLOYMENT](DEPLOYMENT.md) |
| 팀 구성원 역할 및 개인별 작업 요약 | [TEAM](TEAM.md) |
| 민감정보 관리(.env 예시 제공, .gitignore 적용 등) | [.env.example](../.env.example), [.gitignore](../.gitignore), [설정 관리](DEPLOYMENT.md#민감정보-관리) |
| DB 확인 가이드 (가능 범위 내, 아래 중 1개 이상) | [사용자별 조회 SQL·실행 방법](DATABASE.md#사용자별-기록-조회-sql) |
| README에 환경 변수 키 목록(이름 수준)과 설정 방법을 포함한다. | [README 환경 설정](../README.md#환경-변수-및-설정-방법) |
