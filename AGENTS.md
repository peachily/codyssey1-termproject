# AI 코딩 도구 공통 규칙

- 이 저장소는 Python + FastAPI 기반 프로젝트입니다.
- 실제 서비스 기능은 담당자가 명시적으로 요청할 때만 구현합니다.
- 기존 담당자의 코드를 임의로 대규모 수정하거나 재구성하지 않습니다.
- API Key, 비밀번호 등 민감정보를 코드나 Git 추적 파일에 작성하지 않습니다.
- 설정과 민감정보는 환경 변수를 사용하며, 로컬 값은 Git에서 제외되는 `.env`로 관리합니다.
- 필요한 환경 변수의 사용법은 `.env.example`에 실제 비밀값 없이 기록합니다.
- 새로운 패키지를 추가하면 `requirements.txt`를 갱신합니다. 전역 환경의 불필요한 패키지는 포함하지 않습니다.
- 불필요한 파일, 기능, 디렉터리 구조를 임의로 추가하지 않습니다.
- 변경 범위는 요청받은 작업에 한정합니다.
- 현재의 최소 FastAPI 앱과 `GET /`, `GET /health`를 유지합니다.
- 별도 요청 전에는 회원가입, 로그인, DB, AI API, 프론트엔드 및 관련 기능 모듈을 구현하지 않습니다.
- 별도 요청 전에는 Docker나 CI/CD 설정을 추가하지 않습니다.
- 명시적 요청 없이 commit, push, 브랜치 설정 또는 원격 저장소 설정 변경을 하지 않습니다.

## Git Commit Convention

커밋 메시지 형식: `<type>: <한글 설명>`

Types:

- feat: 새로운 기능 추가
- fix: 버그 수정
- docs: 문서 수정
- refactor: 기능 변경 없는 코드 개선
- test: 테스트 코드 추가 및 수정
- chore: 환경 설정, 패키지 등 기타 작업

규칙:

- type은 영어 소문자로 작성합니다.
- 설명은 한글로 작성합니다.
- 하나의 커밋에는 하나의 의미 있는 작업 단위를 담습니다.
- "수정", "업데이트", "작업"처럼 변경 내용을 알 수 없는 커밋 메시지는 사용하지 않습니다.

## Git Workflow

기본 브랜치 구조:

```text
main
└── develop
    └── <type>/<github-id>-<작업명>
```

규칙:

- main은 최종 배포용 브랜치입니다.
- develop은 기능 통합용 개발 브랜치입니다.
- 실제 기능 개발은 develop에서 분기한 feature 브랜치에서 진행합니다.
- 기능 개발 후 Pull Request를 통해 develop에 병합합니다.
- main과 develop에 기능 코드를 직접 push하지 않습니다.
- AI 코딩 도구도 사용자가 명시적으로 요청하지 않는 한 main/develop에 직접 commit 또는 push하지 않습니다.

브랜치 이름 형식: `<type>/<github-id>-<작업명>`

Types:

- feature: 새로운 기능 개발
- fix: 버그 수정
- chore: 환경 설정 및 기타 작업
- docs: 문서 작업

예시:

- `feature/peachily-auth`
- `fix/peachily-login`
- `chore/peachily-railway`
- `docs/peachily-readme`

브랜치 이름 규칙:

- 작업명은 짧은 영문 소문자로 작성합니다.
- 작업자의 GitHub ID를 사용합니다.
- GitHub ID가 명확하지 않으면 임의로 추측하지 말고 사용자에게 확인합니다.
