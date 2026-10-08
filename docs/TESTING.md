# 테스트 및 요구사항 검증

자동화 테스트의 실행 방법과 확인 범위를 설명하고 과제 원문 요구사항을 실제 구현·검증 근거에 연결합니다. 외부 AI·운영 배포·실제 브라우저 확인은 자동화 결과와 구분합니다.

## 기준과 실행 결과

2026-10-08 검증 기준입니다. 문서 브랜치의 기반은 `develop` `df73335`이며, [PR #59](https://github.com/peachily/codyssey1-termproject/pull/59)의 기능 브랜치 `000a4db`는 별도로 검증했습니다.

| 대상 | 실행·조건 | 결과 |
| --- | --- | --- |
| develop df73335 | 필수 테스트 설정을 격리해 전체 unittest, 프론트 빌드 존재 | 245개 실행, 실패 보고 16건 |
| develop df73335 | npm ci 및 npm run build | 성공 |
| PR #59 000a4db | 전체 unittest | 255개 통과 |
| PR #59 000a4db | npm test | 27개 통과 |
| PR #59 000a4db | npm run build | 성공 |
| DB 확인 도구 | 별도 사용자 2명·대화 3개 테스트 DB | 본인 기록 2개, 최신순·인덱스 확인 |

develop의 실패는 빌드가 존재할 때 테스트 전용 `/test-session`이 정적 파일 mount에 가려지는 사례이며 하위 사례를 포함한 보고 건수입니다. 수정과 회귀 테스트는 PR #59에 있습니다. **255개·27개 통과는 병합 전 기능 브랜치의 결과이며 현재 develop 전체 통과로 읽으면 안 됩니다.**

PR #59에서 로컬 빌드를 감지하지 않는 조건의 전체 백엔드 255개 통과와, 한국이 아닌 시간대에서 프론트 날짜 경계 검증도 앞선 작업에서 확인했습니다. 이번 문서 검증의 새 실행 결과와는 구분합니다.

## 실행 준비

- **저장소 루트**에서 [실행 및 환경 설정](DEPLOYMENT.md)에 따라 Python 가상환경과 의존성을 준비합니다.
- 테스트는 임시 DB·테스트 계정을 사용합니다. 운영 DB에 테스트를 실행하지 않습니다.
- 현재 develop의 `test_main.py`는 import 시 서버 설정을 읽으므로 SECRET_KEY가 필요합니다. PR #59에는 테스트 자체에서 설정을 격리하는 보완이 포함됩니다.
- 실제 Codyssey 요청은 mock 처리합니다. 유료 토큰을 사용하거나 외부 AI 품질을 평가하는 테스트가 아닙니다.

## 백엔드 테스트

필수 설정이 프로세스 환경에 있는 경우 **저장소 루트**, 가상환경 활성화 후:

```sh
python -m unittest discover -s tests -v
```

로컬 `.env`를 사용할 때 **저장소 루트**에서 다음 명령으로 먼저 로딩합니다. 테스트 종료 코드는 실패 시 1입니다.

```sh
python -c "from dotenv import load_dotenv; load_dotenv(); import unittest; result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not result.wasSuccessful())"
```

확인 방법: 마지막 `Ran ... tests`와 `OK` 또는 `FAILED`를 확인합니다. 로그에는 실패 테스트 이름이 나오며 비밀값을 출력해 진단하지 않습니다. PR #59의 기본 명령은 별도 `.env` 없이도 실행되도록 테스트 설정을 분리했습니다.

## 프론트 테스트와 빌드

**저장소 루트**에서:

```sh
npm ci --prefix frontend --include=dev
npm run build --prefix frontend
```

PR #59 반영 브랜치에서는 다음 자동화 테스트도 실행합니다.

```sh
npm test --prefix frontend
```

현재 기준 develop에는 `test` npm 스크립트가 없습니다. PR #59는 Vitest·Testing Library·jsdom을 개발 의존성으로 사용합니다. jsdom의 dialog 메서드는 보완 구현을 사용하므로 실제 브라우저의 top layer·포커스 제한·모바일 렌더링 확인을 대체하지 않습니다.

## 인증·DB·AI 검증 근거

| 검증 | 테스트 파일·내용 |
| --- | --- |
| 회원가입 | `test_auth_signup_service.py`, `test_auth_signup_routes.py`: 해시 저장·중복 409·rollback·세션 미생성 |
| 로그인·로그아웃·세션 | `test_auth_login_service.py`, `test_auth_login_routes.py`, `test_auth_current_user_routes.py`, `test_auth_session.py`: 인증·세션 교체·쿠키·로그아웃 |
| 인증되지 않은 API 요청 | `test_auth_dependencies.py`, `test_auth_access_control.py`: 누락·변조·만료 쿠키, 잘못된 ID 타입·존재하지 않는 사용자 |
| 사용자별 데이터 분리 | `test_auth_access_control.py`: 서로 다른 사용자 저장·문맥·처방 입력, 임의 user_id 무시 |
| 최근 5개 문맥 | `test_chat_service.py`, `test_ai_messages.py`, `test_chat_router.py`: 시간순 구성·5개 제한·사용자 필터 |
| 입력값 검증 | `test_auth_schemas.py`, `test_auth_routes.py`, `test_chat_router.py`: 타입·빈 값·공백·길이 경계·JSON 오류 |
| AI timeout | `test_ai_service.py`, `test_auth_access_control.py`: 외부 전송 timeout 모의, 504·미저장·복구 |
| AI 호출 실패 | 같은 파일: 연결·HTTP 오류·잘못된 응답, 502·실패 로그 |
| DB 저장 실패·rollback | `test_chat_service.py`, `test_auth_access_control.py`: 실제 commit 이벤트 실패, rollback·500·미저장 및 복구 |
| 서버 로그 | `test_main.py`, `test_auth_access_control.py`: request_id·user_id 추적·commit 후 성공 로그·비밀값 미노출 |
| 모델·DB 제약·검증 도구 | `test_models.py`, `test_database.py`, `test_check_db.py`: 외래키·UNIQUE·UTC·인덱스·읽기 전용 |
| 처방 | `test_ai_prescription.py`, `test_chat_router.py`: keyword 검증·색상 고정·형식 재시도·처방 미저장 |
| 전체 서버 연결 | `test_main.py`: 가입→로그인→질문→저장→처방→로그아웃 및 후속 차단 |

## PR #59 추가 검증

다음 파일은 기준 develop에 아직 없거나 추가 사례가 병합 전입니다.

| 검증 | 근거 |
| --- | --- |
| 본인 기록·빈 기록·정렬·UTC/KST 경계·재로그인 조회 | `tests/test_history_routes.py` |
| 빌드 유무 양쪽의 로그인·세션 교체·로그아웃 | `tests/test_auth_login_routes.py` 추가 사례 |
| AI 키 없는 env-file과 서버 시작 | `tests/test_ai_missing_key_startup.py` |
| 전송 실패가 실제 HTTP 오류까지 전달됨 | `tests/test_auth_access_control.py` 추가 사례 |
| 날짜별 분류·연월·윤년 경계·동시각 정렬 | `frontend/tests/historyDates.test.js` |
| 조회 credentials·잘못된 API 응답 차단 | `frontend/tests/api.test.js` |
| 기록 열람·처방 복귀·재질문·입력 보존·오류 안내 | `frontend/tests/conversation.test.jsx` |

API 키 누락 테스트는 새 Python 프로세스에 임시 `.env`를 만들고 `uvicorn.Config(..., env_file=...)`로 실제 설정 로딩을 실행합니다. AI 함수나 설정 함수를 대체하지 않고 **외부 HTTP 전송만 감시**합니다. 다른 필수 설정은 존재하고 CODYSSEY_API_KEY만 없을 때 서버 시작·가입·로그인·질문을 실행하여 502 `AI request failed`, 대화 미저장, 서버 유지, reason=missing_api_key 로그, 비밀값 미노출을 확인합니다.

AI timeout은 504, 외부 연결·HTTP·JSON·응답 구조 실패는 502입니다. 프론트는 상태코드별 한국어 안내를 표시하고 내부 detail 원문을 표시하지 않습니다. 정확한 안내는 [운영 오류 표](DEPLOYMENT.md#오류-처리와-점검)를 참조합니다.

## 실제 화면·배포 확인

정적 미리보기의 문구·아이콘 배치는 사용자와 검토했지만, 이는 인증·DB·AI가 연결된 화면의 종단 검증이 아닙니다. 다음 항목은 실제 브라우저·기기에서 최종 확인합니다.

- 가입→로그인→질문→답변→처방 흐름
- PR #59: 처방에서 돌아온 뒤 대화·입력 유지, 재질문 가능
- PR #59: 기록 아이콘→월 이동→날짜 선택→말풍선→닫기, 현재 대화 유지
- 모바일 노치·홈 인디케이터, 가로 잘림, 내부 스크롤과 배경 스크롤 제한
- 키보드 Tab, ESC 닫기, 포커스 복원
- 배포 환경의 실제 AI 연결 및 사용자 오류 안내
- Railway 재배포 후 계정·대화 기록 보존

## 과제 요구사항 대응

출처는 사용자가 제공한 「웹 기반 AI 챗봇 서비스 개발 프로젝트」 원문입니다. 별도의 점수 배점표는 제공되지 않았습니다. 아래 항목명과 요구 문장은 원문의 표현을 유지합니다.

### 2. 최종 결과물

| 원문 항목 | 대응 문서·확인 |
| --- | --- |
| 웹 기반 AI 챗봇 서비스 (FastAPI) | [README](../README.md), [ARCHITECTURE](ARCHITECTURE.md) |
| 접근성: 평가 시점에 외부 네트워크에서 접속 가능한 서비스 URL이 제공되어야 한다. | [DEPLOYMENT의 공개 URL 및 확인 순서](DEPLOYMENT.md#railway-배포-구조) |
| GitHub Repository 링크 | https://github.com/peachily/codyssey1-termproject |
| 프로젝트 개요(문제 정의, 타겟 사용자, 핵심 시나리오) | [README](../README.md)의 프로젝트 소개·서비스 이용 방법 |
| 시스템 구조(간단 아키텍처, 주요 컴포넌트 역할) | [ARCHITECTURE](ARCHITECTURE.md) |
| API 명세(요청/응답 예시 포함) | [API](API.md) |
| DB 구조(ERD 또는 테이블/필드 설명) | [DATABASE](DATABASE.md) |
| 배포/실행 방법(환경 변수 설정 포함) | [DEPLOYMENT](DEPLOYMENT.md) |
| 팀 구성원 역할 및 개인별 작업 요약 | [TEAM](TEAM.md) |
| 민감정보 관리(.env 예시 제공, .gitignore 적용 등) | [DEPLOYMENT](DEPLOYMENT.md#민감정보-관리), `.env.example`, `.gitignore` |
| DB 확인 가이드 (가능 범위 내, 아래 중 1개 이상) | [DATABASE](DATABASE.md): 확인용 SQL과 읽기 전용 스크립트 실행 방법 |

제공된 원문은 README와 기술 문서에 포함할 내용을 요구하지만 `docs/`의 고정 파일명이나 `AGENTS.md` 제출을 요구하지 않습니다.

### 4. 기능 요구 사항

| 원문 항목·요구 문장 | 구현·검증 근거 |
| --- | --- |
| 웹 UI (질문 입력 인터페이스) — 사용자가 질문을 입력할 수 있는 웹 페이지가 존재해야 한다. | `ChatInput.jsx`, `InteriorScene.jsx` |
| 질문 입력 후 응답이 같은 화면에서 확인 가능해야 한다. (형태 자유: 단일 페이지/페이지 전환 등) | `useChat.js`, `ChatBubble.jsx`, [ARCHITECTURE](ARCHITECTURE.md#질문--ai--db--응답) |
| 사용자 인증 및 접근 제어 — 회원가입 및 로그인 기능이 정상 동작해야 한다. | 인증 라우터·서비스, 위 인증 테스트 |
| 인증 상태(로그인/비로그인)에 따라 접근 가능한 기능이 구분되어야 한다. | `App.jsx`, `useAuth.js`, `get_current_user()` |
| “챗봇 질문/응답 기능”은 로그인한 사용자만 사용할 수 있어야 한다. | `POST /api/chat` 인증 의존성, 접근 제어 테스트 |
| AI 챗봇 처리 (FastAPI 백엔드) — 서버가 사용자 질문을 수신하고, AI API를 호출하여 응답을 생성해야 한다. | `app/routers/chat.py`, `app/services/ai.py` |
| AI API 호출은 서버에서 수행되어야 하며(키 노출 방지), 결과만 화면에 반환되어야 한다. | AI settings·requests 호출은 서버에만 존재 |
| 문맥 유지가 가능하도록, 최소한의 컨텍스트 구성 전략을 적용해야 한다. | `get_recent_chats()`, `build_chat_messages()`, 문맥 테스트 |
| 대화 로그 저장 및 조회/추적 — 사용자 질문과 AI 응답이 DB에 누적 저장되어야 한다. | `save_chat()`, Chat 모델·저장 테스트 |
| 최소 추적 필드: 사용자 식별, 생성 시각, 질문, 응답 | [DATABASE 테이블](DATABASE.md#테이블과-제약조건) |
| “사용자 기준 로그 조회/추적”이 가능해야 한다. | [DATABASE의 사용자별 SQL·스크립트](DATABASE.md#사용자별-기록-조회-sql); 조회 API는 PR #59 |
| 운영 및 유지보수 (로그/예외/입력 검증) — 요청 수신 / AI 호출 / AI 응답 수신(또는 실패) / DB 저장 성공·실패 | [ARCHITECTURE 로그 위치](ARCHITECTURE.md#검증오류로그), 로그 테스트 |
| AI API 실패/타임아웃 상황에서 서비스가 비정상 종료되지 않아야 한다. | AI 오류 변환·후속 요청 복구 테스트 |
| 사용자에게 오류가 발생했음을 알리는 응답(메시지/상태코드/안내)이 제공되어야 한다. | [API](API.md), [DEPLOYMENT 오류 표](DEPLOYMENT.md#오류-처리와-점검) |
| 사용자 입력 검증 로직이 최소 1개 이상 존재해야 한다. | username·password·message 서버 검증 |
| 배포 및 접근성 — 배포된 서비스는 평가 시점 기준 외부 네트워크에서 접속 가능해야 한다. | 공개 URL, 평가 시점 재확인 필요 |
| 배포/실행 방법과 환경 변수 설정 방법이 문서에 포함되어야 한다. | [DEPLOYMENT](DEPLOYMENT.md) |
| 협업 및 형상관리 — 브랜치 전략이 적용되어야 한다. (예: main/develop 분리 또는 이에 준하는 운영) | [DEVELOPMENT](DEVELOPMENT.md#git-작업-흐름), 원격 브랜치 |
| 기능 단위 작업 브랜치(또는 이에 준하는 작업 흐름) 흔적이 있어야 한다. | [TEAM PR 이력](TEAM.md) |
| PR 기반 Merge 기록이 존재해야 한다. | develop의 merge commit 및 [TEAM](TEAM.md) |
| 팀원별 유의미한 커밋이 10회 이상 존재해야 한다. | [TEAM의 커밋 집계·확인 명령](TEAM.md#커밋-집계) |
| 문서에 팀 역할/개인별 작업 요약이 포함되어야 하며, Git 이력과 크게 모순되지 않아야 한다. | [TEAM](TEAM.md) |

### 5. 개발 환경 및 6. 제약 사항

| 원문 항목·요구 문장 | 근거 |
| --- | --- |
| Python & FastAPI로 구현한다. | `app/`, `requirements.txt` |
| SQLite 사용을 권장하며, 평가자가 확인 가능한 형태로 연결/조회가 가능해야 한다 | [DATABASE](DATABASE.md) |
| 민감정보 및 설정 관리 — API 키, DB 비밀번호 등 민감정보를 코드/문서에 직접 작성하지 않는다. | 환경 변수와 비밀값 없는 예시 |
| 모든 민감정보는 환경 변수(.env 등)로 관리한다. | `app/config.py`, [DEPLOYMENT](DEPLOYMENT.md) |
| .env 파일은 저장소에 업로드되지 않도록 .gitignore를 적용한다. | `.gitignore` |
| README에 환경 변수 키 목록(이름 수준)과 설정 방법을 포함한다. | 이번 README 개편 요청에 따라 본문에는 설정을 넣지 않고 DEPLOYMENT 링크로 연결함. 원문을 엄격히 적용하면 README에 키 목록을 추가해야 하므로 최종 확인 필요 |
| 운영 안정성 — AI API 호출은 타임아웃을 설정해야 하며(값은 팀이 선택), 실패 시 사용자에게 오류 안내를 반환해야 한다. | AI_TIMEOUT, 예외·프론트 오류 안내 테스트 |
| 요청 수신, AI 호출/응답, DB 저장 성공·실패가 로그로 남아야 한다. | 로그 이벤트·추적 ID 검증 |
| 협업 규칙 — PR 기반으로 머지하고, 브랜치/PR 기록이 저장소에 남아야 한다. | [TEAM](TEAM.md), [DEVELOPMENT](DEVELOPMENT.md) |
| 팀원별 유의미한 커밋 최소 10회 이상 기록되어야 한다. | 팀 커밋 집계와 실제 변경 내용 검토 |
| 기술 문서에 팀 구성원 역할 및 개인별 작업 요약을 반드시 포함해야 한다. | [TEAM](TEAM.md) |
