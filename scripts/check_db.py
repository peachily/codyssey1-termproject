"""Read a user's chat records without creating or modifying a database."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description="DB 대화 기록 읽기 전용 확인")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--user-id", required=True, type=int)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.user_id < 1 or args.limit < 1:
        parser.error("user-id와 limit는 양수여야 합니다")
    uri = args.database.resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id, user_id, question, answer, created_at FROM chats "
                "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (args.user_id, args.limit),
            ).fetchall()
    except sqlite3.Error:
        parser.error("DB 파일 경로·접근 권한·스키마를 확인하세요")
    print(json.dumps([dict(row) for row in rows], ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
