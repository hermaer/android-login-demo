"""ERA Android v0.6 — native ERA dashboard, news, chat, calendar, shop and expenses.

The existing offline SQLite accounts are intentionally NOT migrated or deleted:
new login uses the existing website's username/password and PostgreSQL DB.
"""
import asyncio

import flet as ft
import flet_secure_storage as fss

from era_client import ERAClient, ERAError
from era_config import ERA_BASE_URL
from era_screens import MobileScreens
from update_config import APP_VERSION, GITHUB_OWNER, GITHUB_REPOSITORY
from updater import UpdateCheckError, fetch_latest_release, is_newer

BG = "#0B1220"
CARD = "#162033"
ACCENT = "#5793FA"
TEXT = "#F2F6FF"
MUTED = "#A4B2C9"
ERROR = "#FF9D9D"
SUCCESS = "#85E2B5"
TOKEN_KEY = "era.mobile.token.v1"  # Keystore; NEVER save the raw password.
USERNAME_KEY = "era.mobile.username.v1"


async def main(page: ft.Page):
    page.title = "ЭРА"
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 8
    storage = fss.SecureStorage()
    token = ""
    user = None
    saved_username = ""
    active_chat_id = None
    polling_task = None
    try:
        api = ERAClient(ERA_BASE_URL)
        config_error = ""
    except ERAError as exc:
        api = None
        config_error = str(exc)

    def notify(message):
        page.show_dialog(ft.SnackBar(content=ft.Text(message)))

    def stop_poll():
        nonlocal polling_task, active_chat_id
        active_chat_id = None
        if polling_task and not polling_task.done():
            polling_task.cancel()
        polling_task = None

    def view(title, controls, *, back=None):
        width = min(660, max(280, (page.width or 390) - 20))
        content = [
            ft.Container(bgcolor="#12233B", padding=12, border_radius=12,
                         content=ft.Row(controls=[
                             ft.Icon(ft.Icons.BOLT, color=ACCENT, size=27),
                             ft.Text("ЭРА", size=23, weight=ft.FontWeight.BOLD, color=TEXT),
                             ft.Text("· mobile", size=11, color=MUTED)])),
        ]
        if back:
            content.append(ft.TextButton(content="← Назад", on_click=lambda e: back()))
        content.extend([ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=TEXT), *controls])
        page.clean()
        page.add(ft.SafeArea(content=ft.Column(
            controls=[ft.Container(width=width, padding=13, bgcolor=CARD,
                                   border_radius=18,
                                   content=ft.Column(controls=content, spacing=13))],
            scroll=ft.ScrollMode.AUTO, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ), expand=True))
        page.update()

    async def call(func, *args):
        return await asyncio.to_thread(func, *args)

    def error_text():
        return ft.Text("", color=ERROR, size=12, visible=False)

    def render_updates():
        stop_poll()
        status = ft.Text("Нажмите для проверки GitHub Releases", color=MUTED)
        options = ft.Column(spacing=8)
        button = ft.Button(content="Проверить обновления", icon=ft.Icons.REFRESH)

        async def check(e):
            button.disabled = True
            status.value = "Проверка..."
            options.controls = []
            page.update()
            try:
                release = await call(fetch_latest_release, GITHUB_OWNER, GITHUB_REPOSITORY)
                if is_newer(release.version, APP_VERSION):
                    status.value = f"Доступно обновление {release.version}"
                    options.controls.append(ft.Text(release.title, color=TEXT))
                    if release.apk_url:
                        options.controls.append(ft.Button(content="Скачать APK",
                            icon=ft.Icons.DOWNLOAD, action=ft.OpenUrl(release.apk_url)))
                    else:
                        options.controls.append(ft.Button(content="Открыть выпуск GitHub",
                            action=ft.OpenUrl(release.page_url)))
                else:
                    status.value = f"Актуальная версия: {APP_VERSION}"
            except (UpdateCheckError, Exception):
                status.value = "Не удалось проверить GitHub Releases"
            button.disabled = False
            page.update()

        button.on_click = check
        view("Обновление ЭРА", [ft.Text(f"Установлено: {APP_VERSION}", color=MUTED),
                                button, status, options], back=render_home if user else render_login)

    def render_login():
        stop_poll()
        username = ft.TextField(label="Логин на сайте ЭРА", value=saved_username,
                                autocorrect=False)
        password = ft.TextField(label="Пароль ЭРА", password=True, can_reveal_password=True)
        remember = ft.Checkbox(label="Запомнить меня на 90 дней", value=True)
        err = error_text()
        button = ft.Button(content="Войти", bgcolor=ACCENT, color=BG, height=47)

        async def submit(e):
            nonlocal token, user, saved_username
            if not api:
                err.value = config_error
                err.visible = True
                page.update()
                return
            button.disabled = True
            err.visible = False
            page.update()
            try:
                result = await call(api.login, username.value or "", password.value or "",
                                    bool(remember.value))
                token = result["access_token"]
                user = result["user"]
                try:
                    user.update(await call(api.profile, token))
                except ERAError:
                    pass  # Server may still be on v0.5; do not invalidate login.
                saved_username = user["username"]
                if remember.value:
                    try:
                        await storage.set(TOKEN_KEY, token)
                        await storage.set(USERNAME_KEY, saved_username)
                    except Exception:
                        notify("Вход выполнен, но сохранить сеанс не удалось")
                else:
                    try:
                        await storage.remove(TOKEN_KEY)
                    except Exception:
                        pass
                render_home()
            except ERAError as exc:
                err.value, err.visible = str(exc), True
                page.update()
            finally:
                button.disabled = False

        button.on_click = submit
        password.on_submit = submit
        controls = [ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=56, color=ACCENT),
                    ft.Text("Один аккаунт для сайта и Android", color=MUTED, size=12),
                    username, password, remember, err, button]
        if api:
            controls.append(ft.Button(content="Зарегистрироваться на сайте ЭРА",
                                      action=ft.OpenUrl(api.base_url)))
        else:
            controls.append(ft.Text(config_error, color=ERROR, size=12))
        controls.append(ft.TextButton(content=f"Проверить обновления · {APP_VERSION}",
                                      on_click=lambda e: render_updates()))
        view("Вход в ЭРА", controls)

    def render_home():
        stop_poll()
        if not user:
            render_login()
            return

        async def logout(e):
            nonlocal token, user
            old = token
            token, user = "", None
            try:
                await storage.remove(TOKEN_KEY)
            except Exception:
                pass
            if api and old:
                try:
                    await call(api.logout, old)
                except ERAError:
                    pass
            render_login()
            notify("Вы вышли из аккаунта ЭРА")

        view("ЭРА · Мобильное приложение", [
            ft.Container(bgcolor="#223651", padding=13, border_radius=12,
                content=ft.Column(controls=[
                    ft.Text(f"Привет, {user.get('username', '')}!", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Все данные синхронизированы с сайтом ЭРА", size=12, color=MUTED)])),
            ft.Button(content="Главная · баланс и события", icon=ft.Icons.DASHBOARD,
                      on_click=lambda e: asyncio.create_task(screens.dashboard())),
            ft.Button(content="Мой профиль и настройки", icon=ft.Icons.PERSON,
                      on_click=lambda e: asyncio.create_task(screens.profile())),
            ft.Button(content="Чаты", icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                      on_click=lambda e: asyncio.create_task(render_chats())),
            ft.Button(content="Пользователи", icon=ft.Icons.PEOPLE,
                      on_click=lambda e: asyncio.create_task(render_users())),
            ft.Button(content="Новости ЭРА", icon=ft.Icons.ARTICLE,
                      on_click=lambda e: asyncio.create_task(screens.news())),
            ft.Button(content="Новости из источников", icon=ft.Icons.PUBLIC,
                      on_click=lambda e: asyncio.create_task(screens.feed())),
            ft.Button(content="Календарь", icon=ft.Icons.CALENDAR_MONTH,
                      on_click=lambda e: asyncio.create_task(screens.calendar())),
            ft.Button(content="Расходы и аналитика", icon=ft.Icons.RECEIPT_LONG,
                      on_click=lambda e: asyncio.create_task(screens.expenses())),
            ft.Button(content="Магазин", icon=ft.Icons.SHOPPING_BAG,
                      on_click=lambda e: asyncio.create_task(screens.shop())),
            ft.Button(content="Мои покупки", icon=ft.Icons.INVENTORY_2,
                      on_click=lambda e: asyncio.create_task(screens.inventory())),
            ft.Button(content=f"Обновления · {APP_VERSION}", icon=ft.Icons.UPDATE,
                      on_click=lambda e: render_updates()),
            ft.OutlinedButton(content="Выйти", icon=ft.Icons.LOGOUT, on_click=logout),
        ])

    def render_profile():
        asyncio.create_task(screens.profile())

    async def render_users():
        stop_poll()
        if not api or not token:
            return render_login()
        try:
            users = await call(api.users, token)
            buttons = [ft.OutlinedButton(content=f"{item['username']}",
                        icon=ft.Icons.PERSON_OUTLINE,
                        on_click=lambda e, p=item: asyncio.create_task(render_chat(p))) for item in users]
            view("Пользователи ЭРА", buttons or [ft.Text("Нет пользователей", color=MUTED)],
                 back=render_home)
        except ERAError as exc:
            notify(str(exc))

    async def render_chats():
        stop_poll()
        if not api or not token:
            return render_login()
        try:
            chats = await call(api.chats, token)
            buttons = [ft.OutlinedButton(
                content=f"{item['user']['username']}: {(item['last_message']['text'] or '[вложение]')[:38]}",
                icon=ft.Icons.CHAT_OUTLINED,
                on_click=lambda e, p=item['user']: asyncio.create_task(render_chat(p))) for item in chats]
            view("Чаты ЭРА", buttons or [ft.Text("Переписок пока нет", color=MUTED),
                 ft.Button(content="Найти пользователя",
                           on_click=lambda e: asyncio.create_task(render_users()))], back=render_home)
        except ERAError as exc:
            notify(str(exc))

    async def render_chat(peer):
        nonlocal active_chat_id, polling_task
        stop_poll()
        if not api or not token:
            return render_login()
        peer_id = int(peer["id"])
        active_chat_id = peer_id
        items = ft.Column(spacing=8)
        input_box = ft.TextField(label="Сообщение", multiline=True, min_lines=1, max_lines=3)
        status = ft.Text("Загрузка переписки...", color=MUTED, size=11)
        seen = set()
        last_id = 0

        def show_rows(rows):
            nonlocal last_id
            for msg in rows:
                msg_id = int(msg["id"])
                if msg_id in seen:
                    continue
                seen.add(msg_id)
                last_id = max(last_id, msg_id)
                mine = int(msg["sender_id"]) == user["id"]
                value = msg.get("text") or f"📎 {msg.get('file_name') or 'Вложение (откройте в браузере)'}"
                bubble = [ft.Text(("Вы: " if mine else peer["username"] + ": ") + value,
                                  color=TEXT, size=13)]
                file_url = msg.get('file_url') or ''
                if file_url.startswith('/static/chat_uploads/') and api:
                    bubble.append(ft.Button(content='Открыть вложение', icon=ft.Icons.ATTACH_FILE,
                             action=ft.OpenUrl(api.base_url + file_url)))
                items.controls.append(ft.Container(
                    padding=10, border_radius=10,
                    bgcolor="#28466F" if mine else "#29364B",
                    content=ft.Column(controls=bubble, spacing=3)))
            # Keep a bounded number of controls on screen (new messages remain).
            if len(items.controls) > 120:
                items.controls = items.controls[-100:]
            page.update()

        async def refresh(incremental=True):
            if active_chat_id != peer_id:
                return
            rows = await call(api.messages, token, peer_id, last_id if incremental else 0)
            if active_chat_id != peer_id:
                return
            show_rows(rows)
            if any(m["receiver_id"] == user["id"] and not m["is_read"] for m in rows):
                await call(api.read, token, peer_id)

        async def send(e):
            content = (input_box.value or "").strip()
            if not content:
                return
            if len(content) > 4000:
                notify("Сообщение слишком длинное (максимум 4000 символов)")
                return
            send_button.disabled = True
            page.update()
            try:
                await call(api.send, token, peer_id, content)
                input_box.value = ""
                await refresh(True)
            except ERAError as exc:
                notify(str(exc))
            finally:
                send_button.disabled = False
                page.update()

        async def attach(e):
            try:
                files = await ft.FilePicker().pick_files(allow_multiple=False, with_data=True)
            except Exception:
                notify('Не удалось открыть выбор файла')
                return
            if not files:
                return
            picked = files[0]
            if not picked.bytes or len(picked.bytes) > 15 * 1024 * 1024:
                notify('Файл пуст или слишком большой (максимум 15 МБ для аудио)')
                return
            status.value = 'Загрузка вложения...'
            page.update()
            try:
                await call(api.upload_file, token,
                    f'/api/mobile/v1/chats/{peer_id}/attachments', picked.name, picked.bytes)
                await refresh(True)
                status.value = 'Файл отправлен'
            except ERAError as exc:
                status.value = str(exc)
            page.update()

        send_button = ft.Button(content="Отправить", icon=ft.Icons.SEND,
                                bgcolor=ACCENT, color=BG, on_click=send)
        attach_button = ft.Button(content='Прикрепить файл', icon=ft.Icons.ATTACH_FILE,
                                  on_click=attach)
        view("Чат: " + peer["username"], [
            ft.Text("Общий чат сайта и Android · текст, фото, документы, аудио", color=MUTED, size=11),
            items, input_box, ft.Row(controls=[send_button, attach_button], wrap=True),
            status], back=lambda: asyncio.create_task(render_chats()))
        try:
            await refresh(False)
            status.value = "Синхронизация каждые 3 секунды"
            page.update()
        except ERAError as exc:
            status.value = str(exc)
            page.update()

        async def poll():
            while active_chat_id == peer_id:
                await asyncio.sleep(3)
                try:
                    await refresh()
                except ERAError:
                    status.value = "Нет соединения. Повторная попытка..."
                    page.update()

        polling_task = asyncio.create_task(poll())

    def merge_user(updated):
        nonlocal user
        user = {**(user or {}), **updated}

    async def require_login():
        nonlocal token, user
        token, user = '', None
        stop_poll()
        try:
            await storage.remove(TOKEN_KEY)
        except Exception:
            pass
        render_login()

    screens = MobileScreens(
        page, api, lambda: token, lambda: user or {}, merge_user,
        view, render_home, notify, call, stop_poll,
        lambda: asyncio.create_task(require_login()),
    )

    # Existing local demo remains on disk, but does not provide ERA credentials.
    try:
        saved_username = await storage.get(USERNAME_KEY) or ""
        saved_token = await storage.get(TOKEN_KEY) or ""
        if api and saved_token:
            user = await call(api.me, saved_token)
            token = saved_token
            try:
                user.update(await call(api.profile, saved_token))
            except ERAError:
                pass
    except Exception:
        try:
            await storage.remove(TOKEN_KEY)
        except Exception:
            pass
    if user:
        render_home()
    else:
        render_login()


if __name__ == "__main__":
    ft.run(main)
