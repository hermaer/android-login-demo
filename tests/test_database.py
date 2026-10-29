from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from database import UserRepository


class UserRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "users.sqlite3"
        self.repo = UserRepository(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_registration_authentication_and_restart(self):
        user = self.repo.register("  Иван   Иванов  ", "IVAN@example.com", "secure-password-123")
        self.assertEqual(user.name, "Иван Иванов")
        self.assertEqual(user.email, "ivan@example.com")
        self.assertTrue(self.path.is_file())
        repo_after_restart = UserRepository(self.path)
        self.assertEqual(repo_after_restart.authenticate("ivan@EXAMPLE.com", "secure-password-123"), user)
        self.assertIsNone(repo_after_restart.authenticate("ivan@example.com", "wrong"))

    def test_duplicate_email_case_insensitive(self):
        self.repo.register("First", "mail@example.com", "12345678")
        with self.assertRaisesRegex(ValueError, "уже зарегистрирован"):
            self.repo.register("Second", "MAIL@EXAMPLE.com", "12345678")

    def test_invalid_input(self):
        with self.assertRaisesRegex(ValueError, "почты"):
            self.repo.register("Anna", "not-an-email", "12345678")
        with self.assertRaisesRegex(ValueError, "Пароль"):
            self.repo.register("Anna", "anna@example.com", "123")
        with self.assertRaisesRegex(ValueError, "Имя"):
            self.repo.register("X", "x@example.com", "12345678")

    def test_password_not_in_plain_text(self):
        self.repo.register("Test", "test@example.com", "secret-password-123")
        with sqlite3.connect(self.path) as db:
            salt, digest = db.execute("SELECT password_salt, password_hash FROM users").fetchone()
        self.assertEqual(len(salt), 16)
        self.assertEqual(len(digest), 32)
        self.assertNotIn(b"secret-password-123", self.path.read_bytes())

    def test_sql_injection_does_not_work(self):
        self.repo.register("Test", "test@example.com", "secret-password-123")
        self.assertIsNone(self.repo.authenticate("' OR 1=1 --", "secret-password-123"))


if __name__ == "__main__":
    unittest.main()
