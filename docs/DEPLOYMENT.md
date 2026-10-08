# 실행 및 배포

로컬 실행, 환경 변수와 Railway 배포 방법을 정리합니다.

## 준비

- Python 3.14, Node.js 22.12 이상인 22 버전 또는 24 이상, npm.
- 아래 명령은 **저장소 루트** 기준.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
npm ci --prefix frontend --include=dev
```

Windows PowerShell에서는 `py -m venv .venv`, `.\.venv\Scripts\Activate.ps1`, `Copy-Item .env.example .env`를 사용합니다.

## 환경 변수

| 이름 | 기본값·설정 |
| --- | --- |
| `SECRET_KEY` | 필수, 세션 서명용 비밀값 |
| `CODYSSEY_API_KEY` | AI 호출에 필수. 누락 시 해당 요청 502 |
| `DATABASE_URL` | `sqlite:///./chatbot.db` |
| `SESSION_HTTPS_ONLY` | false. Railway HTTPS에서는 true |
| `AI_API_URL` | `https://copa.codyssey.kr/v1/chat/completions` |
| `AI_MODEL` | `gpt-5.4` |
| `AI_TIMEOUT` | 30초. 양의 유한 숫자 |
| `PORT` | Railway 제공 |

- [.env.example](../.env.example)을 복사한 `.env`에 값 입력.
- `.env`는 자동 로딩되지 않으므로 실행 시 `--env-file .env` 지정.
- DB 초기화는 서버 시작 시 수행. 기존 스키마 변경은 별도 마이그레이션 필요.

## 로컬 실행

터미널 1 — 백엔드:

```sh
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --reload
```

터미널 2 — 프론트:

```sh
npm run dev --prefix frontend
```

- 접속: <http://127.0.0.1:5173>
- Vite가 `/api`, `/health`를 백엔드 8000 포트로 전달.
- 상태 확인: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.

빌드 화면을 FastAPI에서 제공하려면 기존 서버 종료 후:

```sh
npm run build --prefix frontend
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

접속: <http://127.0.0.1:8000>. 빌드 변경 후 서버 재시작 필요.

## Railway 배포 구조

| 항목 | 설정 |
| --- | --- |
| 배포 브랜치 | main |
| 빌드 | `npm ci --prefix frontend --include=dev && npm run build --prefix frontend` |
| 시작 | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Volume | `/data` |
| DATABASE_URL | `sqlite:////data/chatbot.db` |
| SESSION_HTTPS_ONLY | true |
| 비밀값 | 서비스 Variables에 등록 |
| 상태 확인 | `/health` (플랫폼 healthcheckPath는 별도 설정) |

- 설정 파일: [railway.json](../railway.json), [railpack.json](../railpack.json).
- 공개 URL: [서비스 접속](https://codyssey1-termproject-production.up.railway.app).
- 배포 확인: 접속 → 로그인·질문 → 로그아웃 → 재배포 후 기록 보존.

## 오류 처리와 점검

| 상황 | 서버 | 화면 안내 요약 | 확인 |
| --- | --- | --- | --- |
| AI 키 누락·호출 실패 | 502, 대화 미저장 | 답변을 받지 못했어요 | 키·URL·연결 |
| AI timeout | 504, 대화 미저장 | 답변이 늦어지고 있어요 | AI_TIMEOUT·응답 지연 |
| DB 저장 실패 | 500, rollback | 대화를 저장하지 못했어요 | 경로·권한·공간 |
| 기록 조회 실패 | 500, rollback | 지난 이야기를 불러오지 못했어요 | DB 연결·재조회 |
| 세션 만료 | 401 | 다시 로그인해주세요 | 쿠키·HTTPS 설정 |
| 입력 오류 | 400 | 입력 내용을 확인해주세요 | 타입·길이 |
| SECRET_KEY 누락 | 시작 실패 | 서버 연결 불가 | 필수 설정 |

- 로그 위치: 로컬 실행 터미널 / Railway 서비스 로그.
- 핵심 이벤트: [시스템 구조](ARCHITECTURE.md#검증오류로그).

## 민감정보 관리

- 실제 비밀값: `.env` 또는 Railway Variables에만 저장.
- [.gitignore](../.gitignore): `.env`·DB·로그·빌드 결과 제외.
- 프론트 `VITE_` 변수에 비밀값 금지. 현재 API는 같은 호스트의 `/api` 사용.
