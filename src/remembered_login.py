"""Persist a *revocable login token*, not a user's password.

Only the opaque random token is stored in Flet SecureStorage (Android Keystore);
SQLite contains its SHA-256 digest. This is local-only prototype auth, NOT a
server token and NOT multi-device authentication.
"""
from __future__ import annotations

from database import User, UserRepository

TOKEN_KEY = "com.example.simplecabinet.remember.token.v1"
EMAIL_KEY = "com.example.simplecabinet.remember.email.v1"


class RememberedLogin:
    def __init__(self, repository: UserRepository, secure_storage):
        self.repository = repository
        self.secure_storage = secure_storage

    async def restore(self) -> tuple[User | None, str]:
        """Restore saved account if the local token is valid and not expired."""
        try:
            email = await self.secure_storage.get(EMAIL_KEY) or ""
            token = await self.secure_storage.get(TOKEN_KEY)
        except Exception:
            # Keystore inaccessible, e.g. data restored to another handset.
            # Never bypass authentication when secure storage cannot be read.
            return None, ""

        if not token:
            return None, email

        user = self.repository.authenticate_remembered(token)
        if user is None:
            try:
                await self.secure_storage.remove(TOKEN_KEY)
            except Exception:
                pass
            return None, email
        return user, user.email

    async def remember(self, user: User) -> bool:
        """Keep the login across restarts; False on secure storage failures."""
        token = self.repository.issue_remembered_token(user.id)
        try:
            await self.secure_storage.set(TOKEN_KEY, token)
            await self.secure_storage.set(EMAIL_KEY, user.email)
        except Exception:
            self.repository.revoke_user_remembered_tokens(user.id)
            try:
                await self.secure_storage.remove(TOKEN_KEY)
            except Exception:
                pass
            return False
        return True

    async def clear(self, user: User | None, *, keep_email: bool) -> None:
        """Invalidate DB token first: logout remains effective if Keystore fails."""
        if user is not None:
            self.repository.revoke_user_remembered_tokens(user.id)
        try:
            token = await self.secure_storage.get(TOKEN_KEY)
            if token:
                self.repository.revoke_remembered_token(token)
        except Exception:
            pass
        try:
            await self.secure_storage.remove(TOKEN_KEY)
        except Exception:
            pass
        if not keep_email:
            try:
                await self.secure_storage.remove(EMAIL_KEY)
            except Exception:
                pass
