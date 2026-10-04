# 실행 및 배포

## 환경 변수

| 변수 | 용도·설정 |
| --- | --- |
| `SECRET_KEY` | 세션 쿠키 서명용 비밀값 |
| `DATABASE_URL` | 로컬 `sqlite:///./chatbot.db`, Railway `sqlite:////data/chatbot.db` |
| `CODYSSEY_API_KEY` | Codyssey 인증용 virtual key |
| `AI_API_URL` | `https://copa.codyssey.kr/v1/chat/completions` |
| `AI_MODEL` | `gpt-5-mini` |
| `AI_TIMEOUT` | `30`초 |

배포 시 Railway Variables에 설정합니다. 로컬에서는 환경 변수 또는 Git에서 제외되는 `.env`로 관리합니다. 비밀값은 저장소에 포함하지 않습니다.

## 설치 및 실행

Python 3.14, Node.js 22(22.12 이상), npm을 사용합니다. Python 가상환경을 활성화하고 저장소 루트에서 실행합니다.

```sh
python -m pip install -r requirements.txt
npm ci --prefix frontend --include=dev
npm run build --prefix frontend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

로컬 접속은 <http://127.0.0.1:8000/>이며 `.env` 사용 시 실행 명령에 `--env-file .env`를 추가합니다.

## Railway 배포

Railway는 `railway.json`·`railpack.json`에 따라 프론트엔드를 빌드하고 FastAPI를 `$PORT`로 실행합니다. SQLite 영속 저장에는 `/data` Volume을 사용합니다. 서버 상태 확인 경로는 `/health`입니다.

<!-- TODO: 최종 배포 및 데이터 보존 증빙 -->


배포 서비스: [KKAMURUK](https://codyssey1-termproject-production.up.railway.app)

환경 변수 이름은 [`.env.example`](../.env.example)에 제공하며 실제 키와 비밀값은 포함하지 않습니다. `.env`는 [`.gitignore`](../.gitignore)로 추적에서 제외합니다.
