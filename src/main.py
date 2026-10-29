"""ERA Android v0.6.1 — improved mobile UX for the existing ERA website.

The existing offline SQLite accounts are intentionally NOT migrated or deleted:
new login uses the existing website's username/password and PostgreSQL DB.
"""
import asyncio
from datetime import datetime

import flet as ft
import flet_secure_storage as fss

from era_client import ERAClient, ERAError
from era_config import ERA_BASE_URL
from era_screens import MobileScreens
from update_config import APP_VERSION, GITHUB_OWNER, GITHUB_REPOSITORY
from updater import UpdateCheckError, fetch_latest_release, is_newer

BG = "#0B1220"
CARD = "#162033"
CARD_ALT = "#1D2A40"
CARD_SOFT = "#223651"
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
    page.scroll = ft.ScrollMode.AUTO
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

    def section_title(title, subtitle=None):
        controls = [ft.Text(title, size=17, weight=ft.FontWeight.BOLD, color=TEXT)]
        if subtitle:
            controls.append(ft.Text(subtitle, size=12, color=MUTED))
        return ft.Column(controls=controls, spacing=3)

    def chip(label, value=None, color=MUTED):
        text = label if value is None else f"{label}: {value}"
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            bgcolor=CARD_SOFT,
            border_radius=999,
            content=ft.Text(text, size=11, color=color),
        )

    def stat_card(label, value, accent=TEXT):
        return ft.Container(
            expand=True,
            bgcolor=CARD_SOFT,
            border_radius=14,
            padding=12,
            content=ft.Column(
                spacing=3,
                controls=[
                    ft.Text(label, size=11, color=MUTED),
                    ft.Text(str(value), size=20, color=accent, weight=ft.FontWeight.BOLD),
                ],
            ),
        )

    def action_button(label, on_click=None, *, icon=None, primary=False, expand=False, url=None):
        kwargs = dict(content=label, icon=icon, expand=expand)
        if url:
            kwargs["action"] = ft.OpenUrl(url)
        else:
            kwargs["on_click"] = on_click
        if primary:
            kwargs["bgcolor"] = ACCENT
            kwargs["color"] = BG
            return ft.Button(**kwargs)
        return ft.OutlinedButton(**kwargs)

    def nav_card(title, subtitle, icon, callback, badge=None):
        return ft.Container(
            bgcolor=CARD_ALT,
            border_radius=16,
            padding=12,
            border=ft.Border.all(1, "#243856"),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=12,
                        bgcolor="#1E3A5F",
                        content=ft.Icon(icon, color=ACCENT, size=24),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text(title, size=15, color=TEXT, weight=ft.FontWeight.BOLD),
                            ft.Text(subtitle, size=11, color=MUTED),
                        ],
                    ),
                    *([chip(badge)] if badge else []),
                    ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=MUTED, on_click=lambda e: callback()),
                ],
            ),
        )

    def list_card(title, subtitle="", icon=ft.Icons.CIRCLE, on_click=None, trailing=None):
        return ft.Container(
            bgcolor=CARD_ALT,
            border_radius=14,
            padding=12,
            border=ft.Border.all(1, "#243856"),
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color=ACCENT, size=20),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text(title, color=TEXT, size=14, weight=ft.FontWeight.W_600),
                            *([ft.Text(subtitle, color=MUTED, size=11)] if subtitle else []),
                        ],
                    ),
                    *(trailing if isinstance(trailing, list) else ([trailing] if trailing else [])),
                ]
            ),
            on_click=(lambda e: on_click()) if on_click else None,
        )

    def view(title, controls, *, back=None, subtitle=None):
        width = min(720, max(280, (page.width or 390) - 16))
        header = ft.Container(
            bgcolor="#12233B",
            padding=12,
            border_radius=16,
            border=ft.Border.all(1, "#213453"),
            content=ft.Row(
                controls=[
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=14,
                        bgcolor="#1E3A5F",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.BOLT, color=ACCENT, size=24),
                    ),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Text("ЭРА", size=22, weight=ft.FontWeight.BOLD, color=TEXT),
                            ft.Text("mobile · общий аккаунт с сайтом", size=11, color=MUTED),
                        ],
                    ),
                    *([action_button("Назад", lambda e: back(), icon=ft.Icons.ARROW_BACK)] if back else []),
                ]
            ),
        )
        page.clean()
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=width,
                            padding=14,
                            bgcolor=CARD,
                            border_radius=22,
                            border=ft.Border.all(1, "#243856"),
                            content=ft.Column(
                                spacing=14,
                                controls=[
                                    header,
                                    ft.Column(
                                        spacing=3,
                                        controls=[
                                            ft.Text(title, size=23, weight=ft.FontWeight.BOLD, color=TEXT),
                                            *([ft.Text(subtitle, size=12, color=MUTED)] if subtitle else []),
                                        ],
                                    ),
                                    *controls,
                                ],
                            ),
                        )
                    ],
                ),
            )
        )
        page.update()

    async def call(func, *args):
        return await asyncio.to_thread(func, *args)

    def error_text():
        return ft.Text("", color=ERROR, size=12, visible=False)

    def render_updates():
        stop_poll()
        status = ft.Text("Нажмите для проверки GitHub Releases", color=MUTED, size=12)
        options = ft.Column(spacing=8)
        button = action_button("Проверить обновления", icon=ft.Icons.REFRESH, primary=True)

        async def check(e):
            button.disabled = True
            status.value = "Проверка..."
            options.controls = []
            page.update()
            try:
                release = await call(fetch_latest_release, GITHUB_OWNER, GITHUB_REPOSITORY)
                if is_newer(release.version, APP_VERSION):
                    status.value = f"Доступно обновление {release.version}"
                    options.controls = [
                        list_card(release.title, subtitle="Доступен новый выпуск на GitHub Releases",
                                  icon=ft.Icons.UPDATE),
                        action_button("Скачать APK", icon=ft.Icons.DOWNLOAD, primary=True,
                                      url=release.apk_url or release.page_url),
                    ]
                else:
                    status.value = f"Актуальная версия: {APP_VERSION}"
            except (UpdateCheckError, Exception):
                status.value = "Не удалось проверить GitHub Releases"
            button.disabled = False
            page.update()

        button.on_click = check
        view(
            "Обновление ЭРА",
            [
                stat_card("Установлено", APP_VERSION, SUCCESS),
                button,
                status,
                options,
            ],
            back=render_home if user else render_login,
            subtitle="Обновление APK через GitHub Releases.",
        )

    def render_login():
        stop_poll()
        username = ft.TextField(label="Логин на сайте ЭРА", value=saved_username, autocorrect=False)
        password = ft.TextField(label="Пароль ЭРА", password=True, can_reveal_password=True)
        remember = ft.Checkbox(label="Запомнить меня на 90 дней", value=True)
        err = error_text()
        button = action_button("Войти", icon=ft.Icons.LOGIN, primary=True)

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
                result = await call(api.login, username.value or "", password.value or "", bool(remember.value))
                token = result["access_token"]
                user = result["user"]
                try:
                    user.update(await call(api.profile, token))
                except ERAError:
                    pass
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
        controls = [
            ft.Container(
                padding=16,
                bgcolor=CARD_ALT,
                border_radius=18,
                border=ft.Border.all(1, "#243856"),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(controls=[ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=48, color=ACCENT),
                                         ft.Column(controls=[
                                             ft.Text("Вход в ЭРА", size=18, color=TEXT,
                                                     weight=ft.FontWeight.BOLD),
                                             ft.Text("Один аккаунт для сайта и Android", color=MUTED, size=12),
                                         ])]),
                        username,
                        password,
                        remember,
                        err,
                        button,
                    ],
                ),
            )
        ]
        if api:
            controls.append(action_button("Открыть сайт ЭРА", icon=ft.Icons.OPEN_IN_BROWSER, url=api.base_url))
        else:
            controls.append(ft.Text(config_error, color=ERROR, size=12))
        controls.append(action_button(f"Проверить обновления · {APP_VERSION}",
                                      lambda e: render_updates(), icon=ft.Icons.UPDATE))
        view("Вход в ЭРА", controls, subtitle="Авторизация в существующем аккаунте сайта.")

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

        controls = [
            ft.Container(
                bgcolor=CARD_ALT,
                border_radius=18,
                padding=14,
                border=ft.Border.all(1, "#243856"),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Text(f"Привет, {user.get('username', '')}!", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text("Все данные синхронизированы с сайтом ЭРА", size=12, color=MUTED),
                        ft.Row(wrap=True, spacing=8, controls=[
                            chip("Версия", APP_VERSION),
                            chip("Уровень", user.get("level", "—"), SUCCESS),
                            chip("Монеты", user.get("balance_coin", "—"), SUCCESS),
                        ]),
                    ],
                ),
            ),
            section_title("Основное"),
            nav_card("Главная", "Баланс, события и быстрый обзор", ft.Icons.DASHBOARD,
                     lambda: asyncio.create_task(screens.dashboard())),
            nav_card("Профиль и настройки", "Личные данные, пароль, аватар и покупки", ft.Icons.PERSON,
                     lambda: asyncio.create_task(screens.profile())),
            nav_card("Чаты", "Список диалогов и сообщения", ft.Icons.CHAT_BUBBLE_OUTLINE,
                     lambda: asyncio.create_task(render_chats())),
            nav_card("Пользователи", "Начать новый диалог", ft.Icons.PEOPLE,
                     lambda: asyncio.create_task(render_users())),
            section_title("Контент"),
            nav_card("Новости ЭРА", "Лента, комментарии и лайки", ft.Icons.ARTICLE,
                     lambda: asyncio.create_task(screens.news())),
            nav_card("Внешние новости", "Публичные источники и поиск", ft.Icons.PUBLIC,
                     lambda: asyncio.create_task(screens.feed())),
            section_title("Планирование и финансы"),
            nav_card("Календарь", "События и напоминания", ft.Icons.CALENDAR_MONTH,
                     lambda: asyncio.create_task(screens.calendar())),
            nav_card("Расходы", "Категории, расходы и аналитика", ft.Icons.RECEIPT_LONG,
                     lambda: asyncio.create_task(screens.expenses())),
            nav_card("Магазин", "Товары и покупки за монеты", ft.Icons.SHOPPING_BAG,
                     lambda: asyncio.create_task(screens.shop())),
            nav_card("Мои покупки", "Инвентарь и приобретённые товары", ft.Icons.INVENTORY_2,
                     lambda: asyncio.create_task(screens.inventory())),
            section_title("Система"),
            nav_card("Обновления", f"Проверка версии {APP_VERSION}", ft.Icons.UPDATE,
                     render_updates),
            action_button("Выйти", logout, icon=ft.Icons.LOGOUT),
        ]
        view("ЭРА · Мобильное приложение", controls, subtitle="Полноценный мобильный клиент сайта ЭРА.")

    async def render_users():
        stop_poll()
        if not api or not token:
            return render_login()
        try:
            users = await call(api.users, token)
            cards = []
            for item in users:
                cards.append(list_card(
                    item['username'],
                    subtitle=f"ID пользователя: {item['id']}",
                    icon=ft.Icons.PERSON_OUTLINE,
                    on_click=lambda p=item: asyncio.create_task(render_chat(p)),
                    trailing=ft.Icon(ft.Icons.CHAT, color=ACCENT),
                ))
            view("Пользователи ЭРА", cards or [ft.Text("Нет пользователей", color=MUTED)],
                 back=render_home, subtitle="Выберите пользователя, чтобы начать чат.")
        except ERAError as exc:
            notify(str(exc))

    async def render_chats():
        stop_poll()
        if not api or not token:
            return render_login()
        try:
            chats = await call(api.chats, token)
            cards = []
            for item in chats:
                preview = (item['last_message'].get('text') or '[вложение]')[:55]
                cards.append(list_card(
                    item['user']['username'],
                    subtitle=preview,
                    icon=ft.Icons.CHAT_OUTLINED,
                    on_click=lambda p=item['user']: asyncio.create_task(render_chat(p)),
                    trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=MUTED),
                ))
            controls = cards or [
                ft.Text("Переписок пока нет", color=MUTED),
                action_button("Найти пользователя", lambda e: asyncio.create_task(render_users()), icon=ft.Icons.PERSON_SEARCH),
            ]
            view("Чаты ЭРА", controls, back=render_home,
                 subtitle="Открывайте отдельные диалоги, а не весь поток сообщений сразу.")
        except ERAError as exc:
            notify(str(exc))

    def format_dt(value):
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d.%m %H:%M")
        except Exception:
            return value[:16]

    async def render_chat(peer):
        nonlocal active_chat_id, polling_task
        stop_poll()
        if not api or not token:
            return render_login()
        peer_id = int(peer["id"])
        active_chat_id = peer_id
        message_list = ft.ListView(expand=True, spacing=8, auto_scroll=True, padding=6)
        input_box = ft.TextField(label="Сообщение", multiline=True, min_lines=1, max_lines=4, expand=True)
        status = ft.Text("Загрузка переписки...", color=MUTED, size=11)
        hint = ft.Text("Показываются последние 40 сообщений. Новые сообщения синхронизируются автоматически.", color=MUTED, size=11)
        seen = set()
        last_id = 0

        def message_bubble(msg):
            mine = int(msg["sender_id"]) == user["id"]
            text_value = msg.get("text") or ""
            file_name = msg.get('file_name') or 'Вложение'
            file_url = msg.get('file_url') or ''
            meta = ft.Text(format_dt(msg.get("created_at")), size=10, color=MUTED)
            body_controls = []
            if text_value:
                body_controls.append(ft.Text(text_value, color=TEXT, size=13, selectable=True))
            else:
                body_controls.append(ft.Text(f"📎 {file_name}", color=TEXT, size=13))
            if file_url.startswith('/static/chat_uploads/') and api:
                body_controls.append(action_button('Открыть вложение', icon=ft.Icons.ATTACH_FILE,
                                                   url=api.base_url + file_url))
            body_controls.append(meta)
            return ft.Row(
                alignment=ft.MainAxisAlignment.END if mine else ft.MainAxisAlignment.START,
                controls=[
                    ft.Container(
                        width=min(max((page.width or 390) - 110, 180), 460),
                        padding=12,
                        border_radius=16,
                        bgcolor="#28466F" if mine else "#29364B",
                        border=ft.Border.all(1, "#36557E" if mine else "#36445C"),
                        content=ft.Column(spacing=5, controls=body_controls),
                    )
                ],
            )

        def show_rows(rows, replace=False):
            nonlocal last_id, seen
            if replace:
                seen = set()
                last_id = 0
                message_list.controls = []
            added = False
            for msg in rows:
                msg_id = int(msg["id"])
                if msg_id in seen:
                    continue
                seen.add(msg_id)
                last_id = max(last_id, msg_id)
                message_list.controls.append(message_bubble(msg))
                added = True
            if added:
                if len(message_list.controls) > 60:
                    message_list.controls = message_list.controls[-60:]
            page.update()

        async def refresh(incremental=True):
            if active_chat_id != peer_id:
                return
            rows = await call(api.messages, token, peer_id, last_id if incremental else 0, 40)
            if active_chat_id != peer_id:
                return
            show_rows(rows, replace=not incremental)
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
                notify('Файл пуст или слишком большой (максимум 15 МБ)')
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

        send_button = action_button("Отправить", icon=ft.Icons.SEND, primary=True)
        send_button.on_click = send
        attach_button = action_button('Файл', icon=ft.Icons.ATTACH_FILE)
        attach_button.on_click = attach
        open_browser = action_button('Открыть сайт', icon=ft.Icons.OPEN_IN_BROWSER,
                                     url=api.base_url if api else None)
        controls = [
            ft.Container(
                bgcolor=CARD_ALT,
                border_radius=16,
                border=ft.Border.all(1, "#243856"),
                padding=12,
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(controls=[
                            ft.Icon(ft.Icons.PERSON, color=ACCENT),
                            ft.Column(expand=True, spacing=2, controls=[
                                ft.Text(peer['username'], size=18, color=TEXT, weight=ft.FontWeight.BOLD),
                                ft.Text('Общий чат сайта и Android', size=11, color=MUTED),
                            ]),
                            chip('онлайн-обновление'),
                        ]),
                        hint,
                    ],
                ),
            ),
            ft.Container(
                height=min(max((page.height or 740) - 310, 320), 520),
                bgcolor="#101B2D",
                border_radius=16,
                border=ft.Border.all(1, "#243856"),
                padding=8,
                content=message_list,
            ),
            ft.Container(
                bgcolor=CARD_ALT,
                border_radius=16,
                border=ft.Border.all(1, "#243856"),
                padding=12,
                content=ft.Column(
                    spacing=10,
                    controls=[
                        input_box,
                        ft.Row(wrap=True, spacing=8, controls=[send_button, attach_button, open_browser]),
                        status,
                    ],
                ),
            ),
        ]
        view("Чат", controls, back=lambda: asyncio.create_task(render_chats()), subtitle=f"Диалог с {peer['username']}")
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
