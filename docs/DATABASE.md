# 데이터베이스 구조

## ERD

<!-- TODO: 최종 ERD -->

## users

| 필드명 | 타입 | 제약조건 |
| --- | --- | --- |
| `id` | | |
| `username` | | |
| `password_hash` | | |
| `created_at` | | |

## chats

| 필드명 | 타입 | 제약조건 |
| --- | --- | --- |
| `id` | | |
| `user_id` | | |
| `question` | | |
| `answer` | | |
| `created_at` | | |

## 테이블 관계

`users`와 `chats`는 1:N 관계이며, `chats.user_id`는 `users.id`를 참조합니다.

## DB 저장 내용 확인 방법

<!-- TODO: 최종 DB 확인 방법 및 실행 예시 -->
