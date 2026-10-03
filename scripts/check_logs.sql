-- sqlite3 CLI에서 sqlite3 -readonly chatbot.db 실행 후 사용합니다.
-- user_id 1은 확인할 테스트 계정 ID로 변경합니다. 아래 문장은 조회만 수행합니다.
PRAGMA table_info(users);
PRAGMA table_info(chats);
PRAGMA foreign_key_list(chats);
PRAGMA index_list(chats);

SELECT id, user_id, created_at, question, answer
FROM chats
WHERE user_id = 1
ORDER BY created_at DESC, id DESC
LIMIT 20;

EXPLAIN QUERY PLAN
SELECT id, user_id, created_at, question, answer
FROM chats
WHERE user_id = 1
ORDER BY created_at DESC, id DESC
LIMIT 5;
