# Codyssey 1 Term Project

Python + FastAPI 기반 웹 AI 챗봇 서비스의 초기 개발 저장소입니다.
현재는 FastAPI와 React/Vite의 공통 실행 환경 및 `/health` 연결 확인 화면만 제공합니다.
인증, DB 모델, AI 호출, 실제 서비스 화면은 담당자가 구현합니다.

## Python 버전 확인

현재 개발 환경은 **Python 3.14.0**입니다. 같은 버전으로 시작하는 것을 권장합니다.

```sh
python3 --version
```

Windows에서는 `py --version`으로 확인합니다.

## 개발 환경 준비

저장소를 clone한 후 프로젝트 루트에서 실행합니다.

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

가상환경 활성화 후 의존성을 설치합니다.

```sh
python -m pip install -r requirements.txt
```

## 환경 변수

환경 변수는 프로젝트 루트의 `.env`에서 관리합니다. 현재 연결 확인에는 비밀값이나 `.env`가 필요하지 않습니다.
설정이 필요해지면 `.env.example`을 `.env`로 복사하고 로컬 값을 작성합니다.
`.env`는 Git에서 제외되며, `.env.example`에는 실제 API Key나 비밀번호를 넣지 않습니다.

## 개발 서버 실행

가상환경을 활성화한 상태로 프로젝트 루트에서 실행합니다.

```sh
python -m uvicorn app.main:app --reload
```

`.env`를 생성했다면 다음 명령으로 환경 변수를 함께 불러옵니다.

```sh
python -m uvicorn app.main:app --reload --env-file .env
```

- 기본 응답: <http://127.0.0.1:8000/> → 빌드 결과가 없으면 기존 JSON, 있으면 React 화면
- 상태 확인: <http://127.0.0.1:8000/health> → `{"status":"ok"}`
- API 문서: <http://127.0.0.1:8000/docs>

서버 종료는 `Ctrl+C`를 사용합니다.

## 프론트엔드 개발

Node.js 22 LTS(22.12 이상)와 npm을 사용합니다. `node --version`, `npm --version`으로 확인합니다.
로컬 검증 환경은 Node.js 25.1.0 / npm 11.6.2이며, Railway에서는 Node.js 22를 사용합니다.

백엔드를 8000 포트에서 실행한 상태로 별도 터미널에서 실행합니다.

```sh
cd frontend
npm ci
npm run dev
```

<http://127.0.0.1:5173/>에서 `FastAPI 연결 성공`을 확인합니다.
Vite는 `/api`와 `/health` 요청을 `http://127.0.0.1:8000`으로 전달합니다.
기본 화면은 `fetch`로 `/health`만 호출하며 별도 프론트 환경 변수는 필요하지 않습니다.

## 환경 변수 키

| 키 | 용도 |
| --- | --- |
| `SECRET_KEY` | 인증 구현 시 세션 쿠키 서명용 비밀값 |
| `DATABASE_URL` | DB 구현 시 SQLite 연결 URL, 로컬/배포 경로 구분 |
| `GEMINI_API_KEY` | AI 구현 시 서버에서만 사용하는 API Key |
| `GEMINI_MODEL` | 모델 이름, 기본값 `gemini-3.5-flash-lite` |
| `AI_TIMEOUT` | AI 요청 제한 시간(초), 기본값 `30` |

위 변수는 해당 기능을 구현할 때 사용합니다. 현재 scaffold는 DB 연결, 세션 인증, Gemini 호출을 수행하지 않습니다.
프론트 환경 변수가 필요해지면 `VITE_` 접두사를 사용하되 민감정보를 넣지 않습니다.

## Production 빌드 및 실행

프로젝트 루트에서 실행합니다. 가상환경을 활성화한 상태여야 합니다.

```sh
npm ci --prefix frontend --include=dev
npm run build --prefix frontend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI는 시작 시 `frontend/dist/index.html`이 있으면 빌드 결과를 제공합니다.
빌드 후에는 백엔드를 재시작하고 <http://127.0.0.1:8000/>에서 화면을 확인합니다.
개발 중에는 빌드 여부와 관계없이 Vite의 5173 포트에 접속합니다.

`/health`와 `/api/*`는 React fallback 대상에서 제외됩니다. 아직 구현되지 않은 API는 JSON 404로 응답합니다.
담당 API router는 `app/main.py`의 프론트 정적 파일 mount보다 위에서 등록합니다.
`schemas/`, `routers/`, `services/`와 DB·인증 파일은 해당 기능 구현 시 생성합니다.

## Railway 배포

저장소 루트를 서비스 Root Directory로 사용합니다.
`railpack.json`이 Python 3.14 및 프론트 빌드용 Node.js 22를 준비하며 Python 의존성을 설치합니다.
`railway.json`의 build command가 `npm ci`와 Vite build를 수행한 후,
기존 start command가 `$PORT`를 사용해 FastAPI를 실행합니다.
빌드 결과는 Git에 올리지 않으며, FastAPI가 React 정적 파일을 제공하여 공개 URL 하나로 접근합니다.

팀의 PR 절차로 main에 반영한 뒤 기존 Railway 자동 배포 및 공개 URL의 `/health`를 확인합니다.
현재 scaffold에는 Volume이나 비밀값 설정이 필요하지 않습니다.
DB·인증·AI 구현 단계에서 Railway 환경 변수를 설정하고 SQLite용 Volume `/data`를 연결합니다.
실제 Railway 빌드·배포 성공 여부는 원격 배포 후 별도로 확인해야 합니다.

## Git 협업

- 실제 기능 개발은 develop에서 feature 브랜치를 만들어 진행합니다.
- feature 브랜치 → Pull Request → develop 순서로 병합합니다.
- main은 최종 배포용 브랜치입니다.
- 커밋 메시지는 `<type>: <한글 설명>` 형식을 사용합니다.
