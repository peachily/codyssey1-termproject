import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import Column, Integer, Table, text
from sqlalchemy.orm import sessionmaker

from app import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.url = f"sqlite:///{Path(self.directory.name) / 'test.db'}"

    def make_engine(self, url=None):
        engine = database.build_engine(url or self.url)
        self.addCleanup(engine.dispose)
        return engine

    def test_environment_selects_database_file(self):
        with patch.dict(os.environ, {"DATABASE_URL": self.url}):
            engine = database.build_engine()
        self.addCleanup(engine.dispose)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        self.assertTrue((Path(self.directory.name) / 'test.db').exists())

    def test_blank_environment_uses_local_default(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            engine = database.build_engine()
        self.addCleanup(engine.dispose)
        self.assertEqual(engine.url.database, "./chatbot.db")

    def test_each_connection_enforces_foreign_keys_and_busy_timeout(self):
        engine = self.make_engine()
        with engine.connect() as first, engine.connect() as second:
            for connection in (first, second):
                self.assertEqual(connection.scalar(text("PRAGMA foreign_keys")), 1)
                self.assertEqual(connection.scalar(text("PRAGMA busy_timeout")), 5000)

    def test_reinitialization_preserves_existing_rows(self):
        engine = self.make_engine()
        table = Table("initialization_probe", database.Base.metadata,
                      Column("id", Integer, primary_key=True))
        self.addCleanup(database.Base.metadata.remove, table)
        database.initialize_database(engine)
        with engine.begin() as connection:
            connection.execute(table.insert().values(id=1))
        database.initialize_database(engine)
        with engine.connect() as connection:
            self.assertEqual(connection.scalar(table.select()), 1)

    def test_dependency_returns_connection_after_success_and_error(self):
        engine = self.make_engine()
        factory = sessionmaker(bind=engine)
        for fail in (False, True):
            with self.subTest(fail=fail), patch.object(database, "SessionLocal", factory):
                dependency = database.get_db()
                session = next(dependency)
                session.execute(text("SELECT 1"))
                self.assertEqual(engine.pool.checkedout(), 1)
                if fail:
                    with self.assertRaisesRegex(RuntimeError, "request failed"):
                        dependency.throw(RuntimeError("request failed"))
                else:
                    with self.assertRaises(StopIteration):
                        next(dependency)
                self.assertEqual(engine.pool.checkedout(), 0)


if __name__ == "__main__":
    unittest.main()
