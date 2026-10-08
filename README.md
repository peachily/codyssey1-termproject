<p align="center">
  <a href="https://codyssey1-termproject-production.up.railway.app">
    <img src="frontend/src/assets/backgrounds/shop-exterior.webp" width="600" alt="약방에 들어가기" />
  </a>
</p>

<h1 align="center">까무룩 · KKAMURUK</h1>

<p align="center">
  까무룩 잠들고 싶은 밤,<br />
  짧은 이야기와 마법약 한 병의 위로.
</p>

<p align="center">
  <a href="https://codyssey1-termproject-production.up.railway.app">약방에 들어가기</a>
</p>

## 프로젝트 소개

하루가 끝났는데도 생각이 멈추지 않는 밤이 있습니다.

까무룩은 잠들기 어려운 밤, 약방 주인에게 마음을 털어놓고 마법약과 짧은 위로를 받는 웹 서비스입니다. 잘 정리된 말이 아니어도 괜찮아요. 오늘 마음에 남은 이야기부터 들려주세요.

## 약방 이용 방법

처음 방문했다면 아이디와 비밀번호로 가입한 뒤 로그인해 주세요.

### 잠들기 전 짧은 위로

<p align="center">
  <img src="frontend/src/assets/owl/owl-open.webp" width="140" alt="약방의 올빼미 주인" />
</p>

약방 주인에게 오늘 마음에 남은 이야기를 건네보세요. 답변을 읽고 조금 더 이야기를 나누며, 오늘의 마음에 맞는 따뜻한 한마디를 받아보세요.

### 숙면을 도와줄 마법약

대화를 나눈 뒤 **마법약 처방받기**를 눌러보세요. 대화에 담긴 마음을 다섯 가지 색의 마법약과 짧은 위로의 말로 전해드립니다.

<p align="center">
  <img src="frontend/src/assets/potions/potion-bottle.webp" width="140" alt="마법약 병" />
</p>

| 마법약 색 | 대화에 담긴 마음 |
| --- | --- |
| $\textcolor{#718da6}{\text{파랑}}$ | 아직 일어나지 않은 일에 대한 걱정과 불안 |
| $\textcolor{#927da1}{\text{보라}}$ | 슬픔과 가라앉은 기분 |
| $\textcolor{#c79aa8}{\text{분홍}}$ | 외로움과 누군가 곁에 있어 주길 바라는 마음 |
| $\textcolor{#829f8c}{\text{초록}}$ | 일과 사람, 마감에서 오는 압박감 |
| $\textcolor{#d1b974}{\text{노랑}}$ | 기운이 바닥난 듯한 지침과 무기력 |

### 다시 펼치는 지난 이야기

지난 대화가 궁금하다면 상단 **나가기 왼쪽의 달력 아이콘**을 눌러보세요. 날짜를 골라 그날 나눈 이야기를 다시 읽을 수 있어요.

---

## 프로젝트 문서

| 문서 | 내용 |
| --- | --- |
| [시스템 구성](docs/ARCHITECTURE.md) | 아키텍처·주요 컴포넌트·처리 흐름 |
| [API 명세](docs/API.md) | 요청·응답 예시와 오류 응답 |
| [데이터베이스](docs/DATABASE.md) | ERD·테이블·사용자별 기록 확인 SQL 및 실행 방법 |
| [실행 및 배포](docs/DEPLOYMENT.md) | 설치·환경 변수·배포·민감정보 관리 |
| [팀 소개](docs/TEAM.md) | 역할 분담·개인별 작업 요약 |
| [과제 요구사항 검증](docs/TESTING.md) | 구현 근거·확인 방법·제출 자료 |
| [개발 기준](docs/DEVELOPMENT.md) | 기술 계약·브랜치·PR·리뷰 규칙 |

---

## 환경 변수 및 설정 방법

### 환경 변수

| 이름 | 용도 | 설정 기준 |
| --- | --- | --- |
| `SECRET_KEY` | 세션 쿠키 서명 | 필수 |
| `CODYSSEY_API_KEY` | 서버의 AI API 호출 | 대화·처방 이용 시 필수 |
| `SESSION_HTTPS_ONLY` | HTTPS 전용 쿠키 | 로컬 HTTP는 false, 배포 HTTPS는 true |
| `DATABASE_URL` | DB 연결 경로 | 로컬·배포 환경에 맞게 설정 |
| `AI_API_URL` | AI API 주소 | 선택, 기본값 사용 가능 |
| `AI_MODEL` | AI 모델 | 선택, 기본값 사용 가능 |
| `AI_TIMEOUT` | AI 요청 제한 시간 | 선택, 기본 30초 |
| `PORT` | 배포 서버 포트 | Railway에서 제공 |

### 설정 순서

1. 저장소 루트의 [.env.example](.env.example)을 `.env`로 복사합니다.
2. `SECRET_KEY`와 `CODYSSEY_API_KEY`를 입력하고, 나머지 변수는 실행 환경에 맞게 설정합니다.
3. 로컬 백엔드 실행 시 `--env-file .env`로 설정을 전달합니다. Railway에서는 서비스 **Variables**에 등록합니다.

- 실제 비밀값은 공유하지 않습니다. `.env`는 [.gitignore](.gitignore)로 업로드에서 제외합니다.
- 기본값과 설치·실행 명령은 [실행 및 환경 설정](docs/DEPLOYMENT.md)에 안내되어 있습니다.
