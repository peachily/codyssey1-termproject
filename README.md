# 프로젝트명

<!-- TODO: 프로젝트명 -->

<!-- TODO: 한 줄 서비스 소개 -->

## 1. 프로젝트 소개

### 문제 정의

<!-- TODO: 문제 정의 -->

### 타겟 사용자

<!-- TODO: 타겟 사용자 -->

### 핵심 사용 시나리오

<!-- TODO: 핵심 사용 시나리오 -->

## 2. 주요 기능

<!-- TODO: 최종 구현 기능 -->

## 3. 기술 스택

| 구분 | 기술 |
| --- | --- |
| Frontend | React, Vite, JavaScript, HTML/CSS, fetch, REST API + JSON |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Database | SQLite, SQLAlchemy 2.x ORM |
| 인증 | Starlette SessionMiddleware 세션 쿠키, pwdlib[argon2] |
| AI | Codyssey 제공 OpenAI 호환 Chat Completions API, requests, `gpt-5-mini` |
| 배포 | Railway |

## 4. 시스템 구조

<!-- TODO: 최종 시스템 구조 및 구성요소 설명 -->

## 5. 실행 방법

Python 3.14, Node.js 22(22.12 이상), npm을 준비하고 저장소 루트에서 시작합니다.

### 환경 변수

환경 변수는 [.env.example](.env.example)을 기준으로 설정합니다.

| 키 | 용도·설정 예시 |
| --- | --- |
| SECRET_KEY | 서버 담당의 세션 쿠키 서명용 비밀값 |
| DATABASE_URL | 로컬 sqlite:///./chatbot.db, Railway sqlite:////data/chatbot.db |
| CODYSSEY_API_KEY | Codyssey API 인증용 virtual key. 서버 환경에만 등록 |
| AI_API_URL | AI 담당 연동 설정: https://copa.codyssey.kr/v1/chat/completions |
| AI_MODEL | AI 담당 연동 설정: gpt-5-mini |
| AI_TIMEOUT | AI 담당 연동 설정: 30초 |

.env.example의 모든 값은 빈 자리표시자입니다. 프로젝트 루트의 .env로 복사한 뒤 실제 값을 입력합니다. .env는 Git에서 제외됩니다. AI 관련 설정의 적용은 AI 담당 구현과 함께 확인합니다.

앱은 .env를 자동으로 읽지 않습니다. 아래 실행 명령에 --env-file .env를 추가하거나 프로세스 환경 변수로 값을 전달해야 합니다. DATABASE_URL이 비어 있으면 DB 모듈은 로컬 ./chatbot.db를 사용합니다. 인증용 SECRET_KEY 검증 및 세션 설정은 서버 담당 연결 대상입니다.

### Backend

macOS / Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

가상환경 활성화 후 프로젝트 루트에서 실행합니다.

```sh
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

`.env`를 사용하는 경우 `--env-file .env`를 추가합니다.
상태 확인: <http://127.0.0.1:8000/health>.

### Frontend

백엔드를 실행한 상태로 별도 터미널에서 실행합니다.

```sh
cd frontend
npm ci
npm run dev
```

접속 주소: <http://127.0.0.1:5173/>.

### Production

프로젝트 루트에서 가상환경을 활성화한 상태로 실행합니다.

```sh
npm ci --prefix frontend --include=dev
npm run build --prefix frontend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI는 시작 시 `frontend/dist`의 빌드 결과를 제공합니다.
빌드 후 백엔드를 재시작하고 <http://127.0.0.1:8000/>에 접속합니다.
`.env`를 사용하는 경우 `--env-file .env`를 추가합니다. 서버 종료는 `Ctrl+C`를 사용합니다.

## 6. 배포

서비스 접속: [https://codyssey1-termproject-production.up.railway.app](https://codyssey1-termproject-production.up.railway.app)

Railway Variables에 위 환경 변수 등록 및 /data 경로 Volume 마운트가 필요합니다. 현재 배포 시작 명령은 .env를 자동으로 읽지 않습니다. 직접 관리하는 서버에서 .env 파일을 사용할 때는 --env-file .env 옵션을 지정합니다. HTTPS 쿠키 정책은 서버 담당의 인증 구현에서 설정합니다.

로컬 파일 DB 재연결 검증과 실제 Railway 재배포 검증은 구분합니다. Volume 연결 및 재배포 후 데이터 보존 여부는 배포 담당 환경에서 추가 확인이 필요합니다.

## 7. 상세 문서

- [API 명세](docs/API.md)
- [DB 구조 및 저장 내용 확인 방법](docs/DATABASE.md)
- [팀 역할 및 개인별 작업 내역](docs/TEAM.md)
- [인증·AI 담당 연동 안내](docs/INTEGRATION.md)

## 8. DB 검증

프로젝트 루트에서 아래 명령 실행:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

DB 연결·제약·저장 실패 rollback·사용자별 조회·복합 인덱스·읽기 전용 확인 도구의 23개 테스트 검증. 로컬 검증 환경은 Python 3.12이며 배포 설정의 Python 3.14 및 Railway 실제 재배포 검증은 별도 진행 필요. HTTP 라우터·인증·AI 통합 테스트는 서버 담당 연결 후 수행.
