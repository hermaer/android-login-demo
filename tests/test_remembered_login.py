from pathlib import Path
import asyncio
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from database import UserRepository
from remembered_login import EMAIL_KEY, TOKEN_KEY, RememberedLogin


class FakeSecureStorage:
    def __init__(self):
        self.data = {}
        self.fail_writes = False
        self.fail_removes = False

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value):
        if self.fail_writes:
            raise RuntimeError("SecureStorage is unavailable")
        self.data[key] = value

    async def remove(self, key):
        if self.fail_removes:
            raise RuntimeError("Cannot delete")
        self.data.pop(key, None)


class RememberedLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "users.sqlite3"
        self.repo = UserRepository(self.path)
        self.user = self.repo.register("Алексей", "alex@example.com", "password-123")
        self.store = FakeSecureStorage()
        self.auth = RememberedLogin(self.repo, self.store)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_reopen_restores_login_without_password(self):
        self.assertTrue(await self.auth.remember(self.user))
        token = self.store.data[TOKEN_KEY]
        self.assertGreaterEqual(len(token), 40)
        self.assertEqual(self.store.data[EMAIL_KEY], self.user.email)
        with sqlite3.connect(self.path) as db:
            digest = db.execute("SELECT token_hash FROM remembered_sessions").fetchone()[0]
            self.assertEqual(len(digest), 32)
        self.assertNotIn(token.encode(), self.path.read_bytes())
        self.assertNotIn(b"password-123", self.path.read_bytes())
        self.assertEqual(await RememberedLogin(UserRepository(self.path), self.store).restore(),
                         (self.user, self.user.email))

    async def test_logout_revokes_token_and_keeps_email(self):
        await self.auth.remember(self.user)
        token = self.store.data[TOKEN_KEY]
        await self.auth.clear(self.user, keep_email=True)
        self.assertIsNone(self.repo.authenticate_remembered(token))
        self.assertEqual(await self.auth.restore(), (None, self.user.email))

    async def test_logout_revokes_token_even_if_secure_remove_fails(self):
        await self.auth.remember(self.user)
        token = self.store.data[TOKEN_KEY]
        self.store.fail_removes = True
        await self.auth.clear(self.user, keep_email=True)
        self.assertIsNone(self.repo.authenticate_remembered(token))
        self.assertEqual((await self.auth.restore())[0], None)

    async def test_manual_login_without_remember_discards_everything(self):
        await self.auth.remember(self.user)
        await self.auth.clear(self.user, keep_email=False)
        self.assertEqual(self.store.data, {})
        self.assertEqual(await self.auth.restore(), (None, ""))

    async def test_invalid_token_removed(self):
        self.store.data[TOKEN_KEY] = "bad-token-that-is-really-not-valid"
        self.store.data[EMAIL_KEY] = self.user.email
        self.assertEqual(await self.auth.restore(), (None, self.user.email))
        self.assertNotIn(TOKEN_KEY, self.store.data)

    async def test_expired_token_cannot_log_in(self):
        await self.auth.remember(self.user)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE remembered_sessions SET expires_at=?", (int(time.time()) - 1,))
        self.assertEqual(await self.auth.restore(), (None, self.user.email))
        self.assertNotIn(TOKEN_KEY, self.store.data)

    async def test_secure_storage_failure_does_not_remember_user(self):
        self.store.fail_writes = True
        self.assertFalse(await self.auth.remember(self.user))
        self.assertEqual((await self.auth.restore())[0], None)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM remembered_sessions").fetchone()[0], 0)

    async def test_old_database_migrates_without_destroying_accounts(self):
        legacy_path = Path(self.tmp.name) / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as db:
            db.execute("""CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
        migrated = UserRepository(legacy_path)
        user = migrated.register("Ирина", "irina@example.com", "secret-password")
        self.assertEqual(migrated.authenticate("irina@example.com", "secret-password"), user)
        token = migrated.issue_remembered_token(user.id)
        self.assertEqual(migrated.authenticate_remembered(token), user)

    async def test_token_rotation(self):
        self.assertTrue(await self.auth.remember(self.user))
        old_token = self.store.data[TOKEN_KEY]
        self.assertTrue(await self.auth.remember(self.user))
        self.assertNotEqual(old_token, self.store.data[TOKEN_KEY])
        self.assertIsNone(self.repo.authenticate_remembered(old_token))

    async def test_unknown_user_cannot_get_token(self):
        with self.assertRaises(ValueError):
            self.repo.issue_remembered_token(990000)

if __name__ == "__main__":
    unittest.main()
