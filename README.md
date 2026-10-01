# Codyssey 1 Term Project

Python + FastAPI 기반 웹 AI 챗봇 서비스의 초기 개발 저장소입니다.
현재는 기본 앱과 `GET /`, `GET /health` 엔드포인트만 제공합니다.

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

환경 변수는 프로젝트 루트의 `.env`에서 관리합니다. 현재 필수 변수는 없습니다.
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

- 기본 응답: <http://127.0.0.1:8000/> → `{"message":"Hello, Codyssey!"}`
- 상태 확인: <http://127.0.0.1:8000/health> → `{"status":"ok"}`
- API 문서: <http://127.0.0.1:8000/docs>

서버 종료는 `Ctrl+C`를 사용합니다.
