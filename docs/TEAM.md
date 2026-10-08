# 팀 역할 및 협업 내역

4인 팀의 역할과 실제 Git·PR 이력에 근거한 개인별 작업 내용을 정리합니다. 기준은 `develop` `df73335`이며 후속 PR은 병합 상태를 구분합니다.

## 역할과 구현 내용

| 팀원 | 주 담당 | 구현·검증 내용 |
| --- | --- | --- |
| 장정명 ([jungmyung16](https://github.com/jungmyung16)) | 인증·사용자 관리 | Argon2, 입력 검증, 회원가입·로그인·로그아웃·현재 사용자 API, 세션·쿠키 정책, 보호 API 인증·사용자별 데이터 분리 테스트 |
| 김희준 ([TraceofLight](https://github.com/TraceofLight)) | DB·대화 기록 | SQLite 연결·세션, User·Chat, UTC 타입·제약·인덱스, 대화 저장·최근 5개·전체 조회, SQL·읽기 전용 검증 도구 |
| 정빈 ([b0e2](https://github.com/b0e2)) | AI 챗봇·서버 연결 | Codyssey API 설정·호출, 문맥·프롬프트, 대화·처방 API, timeout·예외 처리, 로그·DB 초기화·라우터 등록 |
| 김수정 ([peachily](https://github.com/peachily)) | 웹 UI·API 연결 | React/Vite 기반, 회원가입·로그인·대화·처방 UI, API hooks, 반응형·접근성·오류 상태, 배포 기반과 공통 문서·협업 규칙 |

세부 경로와 공통 파일 변경 원칙은 [개발 규칙](DEVELOPMENT.md#담당-영역과-변경-원칙)을 참조합니다.

## 개인별 작업과 병합 PR

아래 PR은 모두 develop 대상 병합 이력으로 확인했습니다. 링크에서 변경 파일·개별 커밋·리뷰를 확인할 수 있습니다.

| 담당 | Issue → PR | 작업 |
| --- | --- | --- |
| 장정명 | #23 → [#49](https://github.com/peachily/codyssey1-termproject/pull/49) | 해시·입력 스키마·400 변환·세션 환경 설정·쿠키 검증 |
| 장정명 | #40 → [#50](https://github.com/peachily/codyssey1-termproject/pull/50) | 회원가입·중복·DB 저장 실패·통합 테스트 |
| 장정명 | #41 → [#51](https://github.com/peachily/codyssey1-termproject/pull/51) | 로그인·세션 교체·현재 사용자·로그아웃 |
| 장정명 | #48 → [#52](https://github.com/peachily/codyssey1-termproject/pull/52) | 챗봇·처방 인증, 사용자별 데이터 분리, 실패·복구 통합 검증 |
| 김희준 | #9 → [#15](https://github.com/peachily/codyssey1-termproject/pull/15) | Issue 기반 브랜치 명명·협업 규칙 |
| 김희준 | #10 → [#16](https://github.com/peachily/codyssey1-termproject/pull/16) | SQLite 엔진·세션·외래키·초기화 |
| 김희준 | #11 → [#17](https://github.com/peachily/codyssey1-termproject/pull/17) | 모델·UTC·유일 제약·복합 인덱스 |
| 김희준 | #12 → [#18](https://github.com/peachily/codyssey1-termproject/pull/18) | 저장·rollback·사용자별 조회·최근 5개 문맥 |
| 김희준 | #13 → [#19](https://github.com/peachily/codyssey1-termproject/pull/19) | DB 인터페이스·서버 연동 계약 문서화 |
| 김희준 | #14 → [#20](https://github.com/peachily/codyssey1-termproject/pull/20) | DB 문서·SQL·읽기 전용 도구·검증 |
| 정빈 | #24 → [#32](https://github.com/peachily/codyssey1-termproject/pull/32) | AI 설정·로그 기반 |
| 정빈 | #25 → [#33](https://github.com/peachily/codyssey1-termproject/pull/33) | Chat Completions·timeout·실패 유형·로그 |
| 정빈 | #26 → [#34](https://github.com/peachily/codyssey1-termproject/pull/34) | 최근 문맥 구성·대화 톤 |
| 정빈 | #27 → [#37](https://github.com/peachily/codyssey1-termproject/pull/37) | DB 초기화·요청 ID·라우터 등록 |
| 정빈 | #28 → [#35](https://github.com/peachily/codyssey1-termproject/pull/35) | 대화 API·입력 검증·AI 및 저장 오류 |
| 정빈 | #29 → [#36](https://github.com/peachily/codyssey1-termproject/pull/36) | 처방·고정 색상·대화 단계·형식 재시도 |
| 정빈 | #30 → [#38](https://github.com/peachily/codyssey1-termproject/pull/38) | AI API·아키텍처·개인 작업 문서 |
| 김수정 | [#1](https://github.com/peachily/codyssey1-termproject/pull/1), [#3](https://github.com/peachily/codyssey1-termproject/pull/3), [#5](https://github.com/peachily/codyssey1-termproject/pull/5), [#7](https://github.com/peachily/codyssey1-termproject/pull/7) | Railway·공통 개발 기반·API 계약·Codyssey 설정 |
| 김수정 | #21 → [#22](https://github.com/peachily/codyssey1-termproject/pull/22) | 서비스 소개·제출 문서 구조 |
| 김수정 | #42 → [#43](https://github.com/peachily/codyssey1-termproject/pull/43) | 디자인 시스템·반응형 장면 |
| 김수정 | #44 → [#45](https://github.com/peachily/codyssey1-termproject/pull/45) | 회원가입·로그인·세션 복원·입장 전환 |
| 김수정 | #46 → [#47](https://github.com/peachily/codyssey1-termproject/pull/47) | 올빼미·대화 UI·전송 및 오류 상태 |
| 김수정 | #53 → [#54](https://github.com/peachily/codyssey1-termproject/pull/54) | 처방 API·약병·위로 메시지 화면 |
| 김수정 | #56 → [#57](https://github.com/peachily/codyssey1-termproject/pull/57) | 화면·에셋 정리·실패 입력 복원 |

#13의 최종 작업은 DB 인터페이스 문서이며 HTTP 기록 라우터 완성이 아닙니다. 초기 라우터 추가 커밋 뒤 역할 분리에 따라 철회된 이력이 있으므로 최종 기여를 구분했습니다.

## 후속 작업

김수정의 #58 → [PR #59](https://github.com/peachily/codyssey1-termproject/pull/59)는 본인 기록 조회 API·날짜별 모달·처방 복귀·예외 및 회귀 테스트를 포함합니다. 문서 작성 시점에는 리뷰·병합 전이므로 위 develop 기여 집계와 구분합니다. 이번 문서 정리는 [Issue #60](https://github.com/peachily/codyssey1-termproject/issues/60)에서 진행합니다.

## 커밋 집계

2026-10-08, `develop` `df73335`의 merge 제외 작성자별 커밋 수:

| 작성자 | 개수 |
| --- | ---: |
| peachily | 24 |
| jungmyung (GitHub jungmyung16) | 22 |
| b0e2 | 29 |
| TraceofLight | 13 |

모두 수량 기준 10개 이상이며 “유의미한 커밋”의 내용은 각 PR과 diff로 확인합니다. merge 커밋과 병합 전 #58 작업을 이 집계에 포함하지 않았습니다.

**저장소 루트**에서 동일 기준 재현:

```sh
git shortlog -sn --no-merges df73335
git log --no-merges --format='%h %an %s' df73335
git log --merges --oneline df73335
```

최신 develop은 커밋을 추가하면 수치가 달라집니다. 이름만으로 기여를 추정하지 않고 작성자·실제 변경·PR 내역을 함께 확인합니다.

## 협업 구조

담당 기능 브랜치를 PR로 develop에 통합하고, develop → main PR로 배포 코드를 반영합니다. 지정 리뷰어의 승인 후 Merge commit 방식으로 병합하는 것이 팀 규칙입니다. 이는 운영 규칙이며 모든 과거 PR의 승인 여부를 이 문서에서 별도로 보증하는 것은 아닙니다. Issue·브랜치·PR·리뷰어·커밋 형식은 [DEVELOPMENT](DEVELOPMENT.md#git-작업-흐름)에 모았습니다.
