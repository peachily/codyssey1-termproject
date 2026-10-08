# 팀 역할 및 협업 내역

팀원별 담당 기능과 작업 내역을 정리합니다.

## 역할과 구현 내용

| 팀원 | 주 담당 | 구현·검증 내용 |
| --- | --- | --- |
| 장정명 ([jungmyung16](https://github.com/jungmyung16)) | 인증·사용자 관리 | Argon2, 입력 검증, 회원가입·로그인·로그아웃·현재 사용자 API, 세션·쿠키 정책, 보호 API 인증·사용자별 데이터 분리 테스트 |
| 김희준 ([TraceofLight](https://github.com/TraceofLight)) | DB·대화 기록 | SQLite 연결·세션, User·Chat, UTC 타입·제약·인덱스, 대화 저장·최근 5개·전체 조회, SQL·읽기 전용 검증 도구 |
| 정빈 ([b0e2](https://github.com/b0e2)) | AI 챗봇·서버 연결 | Codyssey API 설정·호출, 문맥·프롬프트, 대화·처방 API, timeout·예외 처리, 로그·DB 초기화·라우터 등록 |
| 김수정 ([peachily](https://github.com/peachily)) | 웹 UI·API 연결 | React/Vite 기반, 회원가입·로그인·대화·처방 UI, API hooks, 반응형·접근성·오류 상태, 날짜별 기록 조회·처방 복귀, 배포·문서 |

## 주요 PR

| 담당 | 관련 PR | 작업 |
| --- | --- | --- |
| 장정명 | [#49](https://github.com/peachily/codyssey1-termproject/pull/49) · [#50](https://github.com/peachily/codyssey1-termproject/pull/50) · [#51](https://github.com/peachily/codyssey1-termproject/pull/51) · [#52](https://github.com/peachily/codyssey1-termproject/pull/52) | 인증·가입·세션·접근 제어 |
| 김희준 | [#16](https://github.com/peachily/codyssey1-termproject/pull/16) · [#17](https://github.com/peachily/codyssey1-termproject/pull/17) · [#18](https://github.com/peachily/codyssey1-termproject/pull/18) · [#20](https://github.com/peachily/codyssey1-termproject/pull/20) | DB 연결·모델·조회·검증 도구 |
| 정빈 | [#33](https://github.com/peachily/codyssey1-termproject/pull/33) · [#34](https://github.com/peachily/codyssey1-termproject/pull/34) · [#35](https://github.com/peachily/codyssey1-termproject/pull/35) · [#36](https://github.com/peachily/codyssey1-termproject/pull/36) · [#37](https://github.com/peachily/codyssey1-termproject/pull/37) | AI 호출·문맥·대화·처방·서버 연결 |
| 김수정 | [#43](https://github.com/peachily/codyssey1-termproject/pull/43) · [#45](https://github.com/peachily/codyssey1-termproject/pull/45) · [#47](https://github.com/peachily/codyssey1-termproject/pull/47) · [#54](https://github.com/peachily/codyssey1-termproject/pull/54) · [#57](https://github.com/peachily/codyssey1-termproject/pull/57) · [#59](https://github.com/peachily/codyssey1-termproject/pull/59) | 화면 구성·인증 연결·대화·처방·기록 API·날짜별 화면·처방 복귀·회귀 테스트 |

[브랜치·리뷰·병합 규칙](DEVELOPMENT.md#git-작업-흐름)
