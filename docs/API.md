# API 명세

인증, 요청·응답 예시와 오류 코드를 정리합니다. 예시 데이터는 가상입니다.

## 공통 규칙

- JSON 통신, 세션 쿠키 인증. fetch는 `credentials: 'include'` 사용.
- 조회 대상은 세션 사용자. 비밀번호·해시는 응답에서 제외.
- 시각은 UTC ISO 8601 (`Z`), 오류는 `{"detail": "..."}`.

## API 목록

| 메서드·경로 | 기능 | 인증 | 성공 | 요청 → 응답 예시 |
| --- | --- | --- | --- | --- |
| `POST /api/auth/signup` | 가입 | — | 201 | 인증 예시 참고 |
| `POST /api/auth/login` | 로그인 | — | 200 | 인증 예시 참고 |
| `POST /api/auth/logout` | 로그아웃 | — | 200 | 본문 없음 → `{"message":"logged out"}` |
| `GET /api/auth/me` | 내 정보 | 필요 | 200 | 본문 없음 → `{"id":1,"username":"sample_user"}` |
| `POST /api/chat` | 질문 | 필요 | 200 | 대화 예시 참고 |
| `POST /api/prescription` | 처방 | 필요 | 200 | 본문 없음 → 처방 예시 참고 |
| `GET /api/me/chats` | 내 전체 기록 | 필요 | 200 | 본문 없음 → 기록 예시 참고 |
| `GET /health` | 서버 상태 | — | 200 | 본문 없음 → `{"status":"ok"}` |

## 입력 검증

| 필드 | 규칙 |
| --- | --- |
| username | 필수 문자열, trim 후 `^[a-z0-9_]{3,30}$` |
| password | 필수 문자열, 원문 8~128자, 공백만 입력 금지, trim 안 함 |
| message | 필수 문자열, trim 후 1~2000자 |

누락·null·잘못된 타입·범위 위반은 400입니다.

## 인증 예시

가입·로그인 요청 (`password`는 자리표시자):

```json
{"username":"sample_user","password":"<사용자가 입력한 비밀번호>"}
```

응답: 가입 201 / 로그인 200. 가입만으로 로그인되지 않으며 로그인 성공 시 세션을 교체합니다.

```json
{"id":1,"username":"sample_user"}
```

## 대화 예시

요청:

```json
{"message":"내일 발표가 있어서 잠이 안 와요."}
```

응답: 본인 최근 최대 5개 Q/A로 답변 생성 후 DB 저장.

```json
{
  "id":1,
  "question":"내일 발표가 있어서 잠이 안 와요.",
  "answer":"어떤 장면이 가장 걱정되세요?",
  "created_at":"2026-10-08T12:00:00Z"
}
```

## 처방 예시

최근 최대 5개 Q/A로 생성하며 처방·색상은 DB에 저장하지 않습니다.

```json
{"keyword":"ANXIETY","color":"BLUE","message":"오늘 다 해결하지 않아도 괜찮아요."}
```

| keyword | color |
| --- | --- |
| ANXIETY | BLUE |
| SADNESS | PURPLE |
| LONELINESS | PINK |
| STRESS | GREEN |
| EXHAUSTION | YELLOW |

- 서버가 keyword·message 검증 후 색상을 고정 매핑.
- 처방 형식 오류만 1회 재시도. 전송 실패·timeout은 재시도하지 않음.

## 기록 예시

본인 전체 기록을 최신순(`created_at DESC, id DESC`)으로 반환합니다. pagination은 없습니다.

```json
{
  "chats":[
    {"id":1,"question":"질문","answer":"답변","created_at":"2026-10-08T12:00:00Z"}
  ]
}
```

기록이 없으면 `{"chats":[]}`입니다.

## 오류 응답

| 대상 | 상태 | detail |
| --- | --- | --- |
| 가입·로그인 입력 | 400 | `Invalid username or password` |
| 가입 중복 / 저장 실패 | 409 / 500 | `Username already exists` / `Failed to save user` |
| 로그인 실패 | 401 | `Invalid username or password` |
| 보호 API 미인증 | 401 | `Not authenticated` |
| 로그인·보호 API 사용자 조회 실패 | 500 | `Failed to retrieve user` |
| 질문 입력 / 저장 실패 | 400 / 500 | `Invalid message` / `Failed to save chat` |
| 처방용 대화 없음 | 400 | `No chats to prescribe` |
| 기록 조회 실패 | 500 | `Failed to retrieve chats` |
| 대화·처방 AI 실패 / timeout | 502 / 504 | `AI request failed` / `AI response timed out` |

504 응답 예시:

```json
{"detail":"AI response timed out"}
```

- AI 실패: 대화 미저장. DB 저장 실패: rollback 후 오류 응답.
- 현재 대화·처방의 최근 기록 SELECT 오류에는 별도 `detail` 변환이 없음.
- 사용자 안내 문구: [오류 처리](DEPLOYMENT.md#오류-처리와-점검).
