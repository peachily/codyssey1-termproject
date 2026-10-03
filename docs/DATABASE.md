# 데이터베이스 구조 및 확인 방법

## 과제 대응 범위

- 과제 2: 테이블·필드 설명, DB 확인 가이드, 실행·환경 변수 문서 제공
- 과제 3·4: 사용자별 질문·응답 누적, 최근 대화 문맥 조회, 사용자 기준 추적
- 과제 4·6: 저장 성공·실패 로그, rollback, 민감정보 분리
- 과제 5: SQLite 파일 DB와 SQLAlchemy ORM 사용
- 과제 7: 내 기록 API 및 확인용 SQL 실행 예시 제공

관련 작업: #10 연결, #11 모델, #12 저장·조회, #13 기록 API, #14 문서·검증. 인증·AI 담당자의 회원가입/로그인 및 AI 호출 라우터는 이 DB 작업의 구현 범위에 포함하지 않는다.

## 테이블 관계

users.id (1) → chats.user_id (N)

사용자는 대화 여러 건을 가지며, 대화는 반드시 존재하는 사용자 한 명에 속한다. 별도 세션 테이블이나 벡터 DB는 두지 않는다. 문맥은 팀 계약에 따라 대화방별이 아닌 사용자별 최근 5개 Q/A이다.

KKAMURUK 최종 마법약 처방의 keyword·color·message는 별도 저장·조회 대상이 아니다. 사용자와 일반 대화 Q/A만 저장한다. 처방의 enum 및 고정 색상 매핑은 [담당자 연동 안내](INTEGRATION.md)의 제안 계약이며, 기존 대화 API를 변경하지 않는다.

## users

| 필드 | SQLite 선언 타입 | 제약조건·의미 |
| --- | --- | --- |
| id | INTEGER | 기본키, 필수, DB에서 식별자 생성 |
| username | VARCHAR | 필수, UNIQUE. 정규화·길이 검증은 인증 담당 계약에 따름 |
| password_hash | VARCHAR | 필수, Argon2 해시를 인증 담당이 생성하여 저장. 평문 비밀번호 저장 금지 |
| created_at | DATETIME | 필수, ORM 삽입 시 UTC 현재 시각 기본값 |

## chats

| 필드 | SQLite 선언 타입 | 제약조건·의미 |
| --- | --- | --- |
| id | INTEGER | 기본키, 필수, DB에서 식별자 생성 |
| user_id | INTEGER | 필수, users.id 외래키, ON DELETE RESTRICT |
| question | TEXT | 필수, 검증 완료된 사용자 질문 |
| answer | TEXT | 필수, 정상적으로 수신한 AI 응답 |
| created_at | DATETIME | 필수, ORM 삽입 시 UTC 현재 시각 기본값 |

외래키는 SQLite 연결마다 PRAGMA foreign_keys=ON으로 활성화한다. 대화가 남은 사용자 삭제는 거부하여 기록의 우발적 삭제를 막는다. 회원 탈퇴·기록 삭제 기능은 이번 범위에 없으므로 별도 정책 없이 cascade를 추가하지 않는다.

created_at의 기본값은 DB 서버 기본값이 아닌 ORM 기본값이다. 직접 SQL로 삽입할 경우 시각을 명시해야 한다. UTCDateTime은 시간대가 있는 값을 UTC로 변환해 저장하고, 조회 시 UTC 시간대 정보를 복원한다. 시간대 없는 datetime 입력은 거부한다. API는 UTC를 나타내는 Z가 붙은 ISO 8601 문자열을 반환한다.

## 인덱스와 조회 순서

- users.username: UNIQUE 제약에 따른 SQLite 유일 인덱스 사용
- chats: ix_chats_user_created_id (user_id, created_at, id) 복합 인덱스 사용
- id 기본키는 SQLite INTEGER PRIMARY KEY 사용. 별도 중복 인덱스 추가 없음

조회는 user_id로 대상을 좁힌 뒤 created_at DESC, id DESC로 정렬한다. 동일 시각에서도 id가 순서를 고정한다. 인덱스를 역방향으로 탐색할 수 있어 ASC/DESC 인덱스를 중복 생성하지 않는다. user_id 단일 인덱스도 복합 인덱스의 선두 컬럼과 겹치므로 추가하지 않는다.

질문·응답 전체를 인덱스에 넣는 covering index는 저장 크기와 쓰기 비용을 늘리므로 사용하지 않는다. 최근 문맥 조회는 DB에서 LIMIT 5를 적용한 뒤 최대 5개만 Python에서 역순으로 바꾸어 오래된 대화부터 제공한다.

EXPLAIN QUERY PLAN 테스트에서 복합 인덱스 사용 및 TEMP B-TREE 정렬 미발생을 확인한다. 작은 테스트 DB 결과를 실제 대규모 서비스의 성능 수치로 해석하지 않는다.

## N+1 방지

모델에 자동 지연 조회를 수행하는 ORM relationship을 추가하지 않았다. 필요한 대화를 user_id 조건의 명시적 SELECT로 한 번에 가져오며 응답 생성 중 사용자 관계를 순회하지 않는다.

저장소 조회 함수별 SELECT는 1회이다. 내 기록 API는 인증 사용자 존재 확인 1회와 대화 조회 1회로 총 2회이다. 테스트는 SQLAlchemy 이벤트로 실제 SQL 실행 횟수를 세어 데이터 개수에 따른 추가 조회가 없는지 검증한다.

향후 관리자 화면에서 여러 사용자의 관련 데이터를 함께 출력한다면 필요한 컬럼의 명시적 JOIN 또는 selectinload 등을 조회 목적에 맞게 선택해야 한다. 현재 응답에 필요하지 않은 관계를 미리 로딩하지 않는다.

## 저장·트랜잭션 계약

- app.database.get_db: 요청별 Session 제공 및 종료 시 반환
- app.services.chats.save_chat: flush로 ID 확보 → commit → db_save_success 기록 → Chat 반환
- 저장 SQLAlchemy 오류: rollback → db_save_failure 기록 → ChatSaveError 발생
- list_user_chats: 본인 전체 기록 최신순 조회
- get_recent_chats: 본인 최근 최대 5개 Q/A 시간순 조회

기본 SessionLocal은 expire_on_commit=False이다. 반환 객체를 읽기 위해 commit 직후 불필요한 재조회를 하지 않는다. 저장 함수는 전달된 세션의 트랜잭션을 commit하므로 무관한 변경을 같은 세션에 넣지 않는다. 로그에는 user_id·chat_id 등 추적값만 포함하며 질문·응답·비밀번호·키·DB 오류 원문은 기록하지 않는다.

AI 담당은 입력 검증 및 인증 후 최근 기록을 조회하고 AI 응답이 성공한 경우에만 save_chat을 호출해야 한다. AI 실패·타임아웃에서는 호출하지 않는다. DB 저장 오류는 HTTP 500과 detail: Failed to save chat으로 처리한다. 실제 AI 파이프라인 통합은 해당 라우터 구현 이후 공동 검증이 필요하다.

SQLite busy_timeout은 5초이다. SQLite의 동시 쓰기 제한을 없애는 설정은 아니다. 긴 AI 호출을 DB 쓰기 트랜잭션 안에서 수행하지 않는다. WAL이나 별도 DB 서버는 현 요구사항만으로 추가하지 않았다.

## 초기화·배포·마이그레이션

FastAPI lifespan에서 모델을 등록한 뒤 create_all로 없는 테이블을 생성하고, 종료 시 엔진을 정리한다. 기존 테이블과 데이터는 삭제하지 않는다. create_all은 기존 테이블 구조 변경을 수행하는 마이그레이션 도구가 아니다. 배포 후 스키마가 바뀌면 백업 및 별도 마이그레이션 절차를 마련해야 한다.

- 로컬: DATABASE_URL=sqlite:///./chatbot.db
- Railway: DATABASE_URL=sqlite:////data/chatbot.db
- Railway에는 /data 경로의 Volume을 먼저 마운트하고 쓰기 권한 확인
- .env.example의 값은 모두 빈 상태. 실제 값은 환경 변수나 Git에서 제외한 .env로 전달
- Railway 현재 시작 명령은 .env를 자동으로 읽지 않으므로 Railway Variables로 값 등록
- 직접 .env 파일을 사용하는 서버는 uvicorn 실행 시 --env-file .env 지정

파일 DB의 재연결 후 데이터 보존은 로컬 테스트로 검증한다. 실제 Railway 재배포 후 보존과 외부 URL 접근은 배포 담당의 환경에서 별도 확인하며, 로컬 결과로 배포 검증을 대신하지 않는다.

## DB 저장 내용 확인

scripts/check_logs.sql은 DB 구조, 사용자별 대화, 최근 5개 조회 계획 확인용 읽기 전용 SQL이다. scripts/check_db.py는 Python 표준 라이브러리로 실행하며, 읽기 전용 연결로 실수에 의한 DB 생성·수정을 방지한다.

실행 예시: python scripts/check_db.py --database ./chatbot.db --user-id 1

Railway Volume 확인 예시: python scripts/check_db.py --database /data/chatbot.db --user-id 1

사용자 ID를 명시해야 하며, 기본 최근 20건만 출력한다. 확인 도구의 limit는 운영 조회 범위를 줄이기 위한 옵션이며 페이지네이션 없는 API 계약과 별개이다. 실제 질문·응답이 출력되므로 증빙 자료에는 테스트 계정 데이터를 사용한다. password_hash는 출력하지 않는다.

로그인 기능 통합 후 GET /api/me/chats에 세션 쿠키를 포함하여 본인의 질문·응답·생성 시각을 JSON으로 확인할 수 있다. 서버에서 로그인 기능 없이 테스트용 로그인 API를 제공하지 않는다.

## 참고

- [SQLite 조회 계획과 복합 인덱스](https://www.sqlite.org/queryplanner.html)
- [SQLite EXPLAIN QUERY PLAN](https://www.sqlite.org/eqp.html)
- [SQLAlchemy 관계 로딩과 N+1](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html)
