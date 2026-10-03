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

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->

## GET /api/me/chats

### 설명

로그인 사용자 자신의 대화를 생성 시각 내림차순, 같은 시각에서는 ID 내림차순으로 조회합니다. 페이지네이션은 제공하지 않습니다. 사용자 ID를 요청으로 받지 않으며 세션에서 인증한 사용자만 조회합니다.

### Request

요청 본문 없음. 로그인 후 발급된 세션 쿠키 필요. 브라우저 fetch에서 credentials: "include" 지정.

### Success Response

200 OK

```json
{
  "chats": [
    {
      "id": 2,
      "question": "오늘 하루가 힘들었어요.",
      "answer": "어떤 일이 있었는지 이야기해 주세요.",
      "created_at": "2026-10-04T01:00:00Z"
    }
  ]
}
```

기록이 없으면 chats는 빈 배열입니다. 비밀번호 해시 및 다른 사용자 정보는 포함하지 않습니다. 생성 시각은 UTC이며 소수 초가 포함될 수 있습니다.

### Error Response

401 Unauthorized: 세션이 없거나, 세션 user_id가 정수가 아니거나, 해당 사용자가 DB에 없는 경우.

```json
{"detail": "Not authenticated"}
```

### 로그인 담당 연동

인증 담당의 로그인 성공 처리에서 기존 세션을 비운 뒤 request.session["user_id"]에 User.id 정수 저장이 필요합니다. 로그인 라우터는 별도 구현 대상이며 현재 문서가 로그인 구현 완료를 의미하지 않습니다. 상세 인터페이스는 [연동 안내](INTEGRATION.md) 참고.

## GET /health

### 설명

<!-- TODO: 설명 -->

### Request

<!-- TODO: 요청 -->

### Success Response

<!-- TODO: 성공 응답 -->

### Error Response

<!-- TODO: 오류 응답 -->
