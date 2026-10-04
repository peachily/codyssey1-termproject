# 팀 역할 및 작업 내역

## 역할 분담

| 팀원 | 담당 영역 | 주요 작업 |
| --- | --- | --- |
| 장정명 ([jungmyung16](https://github.com/jungmyung16)) | 로그인 · 사용자 인증 | <!-- TODO: 실제 작업 내역 --> |
| 김희준 ([TraceofLight](https://github.com/TraceofLight)) | DB · 대화 기록 | SQLite 연결, 사용자·대화 모델, 대화 저장·조회, 기록 조회 연동 안내, DB 문서 및 검증 |
| 정빈 ([b0e2](https://github.com/b0e2)) | AI 챗봇 | Codyssey API 호출, 대화 문맥 구성, 대화·처방 API, 입력 검증과 AI 예외 처리, 요청·AI 호출 로그, 서버 연결 |
| 김수정 ([peachily](https://github.com/peachily)) | UI · API 연결 | <!-- TODO: 실제 작업 내역 --> |

## 개인별 작업 내역

### 김희준 ([TraceofLight](https://github.com/TraceofLight))

| 관련 Issue | 주요 작업 |
| --- | --- |
| #9 | Issue 기반 브랜치 명명 및 협업 규칙 정리 |
| #10 | SQLite 엔진, 요청별 세션, 외래키 설정, 초기화 및 테스트 |
| #11 | User·Chat 모델, UTC 시각, 외래키·유일 제약 및 복합 인덱스 검증 |
| #12 | 대화 저장·rollback·로그, 사용자별 기록 및 최근 5개 문맥 조회 |
| #13 | 세션 인증·DB 초기화·기록 조회 연결 계약 문서화 |
| #14 | DB 문서, 읽기 전용 확인 도구 및 테스트 |

### 정빈 ([b0e2](https://github.com/b0e2))

| 관련 Issue | 주요 작업 |
| --- | --- |
| #24 | AI 설정 환경 변수 로딩, 로그 기본 설정 및 테스트 |
| #25 | Codyssey Chat Completions 호출, Timeout·실패 유형 구분, AI 호출 로그 |
| #26 | 최근 5개 Q/A 문맥 메시지 구성, 대화 톤 시스템 메시지 |
| #27 | 서버 시작 시 DB 초기화, 요청 수신 로그와 요청 ID, 라우터 등록 |
| #28 | `POST /api/chat`, message 검증, AI·저장 오류 응답 |
| #29 | `POST /api/prescription`, keyword 검증·color 매핑, 대화 마무리 흐름, 처방 계약 정리 |
| #30 | AI 파트 API 명세, 처리 흐름, 작업 내역 문서 |

### 장정명 ([jungmyung16](https://github.com/jungmyung16))

<!-- TODO: 실제 작업 내역 -->

### 김수정 ([peachily](https://github.com/peachily))

<!-- TODO: 실제 작업 내역 -->
