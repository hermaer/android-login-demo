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
            try:
                detail = json.loads(exc.read(4096).decode('utf-8')).get('detail', '')
                if isinstance(detail, str) and len(detail) < 300:
                    raise ERAError(detail, exc.code) from exc
            except (ValueError, UnicodeError, AttributeError):
                pass
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

    def messages(self, token: str, user_id: int, after_id: int = 0, limit: int = 80) -> list[dict]:
        return self.request("GET", f"/api/mobile/v1/chats/{user_id}/messages",
                            token, query={"after_id": after_id, "limit": int(limit)})

    def send(self, token: str, user_id: int, text: str) -> dict:
        return self.request("POST", f"/api/mobile/v1/chats/{user_id}/messages", token,
                            payload={"text": text})

    def read(self, token: str, user_id: int) -> dict:
        return self.request("POST", f"/api/mobile/v1/chats/{user_id}/read", token)

    # ERA v0.6: all API calls go to the SAME website database.
    def capabilities(self, token):
        return self.request('GET', '/api/mobile/v1/capabilities', token)

    def dashboard(self, token):
        return self.request('GET', '/api/mobile/v1/dashboard', token)

    def profile(self, token):
        return self.request('GET', '/api/mobile/v1/profile', token)

    def edit_profile(self, token, email, phone, about):
        return self.request('PATCH', '/api/mobile/v1/profile', token,
                            payload={'email': email, 'phone': phone, 'about': about})

    def change_password(self, token, old, new):
        return self.request('POST', '/api/mobile/v1/profile/password', token,
                            payload={'current_password': old, 'new_password': new})

    def news(self, token, skip=0):
        return self.request('GET', '/api/mobile/v1/news', token, query={'skip': skip, 'limit': 20})

    def news_item(self, token, news_id):
        return self.request('GET', f'/api/mobile/v1/news/{int(news_id)}', token)

    def news_like(self, token, news_id):
        return self.request('POST', f'/api/mobile/v1/news/{int(news_id)}/like', token)

    def news_comment(self, token, news_id, content):
        return self.request('POST', f'/api/mobile/v1/news/{int(news_id)}/comments', token,
                            payload={'text': content})

    def calendar(self, token):
        return self.request('GET', '/api/mobile/v1/calendar', token)

    def calendar_create(self, token, title, desc, when, kind, yearly):
        return self.request('POST', '/api/mobile/v1/calendar', token,
                            payload={'title': title, 'description': desc, 'event_date': when,
                                     'event_type': kind, 'repeat_yearly': yearly})

    def calendar_delete(self, token, event_id):
        return self.request('DELETE', f'/api/mobile/v1/calendar/{int(event_id)}', token)

    def expense_categories(self, token):
        return self.request('GET', '/api/mobile/v1/expenses/categories', token)

    def expense_category_create(self, token, name):
        return self.request('POST', '/api/mobile/v1/expenses/categories', token, payload={'name': name})

    def expenses(self, token):
        return self.request('GET', '/api/mobile/v1/expenses', token)

    def expense_summary(self, token):
        return self.request('GET', '/api/mobile/v1/expenses/summary', token)

    def expense_create(self, token, amount, cat_id, desc, day):
        return self.request('POST', '/api/mobile/v1/expenses', token,
                            payload={'amount': amount, 'category_id': int(cat_id),
                                     'description': desc, 'expense_date': day})

    def expense_delete(self, token, expense_id):
        return self.request('DELETE', f'/api/mobile/v1/expenses/{int(expense_id)}', token)

    def shop(self, token, category_id=None, sort=''):
        q = {'sort': sort}
        if category_id is not None:
            q['category_id'] = int(category_id)
        return self.request('GET', '/api/mobile/v1/shop', token, query=q)

    def inventory(self, token):
        return self.request('GET', '/api/mobile/v1/shop/inventory', token)

    def buy(self, token, item_id):
        return self.request('POST', f'/api/mobile/v1/shop/{int(item_id)}/buy', token)

    def feed(self, token, category='', keyword=''):
        return self.request('GET', '/api/mobile/v1/feed', token,
                            query={'category': category, 'keyword': keyword})

    def admin_news_create(self, token, title, content, pinned):
        return self.request('POST', '/api/mobile/v1/admin/news', token,
                            payload={'title': title, 'content': content, 'pinned': pinned})

    def admin_news_edit(self, token, news_id, title, content, pinned):
        return self.request('PATCH', f'/api/mobile/v1/admin/news/{int(news_id)}', token,
                            payload={'title': title, 'content': content, 'pinned': pinned})

    def admin_news_delete(self, token, news_id):
        return self.request('DELETE', f'/api/mobile/v1/admin/news/{int(news_id)}', token)

    def upload_file(self, token: str, path: str, filename: str, content: bytes) -> dict:
        """Upload one selected mobile file via authenticated HTTPS multipart POST."""
        import secrets
        import os
        if not (path == '/api/mobile/v1/profile/avatar' or
                (path.startswith('/api/mobile/v1/chats/') and path.endswith('/attachments'))):
            raise ERAError('Запрещённый путь загрузки')
        if not isinstance(content, bytes) or not content or len(content) > 15 * 1024 * 1024:
            raise ERAError('Файл пуст или слишком большой')
        safe_name = os.path.basename(filename.replace('\\', '/'))
        if not safe_name or len(safe_name) > 150:
            raise ERAError('Некорректное имя файла')
        boundary = 'EraMobile_' + secrets.token_hex(16)
        safe_name = ''.join(c if c.isascii() and (c.isalnum() or c in '._-') else '_'
                            for c in safe_name)
        before = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
                  'Content-Type: application/octet-stream\r\n\r\n').encode('ascii')
        body = before + content + f'\r\n--{boundary}--\r\n'.encode('ascii')
        req = urllib.request.Request(self.base_url + path, data=body,
            headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json',
                     'Content-Type': 'multipart/form-data; boundary=' + boundary}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read(1024 * 1024).decode('utf-8'))
        except urllib.error.HTTPError as exc:
            try:
                data = json.loads(exc.read(4096).decode('utf-8'))
                detail = data.get('detail', '')
                if isinstance(detail, str): raise ERAError(detail[:300], exc.code) from exc
            except (ValueError, UnicodeError, AttributeError):
                pass
            raise ERAError(f'Не удалось загрузить файл (HTTP {exc.code})', exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ERAError('Нет соединения с ЭРА во время загрузки файла') from exc

    def fonts(self, token):
        return self.request('GET', '/api/mobile/v1/chat-fonts', token)

    def select_font(self, token, key):
        if not key or '/' in key:
            raise ERAError('Некорректный ключ шрифта')
        return self.request('POST', '/api/mobile/v1/chat-fonts/' + urllib.parse.quote(key), token)
