# API 명세

## POST /api/auth/signup

### 설명

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->

## POST /api/auth/login

### 설명

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->

## POST /api/auth/logout

### 설명

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->

## GET /api/auth/me

### 설명

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->

## POST /api/chat

### 설명

로그인한 사용자의 질문을 받아 AI 답변을 반환하고 대화를 저장합니다. 같은 사용자의 최근 최대 5개 Q/A를 문맥으로 함께 전달합니다. `message`는 앞뒤 공백을 제거한 뒤 1~2000자의 문자열이어야 하며, 공백을 제거한 값이 `question`으로 저장됩니다.

<!-- TODO: 인증 연결 후 로그인 흐름 확인 -->

### Request

```json
{
  "message": "내일 발표가 있어서 잠이 안 와요."
}
```

### Success Response

200 OK

```json
{
  "id": 1,
  "question": "내일 발표가 있어서 잠이 안 와요.",
  "answer": "내일 발표를 앞두고 마음이 많이 조여 오셨군요, 손님. 어떤 장면이 가장 자꾸 떠오르세요?",
  "created_at": "2026-10-02T08:00:00.123456Z"
}
```

`created_at`은 UTC 기준 ISO 8601 문자열입니다.

### Error Response

| 상태 | detail | 조건 |
| --- | --- | --- |
| 400 | `Invalid message` | `message` 누락, null, 문자열이 아닌 값, 공백만 있는 값, 2000자 초과, 잘못된 JSON |
| 401 | | 로그인되지 않은 사용자 |
| 502 | `AI request failed` | AI 호출 실패 또는 사용할 수 없는 AI 응답 |
| 504 | `AI response timed out` | AI 응답 시간 초과 |
| 500 | `Failed to save chat` | 대화 저장 실패 |

AI 호출이 실패하거나 시간 초과되면 대화를 저장하지 않습니다.

## POST /api/prescription

### 설명

로그인한 사용자의 최근 최대 5개 Q/A를 바탕으로 마법약 처방을 생성합니다. AI가 상태(`keyword`)와 위로 메시지(`message`)를 만들고, 서버가 `keyword`를 검증한 뒤 정해진 `color`를 붙입니다. 처방은 저장하지 않습니다.

| keyword | color |
| --- | --- |
| ANXIETY | BLUE |
| SADNESS | PURPLE |
| LONELINESS | PINK |
| STRESS | GREEN |
| EXHAUSTION | YELLOW |

### Request

요청 본문 없음.

### Success Response

200 OK

```json
{
  "keyword": "ANXIETY",
  "color": "BLUE",
  "message": "시험을 앞두고 잠이 오지 않을 만큼 마음이 무거우셨겠어요. 오늘 밤은 시험 걱정을 잠시 내일로 미뤄 두고, 이 밤만큼은 가만히 쉬어 가셔도 돼요."
}
```

### Error Response

| 상태 | detail | 조건 |
| --- | --- | --- |
| 400 | `No chats to prescribe` | 처방에 사용할 대화 기록 없음 |
| 401 | | 로그인되지 않은 사용자 |
| 502 | `AI request failed` | AI 호출 실패, 허용되지 않은 `keyword`, 빈 `message`, 해석할 수 없는 형식 |
| 504 | `AI response timed out` | AI 응답 시간 초과 |

## GET /api/me/chats

### 설명

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->

## GET /health

### 설명

인증 없이 서버 상태를 확인합니다.

### Request

요청 본문 없음.

### Success Response

200 OK

```json
{"status": "ok"}
```

### Error Response

별도의 도메인 오류 응답은 없습니다.
