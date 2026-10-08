# 실행·환경 변수·배포

로컬 개발과 Railway 배포의 설정·실행 방법을 설명합니다. 비밀값은 환경에만 저장하고, 실패 상황은 서버 로그와 HTTP 응답으로 확인합니다.

## 개발 환경 준비

Python 3.14, Node.js 22.12 이상인 22 버전 또는 24 이상, npm을 사용합니다. Railway 설정은 Python 3.14와 Node.js 22입니다. Python 의존성은 `requirements.txt`, 프론트 의존성은 `frontend/package.json` 및 `package-lock.json`에 고정되어 있습니다.

저장소를 내려받은 뒤 **저장소 루트**에서 가상환경을 만듭니다.

macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`의 빈 필수값을 자신의 로컬 설정으로 채운 뒤 서버를 시작합니다. 실제 키나 비밀번호는 문서·커밋·로그에 붙여 넣지 않습니다.

## 환경 변수

설정은 `app/config.py`와 `app/database.py`에서 읽습니다. `.env`를 코드가 자동으로 읽지 않으므로 Uvicorn의 `--env-file .env` 또는 프로세스 환경 변수로 전달합니다.

| 이름 | 필수 여부 | 기본값·설정 |
| --- | --- | --- |
| `SECRET_KEY` | 서버 시작에 필수 | 기본값 없음. 비어 있거나 공백만 있으면 시작 실패. 세션 서명용 비밀값 |
| `CODYSSEY_API_KEY` | AI 대화·처방에 필수 | 누락이어도 서버 시작 가능. AI 요청 시 502 |
| `DATABASE_URL` | 선택 | 미설정·빈 값이면 `sqlite:///./chatbot.db` |
| `SESSION_HTTPS_ONLY` | 선택 | 미설정·빈 값은 false. 로컬 HTTP는 false, Railway HTTPS는 true |
| `AI_API_URL` | 선택 | 미설정·공백이면 `https://copa.codyssey.kr/v1/chat/completions` |
| `AI_MODEL` | 선택 | 미설정·공백이면 `gpt-5.4` |
| `AI_TIMEOUT` | 선택 | 미설정·공백이면 30초. 양의 유한 숫자를 사용하며 잘못된 값은 경고 후 30초 |
| `PORT` | Railway 실행 시 사용 | Railway가 제공하며 시작 명령에 사용. 로컬은 명시적 8000 사용 |

`SESSION_HTTPS_ONLY`는 대소문자·앞뒤 공백을 정규화한 `true` 또는 `false`만 허용합니다. 다른 값은 시작 실패입니다. `SECRET_KEY`를 변경하면 기존 서명 쿠키는 유효하지 않게 됩니다. 세션 쿠키는 HttpOnly, SameSite=lax, 14일 수명을 사용합니다.

아래는 값 입력 전 예시이며 실제 키가 아닙니다. `SECRET_KEY`, `CODYSSEY_API_KEY`는 실행 환경에서 채워야 합니다.

```dotenv
SECRET_KEY=
SESSION_HTTPS_ONLY=false
DATABASE_URL=sqlite:///./chatbot.db
CODYSSEY_API_KEY=
AI_API_URL=https://copa.codyssey.kr/v1/chat/completions
AI_MODEL=gpt-5.4
AI_TIMEOUT=30
```

현재 프론트는 같은 호스트의 `/api`를 사용하며 `VITE_API_BASE_URL`을 읽지 않습니다. `VITE_` 변수는 번들에 노출될 수 있으므로 비밀값을 넣지 않습니다.

## 백엔드 개발 실행

가상환경을 활성화하고 `.env`를 작성한 뒤 **저장소 루트**에서:

```sh
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --reload
```

DB의 없는 테이블은 시작 시 생성됩니다. `create_all()`은 기존 컬럼을 마이그레이션하지 않으므로 구조 변경에는 별도의 백업·마이그레이션이 필요합니다. DB 상위 디렉터리는 먼저 존재해야 하며 쓰기 권한이 있어야 합니다.

다른 터미널에서 **저장소 루트** 기준 헬스체크:

```sh
curl http://127.0.0.1:8000/health
```

예상 응답은 `{"status":"ok"}`입니다. 이는 서버 응답 확인이며 외부 AI 인증·DB 영속성을 모두 검사하는 기능은 아닙니다.

## 프론트엔드 개발 실행

다른 터미널의 **저장소 루트**에서:

```sh
npm ci --prefix frontend --include=dev
npm run dev --prefix frontend
```

브라우저에서 <http://127.0.0.1:5173>에 접속합니다. Vite는 `/api`, `/health`를 `http://127.0.0.1:8000`으로 프록시합니다. 백엔드도 함께 실행해야 합니다. 로그인 확인 시 같은 호스트 표기를 유지합니다.

## 빌드 결과를 FastAPI로 제공

**저장소 루트**에서:

```sh
npm run build --prefix frontend
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

<http://127.0.0.1:8000>으로 접속합니다. 프론트 빌드 존재 여부는 FastAPI 모듈 로딩 시 감지하므로 **빌드 후 서버를 재시작**합니다. 실행 중인 서버가 있으면 먼저 종료합니다. 빌드가 없으면 `/`는 기본 JSON 응답을 반환합니다.

## Railway 배포 구조

[railway.json](../railway.json), [railpack.json](../railpack.json)에 따라 Python 서비스와 Node.js 빌드 환경을 구성합니다.

| 항목 | 설정 |
| --- | --- |
| 빌드 | `npm ci --prefix frontend --include=dev && npm run build --prefix frontend` |
| 시작 | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| DB 영속 경로 | Volume `/data`, `DATABASE_URL=sqlite:////data/chatbot.db` |
| 쿠키 | `SESSION_HTTPS_ONLY=true` |
| 상태 확인 경로 | `/health` |

Railway 서비스 Variables에서 필수 키와 위 배포값을 설정합니다. Volume을 `/data`에 마운트하고 읽기·쓰기 권한을 확인합니다. 환경 변수나 DB 파일을 프론트 번들에 넣지 않습니다.

팀의 배포 운영 기준은 `main` 반영 시 자동 배포입니다. 저장소 연결·배포 브랜치·Volume·Variables는 Railway 서비스 설정에서 확인해야 하며 JSON 파일만으로 설정 완료를 증명할 수 없습니다. 현재 `railway.json`은 별도 healthcheckPath를 지정하지 않으므로 플랫폼 헬스체크를 설정할 때 `/health`를 사용합니다.

서비스 URL: [까무룩](https://codyssey1-termproject-production.up.railway.app)

배포 확인 순서:

1. 공개 URL과 `/health` 응답 확인
2. 테스트 계정 가입·로그인·질문·응답 및 DB 저장 확인
3. 로그아웃 뒤 보호 API 접근 차단 확인
4. 재배포 후 같은 계정으로 재로그인하여 이전 기록 보존 확인
5. [DB 검증](DATABASE.md)의 사용자별 SELECT로 Volume 데이터 확인

문서 작성 환경에서는 운영 서비스 재배포·Volume 검증을 실행하지 않았습니다. 사용자가 확인한 외부 서비스 동작과 자동화 테스트 결과는 별개로 관리합니다.

## 로그 확인

로컬에서는 Uvicorn을 실행한 터미널에서, Railway에서는 해당 배포의 서비스 로그에서 확인합니다. 별도의 로그 파일 저장 기능은 구현되어 있지 않습니다.

성공 흐름의 이벤트 순서는 `request_received` → `ai_call_start` → `ai_call_success` → `db_save_success`입니다. AI 실패 시 `ai_call_failure`, 저장 실패 시 `db_save_failure`를 확인합니다. request_id로 요청·AI 로그를, user_id로 관련 저장 로그를 연결합니다. 위치별 상세는 [시스템 구조](ARCHITECTURE.md#검증오류로그)를 참조합니다.

## 오류 처리와 점검

| 상황 | 서버 동작·응답 | 대화 화면 안내 | 점검 |
| --- | --- | --- | --- |
| AI 키 누락 | 서버 시작 가능, 질문 시 502 `AI request failed`, 로그 reason=missing_api_key, 미저장 | 약방 주인이 답변을 받지 못했어요. 잠시 후 다시 시도해주세요. | 서버 환경의 CODYSSEY_API_KEY 및 env-file 적용 |
| AI timeout | 504 `AI response timed out`, 미저장, 서버 유지 | 답변이 늦어지고 있어요. 잠시 후 다시 시도해주세요. | 외부 응답 지연·AI_TIMEOUT |
| AI 연결·HTTP·응답 형식 실패 | 502 `AI request failed`, 미저장 | 약방 주인이 답변을 받지 못했어요. 잠시 후 다시 시도해주세요. | 네트워크·URL·인증·모델·외부 응답 |
| 대화 commit 실패 | rollback, db_save_failure, 500 `Failed to save chat` | 대화를 저장하지 못했어요. 잠시 후 다시 시도해주세요. | DB 경로·권한·공간·잠금 |
| 세션 만료·미인증 | 401 `Not authenticated` | 로그인이 만료됐어요. 다시 로그인해주세요. | 쿠키·호스트·HTTPS 정책·SECRET_KEY 변경 |
| message 검증 실패 | 400 `Invalid message` | 입력 내용을 확인해주세요. 이야기는 1~2000자로 보내주세요. | trim 후 1~2000자 문자열 |
| SECRET_KEY 누락·쿠키 설정 오류 | 서버 시작 실패 | API 연결 실패 안내 | 필수 설정과 true/false 값 |
| 기록 조회 실패 | PR #59: 500 `Failed to retrieve chats` | PR #59: 지난 이야기를 불러오지 못했어요. 잠시 후 다시 시도해주세요. | 기록 API는 develop 병합 후 사용 |

처방 화면도 별도 상태코드별 안내를 제공하며 Python traceback이나 내부 설정값을 표시하지 않습니다. DB 사용자 조회 실패는 `auth_lookup_failure`와 500 `Failed to retrieve user`로 처리합니다. AI 키·세션 비밀값·비밀번호·DB 오류 원문은 로그에 넣지 않습니다.

## 민감정보 관리

[.env.example](../.env.example)은 변수 이름·목적만 공유합니다. [.gitignore](../.gitignore)는 `.env`, `.env.*`(예시 제외), DB 파일, 로그, 가상환경, node_modules, dist를 제외합니다. 비밀값은 로컬 `.env` 또는 Railway Variables에만 설정합니다. 테스트 증빙은 테스트 계정을 사용하고 실제 개인정보·쿠키·해시를 첨부하지 않습니다.

[테스트 실행 및 결과](TESTING.md) · [개발 규칙](DEVELOPMENT.md)
