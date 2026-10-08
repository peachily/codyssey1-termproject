# API 명세

요청·응답과 오류를 실제 라우터 및 스키마 기준으로 설명합니다. 기준은 `develop`의 `df73335`이며 병합 전 기록 조회 API는 별도 표시합니다. 아래 계정·대화 데이터는 형식 설명용 가상 예시입니다.

## 공통 규칙

- 경로는 `/api`로 시작하며 `/health`만 예외입니다. 본문은 JSON입니다.
- 인증은 세션 쿠키를 사용합니다. 프론트 fetch는 로그인 요청을 포함하여 `credentials: 'include'`를 사용합니다.
- 세션의 `user_id`로 DB 사용자를 조회하며 클라이언트가 전달한 사용자 ID로 조회 범위를 바꾸지 않습니다.
- 반환 시각은 UTC ISO 8601 문자열이며 끝에 `Z`가 붙습니다. 소수 초가 포함될 수 있습니다.
- 비밀번호·해시는 응답에 포함하지 않습니다. 오류는 별도 wrapper 없이 `{"detail": "..."}`입니다.
- Pydantic 요청 검증 실패는 라우터에서 400으로 변환합니다.

| API | 인증 | 정상 상태 |
| --- | --- | --- |
| `POST /api/auth/signup` | 불필요 | 201 |
| `POST /api/auth/login` | 불필요 | 200 |
| `POST /api/auth/logout` | 불필요, 있으면 세션 제거 | 200 |
| `GET /api/auth/me` | 필요 | 200 |
| `POST /api/chat` | 필요 | 200 |
| `POST /api/prescription` | 필요 | 200 |
| `GET /health` | 불필요 | 200 |

## 입력 검증

| 필드 | 규칙 |
| --- | --- |
| `username` | 필수 문자열, trim 후 `^[a-z0-9_]{3,30}$` |
| `password` | 필수 문자열, 원문 기준 8~128자, 공백만 있는 값 금지. trim하지 않음 |
| `message` | 필수 문자열, trim 후 1~2000자 |

회원가입·로그인의 누락, null, 문자열 이외 타입, 빈 값·공백만 있는 값, 길이·형식 위반은 400입니다. 비밀번호 문자 조합 규칙은 없습니다. 입력 검증 상세 오류에 입력 원문을 노출하지 않습니다. 로그인되지 않은 보호 API 요청은 입력 오류보다 인증 실패가 먼저 반환될 수 있습니다.

## POST /api/auth/signup

`app/routers/auth.py`의 `signup()`과 `app/services/auth.py`의 `create_user()`를 사용합니다. 사용자명을 정규화하고 비밀번호를 Argon2 해시로 저장합니다. 가입 성공 후에도 로그인은 별도로 요청합니다.

요청 (`password`의 값은 실제 비밀번호가 아닌 자리표시자):

```json
{"username": "sample_user", "password": "<사용자가 입력한 비밀번호>"}
```

성공 — 201:

```json
{"id": 1, "username": "sample_user"}
```

| 상태 | detail | 조건 |
| --- | --- | --- |
| 400 | `Invalid username or password` | 요청 JSON·입력 검증 실패 |
| 409 | `Username already exists` | trim 후 사용자명 중복 |
| 500 | `Failed to save user` | 사용자 조회·저장 트랜잭션 실패 |

## POST /api/auth/login

`login()` → `authenticate_user()`로 처리합니다. 사용자명 없음과 비밀번호 불일치는 같은 401입니다. 성공 시 기존 세션을 비우고 인증된 사용자 ID로 교체합니다.

요청:

```json
{"username": "sample_user", "password": "<사용자가 입력한 비밀번호>"}
```

성공 — 200, 세션 쿠키 설정:

```json
{"id": 1, "username": "sample_user"}
```

| 상태 | detail | 조건 |
| --- | --- | --- |
| 400 | `Invalid username or password` | 요청 JSON·입력 검증 실패 |
| 401 | `Invalid username or password` | 인증 실패 |
| 500 | `Failed to retrieve user` | DB 사용자 조회 실패 |

실패 예시 — 401:

```json
{"detail": "Invalid username or password"}
```

## POST /api/auth/logout

요청 본문 없음. `request.session.clear()`로 현재 세션을 제거합니다. 비로그인·반복 요청도 성공합니다.

성공 — 200:

```json
{"message": "logged out"}
```

별도의 도메인 오류는 정의하지 않습니다.

## GET /api/auth/me

요청 본문 없음. `get_current_user()`로 인증된 DB 사용자를 조회합니다.

성공 — 200:

```json
{"id": 1, "username": "sample_user"}
```

| 상태 | detail | 조건 |
| --- | --- | --- |
| 401 | `Not authenticated` | 세션 누락·부적절한 ID 타입·해당 사용자 없음 |
| 500 | `Failed to retrieve user` | DB 사용자 조회 실패 |

## POST /api/chat

로그인한 사용자의 최근 최대 5개 Q/A를 문맥으로 사용하고, AI 응답을 저장한 뒤 반환합니다. trim한 입력을 `question`으로 저장하며 답변의 줄바꿈과 연속 공백은 하나의 공백으로 정리합니다.

요청:

```json
{"message": "내일 발표가 있어서 잠이 안 와요."}
```

성공 — 200:

```json
{
  "id": 1,
  "question": "내일 발표가 있어서 잠이 안 와요.",
  "answer": "발표를 앞두고 마음이 무거우셨군요. 어떤 장면이 가장 걱정되세요?",
  "created_at": "2026-10-08T12:00:00.123456Z"
}
```

| 상태 | detail | 조건 |
| --- | --- | --- |
| 400 | `Invalid message` | 요청 JSON·message 검증 실패 |
| 401 | `Not authenticated` | 인증 실패 |
| 500 | `Failed to retrieve user` | 인증 사용자 조회 실패 |
| 500 | `Failed to save chat` | 답변 수신 후 대화 commit 실패, rollback |
| 502 | `AI request failed` | 키 누락·전송·HTTP·응답 형식 오류 |
| 504 | `AI response timed out` | AI timeout |

AI 실패·timeout이면 Chat을 저장하지 않습니다. 저장 실패를 성공 응답으로 반환하지 않습니다.

실패 예시 — 504:

```json
{"detail": "AI response timed out"}
```

## POST /api/prescription

요청 본문 없음. 최근 최대 5개 Q/A에서 처방을 생성하며 처방 자체는 DB에 저장하지 않습니다. keyword를 검증하고 아래 고정 color를 붙입니다.

| keyword | color |
| --- | --- |
| ANXIETY | BLUE |
| SADNESS | PURPLE |
| LONELINESS | PINK |
| STRESS | GREEN |
| EXHAUSTION | YELLOW |

성공 — 200:

```json
{
  "keyword": "ANXIETY",
  "color": "BLUE",
  "message": "오늘 다 해결하지 않아도 괜찮아요. 지금은 편히 쉬어가요."
}
```

| 상태 | detail | 조건 |
| --- | --- | --- |
| 400 | `No chats to prescribe` | 본인 대화 기록 없음 |
| 401 | `Not authenticated` | 인증 실패 |
| 500 | `Failed to retrieve user` | 인증 사용자 조회 실패 |
| 502 | `AI request failed` | AI 호출 또는 처방 형식 실패 |
| 504 | `AI response timed out` | AI timeout |

허용하지 않은 keyword, 비문자열·빈 message, 해석 불가 형식은 처방 실패입니다. 출력 keyword는 trim·대문자 정규화 후 검증합니다. 처방 형식 오류는 최대 2회 생성 시도하며 호출 실패·timeout은 재시도하지 않습니다.

## GET /health

요청 본문 없음. 인증 없이 실행 중인 서버의 상태를 확인합니다. 외부 AI나 DB 영속성을 종합 검사하는 경로는 아닙니다.

성공 — 200:

```json
{"status": "ok"}
```

별도의 도메인 오류는 정의하지 않습니다.

## GET /api/me/chats — 병합 전 변경

[PR #59](https://github.com/peachily/codyssey1-termproject/pull/59)에 구현되어 있으며 기준 develop에는 아직 등록되어 있지 않습니다. 아래는 해당 PR의 구현 명세입니다.

요청 본문 없음. 세션 사용자 기준으로 전체 대화를 `created_at DESC, id DESC` 순서로 반환합니다. 사용자 ID 입력과 pagination은 제공하지 않습니다.

성공 — 200:

```json
{
  "chats": [
    {"id": 2, "question": "두 번째 질문", "answer": "두 번째 답변", "created_at": "2026-10-08T12:10:00Z"},
    {"id": 1, "question": "첫 번째 질문", "answer": "첫 번째 답변", "created_at": "2026-10-08T12:00:00Z"}
  ]
}
```

기록이 없으면 `{"chats": []}`입니다. 질문·답변·시각만 조회하며 처방은 포함하지 않습니다.

| 상태 | detail | 조건 |
| --- | --- | --- |
| 401 | `Not authenticated` | 인증 실패 |
| 500 | `Failed to retrieve user` | 인증 사용자 조회 실패 |
| 500 | `Failed to retrieve chats` | 대화 조회 실패 |

## 계약과 구현 범위

위의 오류 표는 라우터·인증 의존성에서 명시적으로 변환하는 응답입니다. 현재 `/api/chat`·`/api/prescription`의 최근 대화 SELECT 오류는 별도의 HTTPException 변환이 없으므로 모든 DB 읽기 오류가 `detail` JSON으로 변환된다고 보장하지 않습니다. 외부 입력·AI·저장 오류 검증은 [테스트 문서](TESTING.md)를 참조합니다.
