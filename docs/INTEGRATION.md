# 인증·AI 담당 연동 안내

## 구현 범위 및 공통 연결

DB 구현은 사용자와 대화 Q/A 저장 및 조회 기반 제공. 회원가입·로그인, AI 호출, 마법약 처방 생성은 각 담당자 구현 범위. 아래 코드는 연결 위치 설명용이며 완성된 라우터 구현이 아님.

- app.database.get_db: FastAPI Depends로 요청별 Session 전달
- app.models.User: id, username, password_hash, created_at 제공
- app.models.Chat: id, user_id, question, answer, created_at 제공
- app.dependencies.get_current_user: 세션의 정수 user_id 및 DB 사용자 존재 확인, 실패 시 HTTP 401
- app.main.create_app: SessionMiddleware, 시작 시 테이블 초기화, ChatSaveError 처리 등록
- 라우터 등록: app/main.py의 React 정적 파일 mount 이전 위치 사용

## 인증 담당

username 정규화·검증과 pwdlib Argon2 해시 생성은 인증 담당 책임. User.password_hash에는 생성한 해시만 저장. 사용자명 중복은 DB UNIQUE 제약으로도 차단하며 중복 시 rollback 후 HTTP 409 처리. 그 외 저장 실패는 rollback·db_save_failure 로그 및 HTTP 500 처리. 성공 commit 이후에만 db_save_success 기록.

비밀번호 검증 완료 후 세션 설정 예시:

```python
# user는 DB에서 조회하고 비밀번호 검증을 마친 User 객체
request.session.clear()
request.session["user_id"] = user.id
```

문자열 또는 bool user_id는 인증 실패 처리. 클라이언트가 전달한 사용자 ID를 인증 근거로 사용 금지. 로그아웃은 request.session.clear() 적용. 다른 인증 필요 라우터에서도 Depends(get_current_user) 재사용 가능. 비밀번호·해시를 세션 및 응답에 포함하지 않음.

SECRET_KEY는 시작 전에 환경 변수로 제공. 빈 값이면 시작 거부. SESSION_HTTPS_ONLY는 HTTPS 배포에서 true, 로컬 HTTP에서는 false 설정. .env 파일은 uvicorn의 --env-file .env 옵션 또는 배포 환경의 Variables로 로딩.

## AI 담당

app.services.chats의 get_recent_chats(db, user_id)는 최근 최대 5개 대화를 오래된 순으로 반환. save_chat(db, user_id, question, answer)는 정상 AI 응답 저장 및 commit 후 Chat 반환. 두 함수 모두 인증 완료된 user.id 사용.

```python
from app.services.chats import get_recent_chats, save_chat

# 인증·message 검증 이후의 연결 흐름 예시
user_id = user.id
recent = get_recent_chats(db, user_id)
messages = []
for chat in recent:
    messages.append({"role": "user", "content": chat.question})
    messages.append({"role": "assistant", "content": chat.answer})
messages.append({"role": "user", "content": validated_message})

# 조회 결과를 일반 데이터로 만든 뒤 읽기 트랜잭션 종료
# 이 시점에 미저장 변경이 없는 전용 요청 세션이라는 전제
db.rollback()

# AI 담당의 API 호출·timeout·응답 검증 위치
# 성공한 answer를 얻은 이후에만 아래 함수 호출
saved = save_chat(db, user_id, validated_message, answer)
```

AI 호출 중 쓰기 트랜잭션을 열거나 미리 빈 Chat을 삽입하지 않음. 실패·timeout에서는 save_chat 호출 금지. AI timeout은 HTTP 504, 기타 호출 실패는 HTTP 502로 처리하며 AI 담당 로그 이벤트 기록 필요.

저장 실패 시 save_chat은 rollback 후 ChatSaveError 발생. app/main.py의 전역 처리기가 HTTP 500과 detail: Failed to save chat 반환. 오류를 잡아서 성공 응답으로 바꾸지 않음. 질문·응답 및 내부 DB 오류 원문을 로그에 추가하지 않음.

save_chat은 전달한 세션 전체를 commit하므로 관계없는 변경을 같은 세션에 넣지 않음. 위 rollback도 무관한 미저장 변경을 취소할 수 있으므로 전제 유지 필요. DB 함수 연결 후 인증·AI 호출의 실제 통합 시나리오는 해당 담당자와 공동 검증 필요.

## KKAMURUK 마법약 처방 제안 계약

현재 저장 범위는 일반 대화 Q/A이며 최종 처방의 keyword, color, message는 별도 저장·조회하지 않음. 기존 POST /api/chat 응답 계약과 GET /api/me/chats 응답은 유지. 처방 전용 endpoint 경로 및 요청·응답 확정은 팀 협의 사항이며 이 문서는 해당 API 구현 완료를 의미하지 않음.

서버에서 keyword를 아래 enum으로 검증하고 color를 고정 매핑하는 방식 제안. AI가 임의로 반환한 색상이나 미정의 keyword를 그대로 신뢰하지 않는 설계. message는 처방 설명이며 실제 검증 규칙은 AI 담당과 합의 필요.

| keyword | color |
| --- | --- |
| ANXIETY | BLUE |
| SADNESS | PURPLE |
| LONELINESS | PINK |
| STRESS | GREEN |
| EXHAUSTION | YELLOW |

처방 결과를 Chat.answer에 우회 저장하거나 users·chats에 임의 컬럼 추가하지 않음. 향후 처방 기록 기능을 요청하면 별도 이슈에서 보존 범위·테이블 및 API 계약 협의 필요.
