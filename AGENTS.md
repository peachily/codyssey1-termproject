# 개발 규칙

## 프로젝트 및 작업 원칙

- 4인 팀의 웹 AI 챗봇 프로젝트입니다. 아래 기술 스택과 API 계약을 따릅니다.
- 실제 구현은 담당자가 요청한 작업 범위에서 진행합니다. 불필요한 파일, 기능, 디렉터리는 임의로 추가하지 않습니다.
- 기존 담당자의 코드를 임의로 대규모 수정하거나 재구성하지 않습니다. 다른 역할의 코드 변경이 필요하면 담당자와 먼저 협의합니다.
- API Key, 비밀번호, 세션 비밀값 등 민감정보는 코드, 문서, 로그 또는 Git 기록에 작성하지 않습니다.
- 설정은 환경 변수를 사용하며, 로컬 값은 Git에서 제외되는 `.env`로 관리합니다.
- 새로운 백엔드 패키지를 추가하면 `requirements.txt`를 갱신합니다. 전역 환경의 불필요한 패키지는 포함하지 않습니다.
- 프론트엔드 의존성을 변경하면 `package.json`과 `package-lock.json`을 함께 갱신합니다.
- `GET /health`는 유지합니다.
- 명시적 요청 없이 commit, push, 브랜치 설정 또는 원격 저장소 설정 변경을 하지 않습니다.

## 서비스 및 마법약 처방 계약

- **KKAMURUK(까무룩)**은 잠들기 어려운 사용자가 AI와 짧게 대화하고, 대화 내용을 바탕으로 마법약 처방과 짧은 위로 메시지를 받는 웹 서비스입니다.
- 기본 흐름: 회원가입/로그인 → AI와 대화 → 상태 분류 → 마법약 처방 → 짧은 위로 메시지 확인.
- 일반 대화 Q/A는 기존 사용자별 저장·조회 및 최근 최대 5개 Q/A 문맥 계약을 유지합니다. `GET /api/me/chats`와 DB 함수는 유지하며, 별도의 과거 대화 기록 화면은 현재 필수 기능이 아닙니다.
- AI는 대화 내용을 바탕으로 아래 `keyword` 중 하나와 짧은 위로 `message`를 생성합니다. 서버는 `keyword`를 검증하고 `color`를 고정 매핑하며, AI가 임의로 생성한 색상을 사용하지 않습니다.

| keyword | color |
| --- | --- |
| ANXIETY | BLUE |
| SADNESS | PURPLE |
| LONELINESS | PINK |
| STRESS | GREEN |
| EXHAUSTION | YELLOW |

- 최종 처방 데이터는 `keyword`, `color`, `message`입니다. `keyword`와 `color`는 내부 분류값이며 사용자 화면에 문자열로 표시할 의무는 없습니다. 프론트엔드는 `color`를 마법약의 시각적 표현에 사용할 수 있습니다.
- 일반 대화 Q/A 저장과 최종 처방은 구분합니다. 최종 처방은 DB에 저장하지 않으며 이전 처방 조회 기능을 제공하지 않습니다.
- 처방은 `POST /api/prescription`으로 요청합니다. 요청·응답 형식은 아래 API Convention을 따릅니다.

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

- Codyssey 제공 OpenAI 호환 Chat Completions API를 Python `requests`로 호출합니다.
- 요청 URL은 `AI_API_URL`로 설정하며 기본값은 `https://copa.codyssey.kr/v1/chat/completions`입니다. 모델은 `AI_MODEL`로 설정하며 기본값은 `gpt-5.4`입니다.
- `CODYSSEY_API_KEY`에서 virtual key를 읽어 `Authorization: Bearer <virtual-key>` 헤더로 전달합니다. 실제 키는 로컬 `.env` 또는 Railway Variables에만 설정하며 코드·문서·로그에 남기지 않습니다.
- POST 요청의 JSON에는 `model`과 `messages`를 전달하고, 응답의 `choices[0].message.content`를 AI 답변으로 사용합니다.
- 최근 Q/A는 `user`·`assistant` 메시지로 순서대로 구성하고 마지막에 현재 질문을 `user` 메시지로 추가합니다.
- 요청에는 `AI_TIMEOUT`을 timeout으로 적용하고 HTTP 오류도 AI 호출 실패로 처리합니다.
- AI API 호출은 반드시 FastAPI 서버에서 수행합니다. React에서 Codyssey API를 직접 호출하지 않습니다.
- AI 연동 코드는 `app/services/ai.py`에 격리합니다.
- 같은 사용자의 최근 최대 5개 Q/A를 DB에서 조회하고 시간순으로 정렬하여 현재 질문과 함께 AI에 전달합니다. 다른 사용자의 대화는 포함하지 않습니다.
- 별도 벡터 DB, RAG, 장기 메모리 시스템은 사용하지 않습니다.

## 입력 검증 및 오류 처리

### username / password

- 회원가입·로그인 모두 `username`과 `password`를 필수 문자열로 받습니다. 누락, null, 문자열이 아닌 값, 빈 문자열과 공백만 있는 값은 HTTP 400으로 처리합니다.
- `username`은 앞뒤 공백을 제거한 값으로 가입·중복 확인·로그인을 처리합니다.
- 공백 제거 후 `username`은 3~30자이며, 영문 소문자·숫자·underscore(`_`)만 허용합니다. 정규식은 `^[a-z0-9_]{3,30}$`입니다.
- `password`는 공백만 있는지 검증하되, 유효한 비밀번호의 앞뒤 공백을 제거하거나 값을 변형하지 않습니다. 해시와 인증에는 입력 원문을 사용합니다.
- `password`는 trim하지 않은 문자열 기준 8~128자이며, 별도의 영문·숫자·특수문자 조합 규칙은 두지 않습니다. 평문 password는 저장하거나 로그에 기록하지 않습니다.
- 가입 시 username 중복은 HTTP 409입니다. 비밀번호는 `pwdlib[argon2]`로 해시하여 저장합니다.
- username/password의 추가 길이·문자 제한은 팀 합의 없이 임의로 도입하지 않습니다.

### chat message

- `message`는 필수 문자열입니다. 누락, null, 문자열이 아닌 값은 HTTP 400으로 처리합니다.
- trim 후 빈 문자열이거나 2000자를 넘으면 HTTP 400으로 처리합니다. 검증된 메시지를 AI에 전달하고 `question`으로 저장합니다.
- 프론트 검증 여부와 관계없이 백엔드에서도 검증합니다.

### AI 오류

- 기본 Timeout은 30초이며 `AI_TIMEOUT`으로 설정합니다.
- Timeout은 HTTP 504, 기타 AI API 실패는 HTTP 502로 응답하고 `ai_call_failure`를 기록합니다.
- AI 호출 자체가 실패하거나 Timeout이 발생하면 chat을 DB에 저장하지 않습니다.
- 오류가 발생해도 서버가 비정상 종료되지 않아야 합니다. 오류 응답은 `detail` 형식을 사용하고, 사용자 안내 문구는 React에서 표시할 수 있습니다.

### DB 저장 실패

- 회원가입 및 대화 저장에 실패하면 해당 트랜잭션을 rollback하고 `db_save_failure`를 기록한 뒤 HTTP 500을 반환합니다. username 중복은 rollback 후 계약에 따라 HTTP 409로 처리합니다.
- `user_id` 또는 `request_id` 등 가능한 추적 정보를 로그에 포함하되, 비밀번호·API Key·세션 비밀값을 기록하거나 내부 DB 오류를 응답에 노출하지 않습니다.
- 저장이 성공적으로 commit된 뒤에만 `db_save_success`를 기록하고 성공 응답을 반환합니다. AI 응답을 받았더라도 대화 저장에 실패하면 성공으로 응답하지 않습니다.
- `POST /api/chat`에서 AI 응답을 정상적으로 받았더라도 DB 저장에 실패하면 트랜잭션을 rollback하고 `db_save_failure`를 기록한 뒤 HTTP 500과 `{"detail": "Failed to save chat"}`을 반환합니다.

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

개발 중 API 계약은 이 문서를 기준으로 합니다. 계약 변경은 관련 담당자와 합의합니다. 문서 작성 위치와 기준은 아래 「문서 역할 및 작성 규칙」을 따릅니다.

### 공통 규칙 및 라우터 등록

- 모든 API 경로는 `/api` 접두사를 사용합니다. 단, `/health`는 예외입니다.
- 요청과 응답은 JSON을 기본으로 합니다.
- FastAPI API router는 `app/main.py`에서 React 정적 파일 mount 및 SPA fallback보다 먼저 등록합니다.
- `/api/*` 및 `/health` 요청이 React SPA fallback에 의해 처리되지 않도록 유지합니다.
- 인증은 Starlette `SessionMiddleware` 기반 세션 쿠키를 사용합니다.
- 로그인 성공 시 기존 세션을 비우고 `request.session["user_id"]`에 사용자 id를 저장합니다. 로그아웃 시 `request.session.clear()`로 세션을 제거합니다.
- 인증이 필요한 요청은 세션의 `user_id`로 DB 사용자를 조회합니다. 세션이 없거나 해당 사용자가 없으면 HTTP 401을 반환합니다.
- 세션에는 비밀번호·비밀번호 해시·API Key를 저장하지 않습니다.
- 프론트엔드 `fetch` 요청에는 `credentials: "include"`를 사용합니다.
- 클라이언트가 `user_id`를 임의로 전달하여 인증 또는 데이터 조회에 사용하지 않습니다.
- 날짜/시간은 UTC로 생성·저장하고, API에서는 UTC를 나타내는 `Z`를 붙인 ISO 8601 문자열로 반환합니다. 서버 로컬 시간대에 의존하지 않습니다. 예: `2026-10-02T08:00:00Z`.
- `password` 및 `password_hash`는 API 응답에 절대 포함하지 않습니다.

### POST /api/auth/signup

#### 설명

username과 password로 가입합니다. username은 중복될 수 없으며 회원가입만으로 로그인 세션을 생성하지 않습니다.

#### Request

```json
{
  "username": "peachily",
  "password": "password123"
}
```

#### Success Response

201 Created

```json
{
  "id": 1,
  "username": "peachily"
}
```

#### Error Response

- 400: 입력값 검증 실패
- 409: username 중복
- 500: DB 저장 실패

### POST /api/auth/login

#### 설명

사용자 인증 및 로그인 세션 생성. 잘못된 사용자명과 비밀번호는 동일한 인증 실패로 응답합니다.

#### Request

```json
{
  "username": "peachily",
  "password": "password123"
}
```

#### Success Response

200 OK

```json
{
  "id": 1,
  "username": "peachily"
}
```

#### Error Response

- 400: 입력값 검증 실패
- 401: 인증 실패

### POST /api/auth/logout

#### 설명

현재 로그인 세션 제거.

#### Request

Request body 없음.

#### Success Response

200 OK

```json
{
  "message": "logged out"
}
```

#### Error Response

별도의 도메인 오류 응답은 정의하지 않습니다.

### GET /api/auth/me

#### 설명

세션으로 식별한 현재 로그인 사용자 조회.

#### Request

Request body 없음.

#### Success Response

200 OK

```json
{
  "id": 1,
  "username": "peachily"
}
```

#### Error Response

- 401: 로그인되지 않은 사용자

### POST /api/chat

#### 설명

로그인 사용자의 질문 처리. 공백 제거 후 비어 있지 않은 최대 2000자 메시지를 받으며, 자신의 최근 최대 5개 Q/A를 문맥으로 사용합니다. AI 응답 성공 후 대화를 저장합니다.

#### Request

```json
{
  "message": "안녕하세요."
}
```

#### Success Response

200 OK

```json
{
  "id": 1,
  "question": "안녕하세요.",
  "answer": "안녕하세요! 무엇을 도와드릴까요?",
  "created_at": "2026-10-02T08:00:00Z"
}
```

#### Error Response

- 400: message 누락·타입 오류·빈 입력 또는 길이 제한 초과
- 401: 로그인되지 않은 사용자
- 502: AI 호출 실패
- 504: AI timeout
- 500: DB 저장 실패

### GET /api/me/chats

#### 설명

로그인 사용자 자신의 대화를 최신순으로 조회합니다. pagination은 제공하지 않습니다.

#### Request

Request body 없음.

#### Success Response

200 OK

```json
{
  "chats": [
    {
      "id": 2,
      "question": "두 번째 질문",
      "answer": "두 번째 답변",
      "created_at": "2026-10-02T08:10:00Z"
    },
    {
      "id": 1,
      "question": "첫 번째 질문",
      "answer": "첫 번째 답변",
      "created_at": "2026-10-02T08:00:00Z"
    }
  ]
}
```

#### Error Response

- 401: 로그인되지 않은 사용자

### POST /api/prescription

#### 설명

로그인 사용자의 최근 최대 5개 Q/A를 바탕으로 마법약 처방을 생성합니다. 서버가 `keyword`를 검증하고 `color`를 고정 매핑합니다. 처방은 DB에 저장하지 않습니다.

#### Request

Request body 없음.

#### Success Response

200 OK

```json
{
  "keyword": "ANXIETY",
  "color": "BLUE",
  "message": "오늘 다 해결하지 않아도 괜찮아요. 지금은 편히 쉬어가요."
}
```

#### Error Response

- 400: 처방에 사용할 대화 기록 없음
- 401: 로그인되지 않은 사용자
- 502: AI 호출 실패 또는 처방 형식 오류
- 504: AI timeout

### GET /health

#### 설명

인증 없이 로컬 및 Railway 서버 상태를 확인합니다.

#### Request

Request body 없음.

#### Success Response

200 OK

```json
{
  "status": "ok"
}
```

#### Error Response

별도의 도메인 오류 응답은 정의하지 않습니다.

### 오류 응답 규칙

FastAPI의 기본 `HTTPException` 응답 형태를 사용합니다.

```json
{
  "detail": "Invalid username or password"
}
```

- 별도의 공통 error wrapper나 자체 오류 응답 구조를 만들지 않습니다.
- 입력 검증 실패도 위 API 계약에 명시된 HTTP 400 및 `detail` 형태로 처리합니다. 자동 검증 응답이 계약과 달라지지 않도록 구현합니다.
- 사용자에게 실제로 보여주는 친절한 오류 문구는 React UI 담당자가 처리할 수 있지만, HTTP status code와 API 계약은 위 규칙을 따릅니다.

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

| 영역 | 책임 | 주요 담당 경로 |
| --- | --- | --- |
| 인증 · 사용자 관리 | `/api/auth/*`, 인증·세션, 접근 제어 | `app/routers/auth.py`, `app/services/auth.py` |
| DB · 대화 기록 | DB 연결, User/Chat 모델, 대화 저장·조회 | `app/database.py`, `app/models.py`, `app/routers/history.py` |
| AI 챗봇 | Codyssey API 호출, `/api/chat` AI 처리, 최근 5개 문맥, Timeout·오류 처리 | `app/services/ai.py`, `app/routers/chat.py` |
| 웹 UI · API 연결 | 회원가입·로그인 화면, 챗봇·마법약 처방 결과 화면, FastAPI API와 React 연결 | `frontend/` |

- 각 담당자는 자기 영역의 입력 검증, 예외 처리, 필요한 로그까지 함께 구현합니다.
- Frontend 담당자는 위 API 계약을 그대로 사용하며 backend API의 요청/응답 형식을 임의로 변경하지 않습니다.
- 공통 파일과 역할 간 인터페이스는 관련 담당자와 조율하고, 다른 담당자의 코드를 임의로 크게 수정하지 않습니다.

## DB 및 담당 영역 간 연동

- 현재 `app/main.py`는 `/health`와 React 정적 파일 제공을 담당합니다. DB 초기화, 인증·대화 라우터, AI 호출 및 서비스 UI 연결은 각 담당자의 구현 범위입니다.
- `app.database.get_db`를 FastAPI `Depends`로 사용해 요청별 Session을 전달합니다. 직접 세션이 필요한 서버 코드는 `SessionLocal`을 사용합니다.
- 서버 담당은 lifespan 시작 시 `app.models`를 import한 뒤 `initialize_database(engine)`을 호출하고 종료 시 `engine.dispose()`를 호출합니다. `create_all`은 기존 스키마를 변경하지 않으므로 스키마 변경 시 백업·마이그레이션 절차를 별도로 마련합니다.
- `User.password_hash`에는 인증 담당이 생성한 Argon2 해시만 넣습니다. DB UNIQUE 오류는 rollback 후 HTTP 409로 처리합니다.
- 인증 의존성은 재사용하며 세션의 `user_id`가 문자열 또는 bool이면 인증 실패로 처리하도록 검증하는 것을 권장합니다. SECRET_KEY 검증과 HTTPS 쿠키 정책은 인증 담당이 연결합니다.

### 대화 저장·조회 인터페이스

| 함수 | 동작 |
| --- | --- |
| `save_chat(db, user_id, question, answer)` | flush → commit → 성공 로그 → Chat 반환 |
| `list_user_chats(db, user_id)` | 본인 전체 대화 최신순 조회 |
| `get_recent_chats(db, user_id)` | 본인 최근 최대 5개 Q/A를 오래된 순으로 반환 |

- 세 함수의 `user_id`는 인증된 `user.id`를 사용합니다. 조회 정렬은 `created_at DESC, id DESC`이며 최근 문맥만 역순으로 반환합니다.
- 기록이 없으면 `GET /api/me/chats`의 `chats`는 빈 배열입니다. UTC 응답 시각에는 소수 초가 포함될 수 있습니다. 401의 구체적인 문구는 기존 API 계약 이상으로 확정하지 않습니다.
- AI 담당은 최근 Q/A를 일반 메시지 데이터로 변환한 후, 미저장 변경이 없는 전용 요청 세션에서 `db.rollback()`으로 읽기 트랜잭션을 종료하고 AI를 호출합니다. 무관한 미저장 변경을 같은 세션에 넣지 않습니다.
- AI 호출 중 쓰기 트랜잭션을 열거나 빈 Chat을 미리 삽입하지 않습니다. 성공한 일반 대화 답변만 `save_chat`에 전달하며 실패·timeout 시 호출하지 않습니다.
- `save_chat`은 전달된 세션 전체를 commit합니다. SQLAlchemy 저장 오류 시 rollback·실패 로그 후 `ChatSaveError`를 발생시키므로 서버 담당은 기존 계약의 HTTP 500 및 `Failed to save chat` 응답으로 변환합니다.
- `SessionLocal`은 `expire_on_commit=False`입니다. 로그에는 추적 ID만 사용하고 질문·응답·내부 DB 오류 원문을 추가하지 않습니다.
- SQLite 연결의 foreign_keys와 5초 busy_timeout, 사용자별 복합 인덱스를 유지합니다. 사용자 삭제에 cascade를 임의로 추가하지 않습니다.
- UTCDateTime은 시간대 없는 입력을 거부합니다. 직접 SQL로 삽입할 때에는 ORM 기본값이 적용되지 않으므로 생성 시각을 명시합니다.
- 현재 조회는 관계의 지연 로딩 없이 명시적 SELECT를 사용합니다. 필요하지 않은 relationship, 중복 인덱스, covering index, WAL 또는 별도 DB 서버를 임의로 추가하지 않습니다.

### 처방 연동 경계

- AI 담당은 공통 처방 계약의 keyword와 짧은 message를 생성하고, 서버는 keyword 검증과 고정 color 매핑을 수행합니다.
- 프론트엔드는 최종 처방을 표시합니다. 처방을 `Chat.answer`에 우회 저장하거나 users·chats에 처방 컬럼을 추가하지 않습니다.
- 서버는 AI 출력에서 `keyword`와 `message`만 사용합니다. 허용되지 않은 `keyword`, 빈 `message`, 해석할 수 없는 형식은 AI 호출 실패(HTTP 502)로 처리합니다.
- 처방을 요청하는 시점과 화면 흐름은 프론트엔드에서 정합니다. 대화 응답에는 처방 시점을 알리는 값을 넣지 않습니다.

### 로컬 개발 및 통합 검증

가상환경 생성·활성화:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

- `.env.example`을 `.env`로 복사하고 서버 설정값을 입력합니다. 실제 키나 비밀값은 예시 파일에 넣지 않습니다.
- React 빌드 결과는 FastAPI 시작 시 감지하므로 빌드 후 서버를 재시작합니다.

- 공통 설치·배포 실행 명령은 `docs/DEPLOYMENT.md`를 사용합니다. 로컬 개발 시 backend 명령에 `--reload`를 추가하고, 별도 터미널에서 `cd frontend`, `npm ci`, `npm run dev`를 실행합니다. Vite 주소는 `http://127.0.0.1:5173`입니다.
- DB 모듈은 DATABASE_URL이 비어 있으면 `sqlite:///./chatbot.db`를 사용합니다. `.env`는 자동 로딩되지 않으므로 Uvicorn의 `--env-file .env` 또는 프로세스 환경 변수로 전달합니다.
- DB 회귀 검증은 `python -m unittest discover -s tests -v`로 수행합니다. 기존 23개 테스트는 DB 기반 검증이며 인증·AI HTTP 통합 및 Railway 재배포 검증을 대신하지 않습니다.
- 담당자 연동 후 인증·AI·DB 저장 실패 시나리오를 함께 검증합니다. Railway Volume 연결·쓰기 권한·재배포 후 데이터 보존과 외부 서비스 접근은 실제 배포 환경에서 확인합니다.
- DB 증빙에는 테스트 계정 데이터를 사용합니다. 로그인 없이 사용할 수 있는 테스트용 로그인 API를 만들지 않습니다.

## Environment Variables

백엔드 환경 변수 기준은 다음과 같습니다. 빈 값은 실제 값이 아닌 설정 자리표시자입니다.

```dotenv
SECRET_KEY=
DATABASE_URL=
CODYSSEY_API_KEY=
AI_API_URL=https://copa.codyssey.kr/v1/chat/completions
AI_MODEL=gpt-5.4
AI_TIMEOUT=30
```

- `SECRET_KEY`: 세션 쿠키 인증에 사용하는 비밀값
- `DATABASE_URL`: 로컬 또는 배포 SQLite DB 연결 경로
- `CODYSSEY_API_KEY`: 서버에서 사용하는 Codyssey virtual key
- `AI_API_URL`: Codyssey Chat Completions API URL
- `AI_MODEL`: AI 모델 이름
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
- misc: 협업 규칙 등 기타 관리 작업

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
    └── <type>/<issue_number>-<module>-<task_name>
```

규칙:

- main은 최종 배포용 브랜치입니다.
- develop은 기능 통합용 개발 브랜치입니다.
- 모든 작업 브랜치는 원격 최신 상태로 동기화한 develop에서 분기합니다.
- 실제 기능 개발은 feature 브랜치에서 진행합니다.
- 작업 브랜치 → Pull Request → develop 순서로 병합합니다.
- main과 develop에 기능 코드를 직접 push하지 않습니다.
- AI 코딩 도구도 사용자가 명시적으로 요청하지 않는 한 main/develop에 직접 commit 또는 push하지 않습니다.

브랜치 이름 형식: `<type>/<issue_number>-<module>-<task_name>`

Types:

- feature: 새로운 기능 개발
- fix: 버그 수정
- chore: 환경 설정 및 기타 작업
- docs: 문서 작업
- misc: 협업 규칙 등 기타 관리 작업

예시:

- `feature/12-auth-sign_up`
- `fix/13-auth-login_error`
- `chore/14-deploy-railway_setup`
- `docs/15-db-verification_guide`
- `misc/16-workflow-branch_naming`

브랜치 이름 규칙:

- `issue_number`는 먼저 생성한 실제 GitHub Issue 번호이며 `#`은 붙이지 않습니다. 위 번호는 형식 예시입니다.
- `module`은 `db`, `auth`, `workflow`처럼 변경하는 모듈 또는 영역을 나타냅니다.
- `module`과 `task_name`은 영문 소문자로 작성하고, 여러 단어는 underscore(`_`)로 구분합니다.
- `task_name`은 작업 내용을 짧게 표현합니다. 예: `storage_and_history`.
- type 뒤에는 `/`, issue_number·module·task_name 사이에는 `-`를 사용합니다.
- 작업자 GitHub ID 대신 Issue 번호로 작업을 식별합니다.

### Issue 및 작업 브랜치 연결

- 작업 Issue를 먼저 생성하고 목적, 과제 대응 항목, 작업 범위, 완료 조건 및 의존성을 기록합니다. 큰 작업은 상위 Issue와 하위 Task로 나눕니다.
- Issue의 Development → Create a branch에서 위 이름을 입력하고 최신 `develop`을 기준으로 브랜치를 생성합니다. 기본 기준 브랜치인 `main`을 그대로 사용하지 않습니다.
- 생성된 원격 브랜치를 fetch한 뒤 작업별 별도 Git worktree에서 작업합니다.
- 브랜치 이름에 Issue 번호를 넣는 것만으로 GitHub Issue가 자동 연결되지는 않습니다. Development의 연결 상태를 확인합니다.
- PR 본문에 관련 Issue를 명시하고 Development에서 연결을 확인합니다.
- `develop` 대상 PR의 `Closes #번호`는 GitHub 자동 연결·종료를 수행하지 않습니다. 완료 조건 충족 여부를 확인하여 Issue 상태를 관리하고, 기본 브랜치 `main` 반영 시 자동 종료할 경우 해당 PR에 종료 키워드를 사용합니다.
- Issue 관리는 팀의 작업 추적 방식이며, 과제 원문에서 요구하는 브랜치·PR 이력과 개인별 유의미한 커밋 요건을 대체하지 않습니다.

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

- feature, fix, chore, docs, misc 브랜치에서 작업한 내용은 Pull Request를 통해 병합합니다.
- 기능 개발 브랜치는 기본적으로 develop을 base branch로 사용합니다.
- main에는 직접 기능 PR을 생성하지 않습니다.
- main 반영은 develop → main Pull Request를 통해 진행합니다.
- PR 생성 전 현재 브랜치, 변경사항, commit 및 push 상태를 확인합니다.
- PR 제목과 본문은 실제 변경 내용을 기준으로 작성합니다.
- GitHub CLI를 사용할 수 있는 경우 `gh pr create`를 사용합니다.
- 사용자가 명시적으로 요청하지 않은 PR merge는 수행하지 않습니다.

### PR Reviewer

모든 작업 PR과 `develop → main` 통합 PR은 생성 시 작성자에 따라 GitHub Reviewer를 실제 지정합니다.

| PR 작성자 | Reviewer |
| --- | --- |
| peachily | b0e2 |
| b0e2 | peachily |
| jungmyung16 | peachily |
| TraceofLight | peachily |

- 작성자는 자신의 PR Reviewer가 될 수 없습니다.
- Codex도 PR 생성을 요청받으면 본문에 이름만 쓰지 않고 GitHub의 Reviewer에 지정합니다. GitHub CLI에서는 `--reviewer`를 사용합니다.
- 권한이나 환경 문제로 지정할 수 없으면 임의의 다른 Reviewer를 선택하지 않고 사용자에게 알립니다.

### Merge Policy

- 작업 브랜치 → PR → develop, develop → PR → main 흐름을 따릅니다.
- 지정된 Reviewer의 Approve를 받은 후 merge합니다.
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

## 문서 역할 및 작성 규칙

문서는 아래 역할에 맞게 수정합니다. README와 docs/는 이용자·평가자가 읽는 서비스 소개 및 제출 자료이고, AGENTS.md는 팀원과 AI 코딩 도구가 따르는 내부 개발 기준입니다.

### 문서별 역할

- `AGENTS.md`: 확정된 개발 계약, 입력 검증·인증·오류 처리 규칙, 담당 영역 간 연동 방법, 로컬 개발·테스트 절차, Git·Issue·PR·Reviewer 규칙
- README: 이용자 관점의 서비스 소개, 문제·대상 사용자, 사용 흐름, 주요 경험, 외부 접속 URL 및 상세 문서 링크
- `docs/ARCHITECTURE.md`: 기술 스택, 아키텍처, 주요 구성요소와 처리 흐름
- `docs/DEPLOYMENT.md`: 환경 변수 키·설정 방법, 실행·배포 방법, 민감정보 관리
- `docs/API.md`: API 명세와 요청·응답 예시
- `docs/DATABASE.md`: ERD 또는 테이블·필드 설명, DB 확인 방법(SQL·API·화면·스크립트·증빙 중 1개 이상)
- `docs/TEAM.md`: 역할 분담과 개인별 작업 요약. 실제 Git 이력과 일치해야 합니다.

### 작성 기준

- README에는 기술 스택 표, 아키텍처·ERD, 환경 변수, 설치 명령, 로컬 접속 방법, 개발 진행 상태 또는 팀 내부 작업 지시를 넣지 않습니다. 필요한 상세 내용은 해당 docs/ 문서로 연결합니다.
- docs/에는 과제 요구사항과 최종 결과를 설명·검증하는 데 필요한 내용을 기록합니다. 개발자가 지켜야 할 약속이나 담당자에게 연결·수정을 지시하는 내용은 AGENTS.md에 둡니다. 별도의 내부 연동 안내 문서를 docs/에 만들지 않습니다.
- 제출용 API 명세는 실제 구현을 기준으로 작성합니다. 구현 전의 확정 계약은 AGENTS.md에서 관리하며, 제출 문서에 구현 완료 사실처럼 옮기지 않습니다.
- 미확정·미검증 내용은 짧은 HTML TODO 주석으로 남깁니다. 미구현 기능을 완료된 것으로 쓰거나, 제출 문서에 긴 진행 상황·주의 문구를 덧붙이지 않습니다.
- 같은 설명은 한 문서에 두고 다른 문서에서는 링크로 참조합니다. 내용 이동 시 제출 필수 항목을 누락하지 않고 기존 링크와 이미지 경로도 갱신합니다.
- 기술적 설계·구현 결과 설명과 내부 개발 규칙을 구분합니다. 예를 들어 테이블·조회 방식은 DATABASE, 실행 재현·환경 설정은 DEPLOYMENT, 트랜잭션 사용 주의사항·담당자 연동 절차는 AGENTS에 둡니다.
- 서비스 화면·다이어그램·개인별 작업 내역은 실제 결과와 일치시킵니다. 미확정 API 경로, 팀원 작업 실적 또는 배포 검증 결과를 임의로 작성하지 않습니다.
- 문서 개수는 고정 요건이 아닙니다. 새 문서는 기존 문서로 담기 어려운 제출 항목이 있을 때만 추가하며, 내부 규칙은 AGENTS.md로 모읍니다.

### 제출 확인

- GitHub Repository 링크, `.env.example`, `.gitignore`를 제출 자료에 포함합니다. README에 자기 저장소 링크를 중복 표시할 필요는 없습니다. `.env`와 비밀값은 제외합니다.
- 제출 전 외부 네트워크에서 서비스 접속과 주요 기능을 확인합니다.
