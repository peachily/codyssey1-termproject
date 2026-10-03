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

| 키 | 용도 |
| --- | --- |
| `SECRET_KEY` | 세션 쿠키 서명 |
| `DATABASE_URL` | SQLite 연결 URL |
| `CODYSSEY_API_KEY` | Codyssey API 인증용 virtual key |
| `AI_API_URL` | API URL (`https://copa.codyssey.kr/v1/chat/completions`) |
| `AI_MODEL` | 모델 이름 (`gpt-5-mini`) |
| `AI_TIMEOUT` | AI 요청 제한 시간(초, 기본값 30) |

`.env.example`을 프로젝트 루트의 `.env`로 복사한 뒤 값을 입력합니다. `.env`는 Git에서 제외됩니다.

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

<!-- TODO: 최종 배포 정보 -->

## 7. 상세 문서

- [API 명세](docs/API.md)
- [DB 구조 및 저장 내용 확인 방법](docs/DATABASE.md)
- [팀 역할 및 개인별 작업 내역](docs/TEAM.md)
