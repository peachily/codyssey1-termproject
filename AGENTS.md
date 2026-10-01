## 프로젝트 및 작업 원칙

- 이 프로젝트는 4인 팀이 개발하는 웹 기반 AI 챗봇 과제입니다. 서비스 주제와 역할 담당자는 확정 전이며, 아래 기술 스택과 공통 개발 방식을 기준으로 구현합니다.
- 실제 구현은 담당자가 요청한 작업 범위에서 진행합니다. 불필요한 파일, 기능, 디렉터리는 임의로 추가하지 않습니다.
- 기존 담당자의 코드를 임의로 대규모 수정하거나 재구성하지 않습니다. 다른 역할의 코드 변경이 필요하면 담당자와 먼저 협의합니다.
- API Key, 비밀번호, 세션 비밀값 등 민감정보는 코드, 문서, 로그 또는 Git 기록에 작성하지 않습니다.
- 설정은 환경 변수를 사용하며, 로컬 값은 Git에서 제외되는 `.env`로 관리합니다.
- 새로운 백엔드 패키지를 추가하면 `requirements.txt`를 갱신합니다. 전역 환경의 불필요한 패키지는 포함하지 않습니다.
- 프론트엔드 의존성을 변경하면 `package.json`과 `package-lock.json`을 함께 갱신합니다.
- `GET /health`는 유지합니다.
- 명시적 요청 없이 commit, push, 브랜치 설정 또는 원격 저장소 설정 변경을 하지 않습니다.

## 고정 기술 스택

### Frontend

- React + Vite + JavaScript + HTML / CSS를 사용합니다.
- FastAPI와 REST API + JSON으로 통신하며, API 요청은 기본적으로 `fetch`를 사용합니다.
- Next.js, Axios, 별도 전역 상태관리 라이브러리는 사용하지 않습니다.
- 개발 환경에서는 Vite proxy로 `/api` 및 `/health` 요청을 FastAPI에 전달합니다.
- 인증이 필요한 API 요청에는 `credentials: "include"`를 지정합니다. 로그인 요청 등 세션 쿠키를 설정하는 요청에도 적용합니다.

### Backend

- Python + FastAPI + Uvicorn + Pydantic을 사용합니다.

### Database

- SQLite + SQLAlchemy 2.x ORM을 사용합니다.
- 기본 테이블은 다음과 같습니다.

| 테이블 | 필드 |
| --- | --- |
| `users` | `id`, `username`, `password_hash`, `created_at` |
| `chats` | `id`, `user_id`, `question`, `answer`, `created_at` |

- `chats.user_id`는 `users.id`를 참조합니다.
- 사용자 질문과 AI 응답을 사용자 식별 정보 및 생성 시각과 함께 누적 저장합니다.
- 대화 조회와 문맥 구성은 인증된 사용자 기준으로 수행합니다. 다른 사용자의 대화가 포함되지 않아야 합니다.

### Authentication

- `username` + `password`로 인증합니다.
- 비밀번호는 `pwdlib[argon2]`로 해시하여 저장합니다.
- Starlette `SessionMiddleware` 기반 세션 쿠키 인증을 사용하며 JWT는 사용하지 않습니다.
- 로그인하지 않은 사용자는 챗봇 기능을 사용할 수 없습니다.
- 프론트에서도 로그인 상태에 따라 화면 접근을 제어하되, 실제 API 권한 검증은 FastAPI에서도 반드시 수행합니다.

### AI 및 Context

- Google Gemini Developer API와 Python SDK `google-genai`를 사용합니다.
- 모델은 `gemini-3.5-flash-lite`이며 `GEMINI_MODEL`로 설정합니다. API Key는 `GEMINI_API_KEY`로 전달합니다.
- AI API 호출은 반드시 FastAPI 서버에서 수행합니다. React에서 Gemini API를 직접 호출하지 않습니다.
- AI 연동 코드는 `app/services/ai.py`에 격리합니다.
- 같은 사용자의 최근 5개 Q/A를 DB에서 조회하고, 최근 대화와 현재 질문을 함께 AI에 전달하여 문맥을 유지합니다.
- 별도 벡터 DB, RAG, 장기 메모리 시스템은 사용하지 않습니다.

## 입력 검증 및 AI 오류 처리

- 빈 입력과 공백만 있는 입력을 금지합니다.
- 질문의 최대 길이는 2000자입니다.
- 프론트 검증 여부와 관계없이 백엔드에서도 검증합니다.
- AI API 기본 Timeout은 30초이며 `AI_TIMEOUT`으로 설정합니다.
- Timeout은 HTTP 504, 기타 AI API 실패는 HTTP 502로 응답합니다.
- AI 실패나 Timeout이 발생해도 서버가 비정상 종료되지 않아야 하며, 사용자에게 이해 가능한 오류 메시지를 반환합니다.

## Logging

Python `logging`을 사용하며 다음 이벤트를 최소한 기록합니다.

- `request_received`: 요청 수신
- `ai_call_start`: AI 호출 시작
- `ai_call_success`: AI 응답 성공
- `ai_call_failure`: AI 실패 또는 Timeout
- `db_save_success`: DB 저장 성공
- `db_save_failure`: DB 저장 실패

가능하면 `user_id` 또는 `request_id`를 함께 기록합니다. 비밀번호, API Key, 세션 비밀값 등 민감정보는 로그에 기록하지 않습니다.

## API Convention

API 요청과 응답은 JSON을 기본으로 합니다.

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/chat`
- `GET /api/me/chats`
- `GET /health`

## Project Structure

아래는 구현 시 사용할 기준 구조입니다. 필요하지 않은 파일이나 디렉터리는 미리 만들지 않습니다.

```text
app/
├── main.py
├── config.py
├── database.py
├── models.py
├── schemas/
├── routers/
│   ├── auth.py
│   ├── chat.py
│   └── history.py
└── services/
    ├── auth.py
    └── ai.py

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── App.jsx
│   └── main.jsx
├── package.json
├── package-lock.json
└── vite.config.js
```

## Role Boundaries

담당자는 추후 배정하며, 다음 네 영역을 기준으로 역할을 나눕니다.

| 영역 | 책임 | 주요 담당 경로 |
| --- | --- | --- |
| 인증 · 사용자 관리 | 회원가입, 로그인, 로그아웃, 인증 상태 확인, 접근 제어 | `app/routers/auth.py`, `app/services/auth.py` |
| DB · 대화 기록 | SQLite / SQLAlchemy, 사용자·대화 데이터, 질문·AI 응답 저장, 사용자별 대화 기록 조회 | `app/database.py`, `app/models.py`, `app/routers/history.py` |
| AI 챗봇 | Gemini API, 질문·응답 처리, 최근 5개 Q/A 문맥 유지, Timeout 및 AI 오류 처리 | `app/services/ai.py`, `app/routers/chat.py` |
| 웹 UI · API 연결 | 회원가입·로그인 화면, 챗봇 화면, 대화 기록 화면, FastAPI API와 React 연결 | `frontend/` |

- 각 담당자는 자기 영역의 입력 검증, 예외 처리, 필요한 로그까지 함께 구현합니다.
- 공통 파일과 역할 간 API·데이터 인터페이스 변경은 관련 담당자와 협의합니다.

## Environment Variables

백엔드 환경 변수 기준은 다음과 같습니다. 빈 값은 실제 값이 아닌 설정 자리표시자입니다.

```dotenv
SECRET_KEY=
DATABASE_URL=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
AI_TIMEOUT=30
```

- `SECRET_KEY`: 세션 쿠키 인증에 사용하는 비밀값
- `DATABASE_URL`: 로컬 또는 배포 SQLite DB 연결 경로
- `GEMINI_API_KEY`: 서버에서 사용하는 Gemini API Key
- `GEMINI_MODEL`: Gemini 모델 이름
- `AI_TIMEOUT`: AI API Timeout 시간(초)
- 프론트 환경 변수가 필요하면 `VITE_` 접두사를 사용합니다. 예: `VITE_API_BASE_URL=`.
- `VITE_` 환경 변수에는 민감정보를 넣지 않습니다.
- 새 환경 변수를 도입하는 구현 작업에서는 `.env.example`에도 이름과 사용 목적을 추가합니다.
- 실제 비밀값은 `.env.example`, README, 코드 또는 Git 기록에 작성하지 않습니다.

## Deployment

- Railway를 사용하며 main 브랜치 반영 시 자동 배포하는 방식을 유지합니다.
- React는 Vite로 build하고, 배포 환경에서는 React `dist`를 FastAPI가 정적 파일로 제공합니다.
- 최종 서비스는 Railway 공개 URL 하나로 제공합니다.
- `GET /health`를 유지합니다.
- 배포용 SQLite DB는 Railway Volume `/data`에 저장합니다.
- `DATABASE_URL`로 로컬과 배포 DB 경로를 구분합니다.

## Git Commit Convention

커밋 메시지 형식: `<type>: <한글 설명>`

Types:

- feat: 새로운 기능 추가
- fix: 버그 수정
- docs: 문서 수정
- refactor: 기능 변경 없는 코드 개선
- test: 테스트 코드 추가 및 수정
- chore: 환경 설정, 패키지 등 기타 작업

규칙:

- type은 영어 소문자로 작성합니다.
- 설명은 한글로 작성합니다.
- 하나의 커밋에는 하나의 의미 있는 작업 단위를 담습니다.
- "수정", "업데이트", "작업"처럼 변경 내용을 알 수 없는 커밋 메시지는 사용하지 않습니다.

## Git Workflow

기본 브랜치 구조:

```text
main
└── develop
    └── <type>/<github-id>-<작업명>
```

규칙:

- main은 최종 배포용 브랜치입니다.
- develop은 기능 통합용 개발 브랜치입니다.
- 모든 작업 브랜치는 원격 최신 상태로 동기화한 develop에서 분기합니다.
- 실제 기능 개발은 feature 브랜치에서 진행합니다.
- 작업 브랜치 → Pull Request → develop 순서로 병합합니다.
- main과 develop에 기능 코드를 직접 push하지 않습니다.
- AI 코딩 도구도 사용자가 명시적으로 요청하지 않는 한 main/develop에 직접 commit 또는 push하지 않습니다.

브랜치 이름 형식: `<type>/<github-id>-<작업명>`

Types:

- feature: 새로운 기능 개발
- fix: 버그 수정
- chore: 환경 설정 및 기타 작업
- docs: 문서 작업

예시:

- `feature/peachily-auth`
- `fix/peachily-login`
- `chore/peachily-railway`
- `docs/peachily-readme`

브랜치 이름 규칙:

- 작업명은 짧은 영문 소문자로 작성합니다.
- 작업자의 GitHub ID를 사용합니다.
- GitHub ID가 명확하지 않으면 임의로 추측하지 말고 사용자에게 확인합니다.

### Pull Request Convention

PR 제목은 커밋 컨벤션과 동일하게 작성합니다.

형식: `<type>: <한글 설명>`

예시:

- `feat: 로그인 기능 구현`
- `fix: AI 응답 오류 처리 수정`
- `docs: API 명세 추가`
- `chore: Railway 배포 설정 추가`

PR 본문은 `.github/pull_request_template.md` 형식을 따릅니다.

PR 생성 규칙:

- feature, fix, chore, docs 브랜치에서 작업한 내용은 Pull Request를 통해 병합합니다.
- 기능 개발 브랜치는 기본적으로 develop을 base branch로 사용합니다.
- main에는 직접 기능 PR을 생성하지 않습니다.
- main 반영은 develop → main Pull Request를 통해 진행합니다.
- PR 생성 전 현재 브랜치, 변경사항, commit 및 push 상태를 확인합니다.
- PR 제목과 본문은 실제 변경 내용을 기준으로 작성합니다.
- GitHub CLI를 사용할 수 있는 경우 `gh pr create`를 사용합니다.
- 사용자가 명시적으로 요청하지 않은 PR merge는 수행하지 않습니다.

### Merge Policy

- 작업 브랜치 → PR → develop, develop → PR → main 흐름을 따릅니다.
- PR은 Merge commit 방식으로 병합합니다. Squash merge 또는 Rebase merge로 대체하지 않습니다.
- AI 코딩 도구는 사용자의 명시적 요청 없이 PR을 merge하지 않습니다.

## 과제 필수 요구사항

- 회원가입 / 로그인을 제공합니다.
- 로그인 상태에 따른 접근 제어를 구현하고 로그인 사용자만 챗봇을 사용할 수 있게 합니다.
- 웹에서 질문을 입력한 후 같은 화면에서 AI 응답을 확인할 수 있어야 합니다.
- AI API는 서버에서 호출합니다.
- 이전 대화를 이용해 문맥을 유지합니다.
- 사용자 질문 / AI 응답을 DB에 누적 저장합니다.
- 최소 저장 필드는 사용자 식별, 생성 시각, 질문, 응답입니다.
- 사용자 기준으로 대화 로그를 조회 / 추적할 수 있어야 합니다.
- 입력 검증을 최소 1개 이상 구현합니다. 본 프로젝트는 위의 빈 입력·공백 입력·최대 길이 검증을 모두 적용합니다.
- AI API Timeout을 적용하고, AI 실패 / Timeout 시 서버 비정상 종료를 방지합니다.
- 사용자에게 오류를 안내합니다.
- 서버 로그에 요청 수신, AI 호출, AI 응답 또는 실패, DB 저장 성공 또는 실패를 기록합니다.
- 민감정보는 환경 변수로 관리합니다.
- 팀원별 유의미한 커밋을 10회 이상 남깁니다.
- 기능 단위 브랜치 작업 기록과 PR 기반 Merge 기록을 남깁니다.

## 최종 README / 기술 문서 요구사항

최종 README에는 다음 항목을 포함합니다. 서비스 주제와 역할 확정 및 구현 진행에 맞춰 작성합니다.

- 문제 정의
- 타겟 사용자
- 핵심 시나리오
- 시스템 아키텍처
- 주요 컴포넌트 역할
- API 명세
- 요청 / 응답 예시
- DB 구조 또는 ERD
- 실행 방법
- 배포 방법
- 환경 변수 키 목록 및 설정 방법
- 팀 구성원 역할
- 개인별 작업 요약
- DB 확인 방법: 로그 조회 API / 관리자 화면 / SQL 또는 스크립트 / 증빙 중 1개 이상

## Final Submission Requirements

최종 제출 시 다음 조건을 확인합니다.

- 평가 시점에 외부 네트워크에서 접속 가능한 서비스 URL을 제공합니다.
- GitHub Repository 링크를 제출합니다.
- README / 기술 문서에 과제에서 요구한 모든 항목을 포함합니다.
- `.env.example`을 제공하고 `.env`가 Git에 포함되지 않도록 `.gitignore`를 적용합니다.
- README / 기술 문서에 환경 변수 키 목록과 설정 방법을 작성합니다.
- 팀 구성원 역할 및 개인별 작업 요약을 작성하며, 실제 Git 이력과 크게 모순되지 않아야 합니다.
- DB 저장 내용을 평가자가 확인할 수 있는 방법을 최소 1개 이상 제공합니다.