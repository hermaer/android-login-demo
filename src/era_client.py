"""HTTPS client for the ERA site's existing SQLAlchemy DB via mobile API.

Android NEVER connects directly to PostgreSQL. Only the FastAPI server can
read/write the database. Raw passwords and bearer tokens are never logged.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class ERAError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


@dataclass
class ERAClient:
    base_url: str

    def __post_init__(self):
        self.base_url = self.base_url.strip().rstrip("/")
        if not self.base_url:
            raise ERAError("Укажите HTTPS-адрес сайта ЭРА в src/era_config.py")
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")
        ):
            raise ERAError("Для мобильного приложения необходим HTTPS-адрес ЭРА")
        if not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/"):
            raise ERAError("В ERA_BASE_URL укажите только адрес сайта без пути")

    def request(self, method: str, path: str, token: str | None = None,
                payload: dict | None = None, query: dict | None = None):
        if not path.startswith("/api/mobile/v1/"):
            raise ERAError("Недопустимый API-путь")
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read(1024 * 1024).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise ERAError("Неверный логин/пароль или истёк сеанс", 401) from exc
            if exc.code == 404:
                raise ERAError("API не найден. Проверьте обновление сервера ЭРА", 404) from exc
            if exc.code == 429:
                raise ERAError("Слишком много попыток. Повторите позже", 429) from exc
            raise ERAError(f"Ошибка сервера ЭРА (HTTP {exc.code})", exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ERAError("Не удалось подключиться к серверу ЭРА. Проверьте адрес, HTTPS и интернет") from exc

    def login(self, username: str, password: str, remember: bool) -> dict:
        return self.request("POST", "/api/mobile/v1/auth/login", payload={
            "username": username, "password": password, "remember_me": remember
        })

    def me(self, token: str) -> dict:
        return self.request("GET", "/api/mobile/v1/me", token)

    def logout(self, token: str) -> dict:
        return self.request("POST", "/api/mobile/v1/auth/logout", token)

    def users(self, token: str) -> list[dict]:
        return self.request("GET", "/api/mobile/v1/users", token)

    def chats(self, token: str) -> list[dict]:
        return self.request("GET", "/api/mobile/v1/chats", token)

    def messages(self, token: str, user_id: int, after_id: int = 0) -> list[dict]:
        return self.request("GET", f"/api/mobile/v1/chats/{user_id}/messages",
                            token, query={"after_id": after_id})

    def send(self, token: str, user_id: int, text: str) -> dict:
        return self.request("POST", f"/api/mobile/v1/chats/{user_id}/messages", token,
                            payload={"text": text})

    def read(self, token: str, user_id: int) -> dict:
        return self.request("POST", f"/api/mobile/v1/chats/{user_id}/read", token)
