# 기술 및 시스템 구성

실제 서버·프론트엔드 구성과 인증, 대화, 처방의 처리 흐름을 설명합니다. API 형식은 [API 명세](API.md), 실행 방법은 [실행 및 배포](DEPLOYMENT.md)를 참조합니다.

| 구성 | 기술 | 역할 |
| --- | --- | --- |
| 웹 화면 | React, Vite, JavaScript | 사용자 입력과 응답 표시 |
| 서버 | Python, FastAPI, Uvicorn, Pydantic | API 요청 처리 및 서버 측 AI 연동 |
| 데이터베이스 | SQLite, SQLAlchemy 2.x | 사용자와 일반 대화 Q/A 저장 |
| 인증 | SessionMiddleware, pwdlib[argon2] | 세션 쿠키 및 비밀번호 해시 |
| AI | Codyssey Chat Completions API, requests, gpt-5.4 | 대화 응답과 처방 메시지 생성 |
| 배포 | Railway | React 빌드와 FastAPI를 하나의 서비스 URL로 제공 |

## 아키텍처

![KKAMURUK 시스템 아키텍처](diagrams/kkamuruk-architecture.png)

<!-- TODO: 최종 아키텍처 이미지 교체 -->

## 대화 처리 설계

웹 화면에서 입력한 질문은 FastAPI 서버로 전달됩니다. 서버는 인증된 사용자의 최근 최대 5개 Q/A를 문맥으로 구성해 Codyssey API를 호출하고, 정상 응답을 받은 일반 대화 Q/A를 사용자 식별 정보·생성 시각과 함께 저장하는 구조입니다.

마법약 처방은 대화 내용을 바탕으로 상태와 위로 메시지를 생성하는 별도 결과이며, 일반 대화 기록과 달리 DB에 저장하지 않습니다.

### 처리 순서

`POST /api/chat` 요청 하나는 다음 순서로 처리됩니다.

1. 로그인 사용자 확인
2. `message` 검증
3. 같은 사용자의 최근 최대 5개 Q/A 조회
4. 시스템 메시지, 최근 Q/A, 현재 질문으로 메시지 구성
5. Codyssey API 호출
6. 질문과 답변 저장
7. 응답 반환

AI를 호출하기 전에 DB 읽기를 끝내서, 응답을 기다리는 동안 DB를 점유하지 않습니다.

### 문맥 유지

AI는 이전 대화를 기억하지 않으므로, 요청마다 같은 사용자의 최근 최대 5개 Q/A를 시간순으로 다시 전달하고 마지막에 현재 질문을 붙입니다. 다른 사용자의 대화는 조회 단계에서 제외됩니다.

### 대화 마무리

서버가 최근 1시간 안의 대화 수와 사용자가 쓴 글의 분량을 세어 대화 단계를 정하고, 시스템 메시지에 단계 안내를 덧붙입니다. 처음에는 공감하며 질문하고, 세 번째 이야기이거나 이야기가 충분히 나오면 약을 지어 드릴지 권하며, 그 뒤에는 질문 없이 마무리합니다. 처방은 화면에서 `POST /api/prescription`을 요청할 때 생성됩니다.

### 입력 검증

`message`는 서버에서 검증합니다. 누락, null, 문자열이 아닌 값, 공백만 있는 값, 2000자 초과는 HTTP 400으로 응답하고 AI를 호출하지 않습니다.

### AI 예외 처리

| 상황 | 응답 | 대화 저장 |
| --- | --- | --- |
| AI 응답 시간 초과 (`AI_TIMEOUT`, 기본 30초) | 504 | 저장하지 않음 |
| 연결 오류, HTTP 오류, 사용할 수 없는 응답, API Key 없음 | 502 | 저장하지 않음 |
| 처방의 `keyword`·`message`가 형식에 맞지 않음 | 1회 재요청 후 502 | 해당 없음 |
| 대화 저장 실패 | 500 | rollback |

모든 실패는 `detail`이 담긴 오류 응답으로 바뀌며 서버는 계속 동작합니다. AI 답변은 그대로 믿지 않고, 처방의 `keyword`는 서버가 허용 목록으로 검증하며 `color`는 서버가 정합니다.

### 서버 로그

| 이벤트 | 시점 |
| --- | --- |
| `request_received` | `/api` 요청 수신 |
| `ai_call_start` | AI 호출 시작 |
| `ai_call_success` | AI 응답 수신 (`latency_ms` 포함) |
| `ai_call_failure` | AI 실패 또는 시간 초과 (`reason` 포함) |
| `db_save_success` | 대화 저장 성공 |
| `db_save_failure` | 대화 저장 실패 |

요청마다 `request_id`를 부여해 요청 수신 로그와 AI 호출 로그를 같은 값으로 연결합니다. 로그에는 질문·답변 원문과 API Key를 남기지 않습니다.

```text
INFO app.main request_received request_id=44cc91f1f727 method=POST path=/api/chat
INFO app.services.ai ai_call_start user_id=1 request_id=44cc91f1f727 model=gpt-5.4
INFO app.services.ai ai_call_success user_id=1 request_id=44cc91f1f727 latency_ms=2314
INFO app.services.chats db_save_success user_id=1 chat_id=7
```

<!-- TODO: 최종 인증 흐름 -->

## 관련 문서

- [API 명세](API.md)
- [DB 구조 및 저장 내용 확인](DATABASE.md)
- [실행·배포 및 환경 변수](DEPLOYMENT.md)
