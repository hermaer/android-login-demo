"""Entry point: run with `flet run` or `python src/main.py`."""

import asyncio

import flet as ft
import flet_secure_storage as fss

from database import User, UserRepository
from remembered_login import RememberedLogin
from update_config import APP_VERSION, GITHUB_OWNER, GITHUB_REPOSITORY
from updater import UpdateCheckError, fetch_latest_release, is_newer

# Colors for a simple, phone-friendly dark interface.
BG = "#0B1220"
CARD = "#162033"
ACCENT = "#5793FA"
TEXT = "#F2F6FF"
MUTED = "#A4B2C9"
ERROR = "#FF9D9D"


async def main(page: ft.Page) -> None:
    page.title = "Мой кабинет"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 14

    repo = UserRepository()
    # Android Keystore / Windows Credential Manager. Never save a raw password.
    # Keep a strong reference to the service for the lifetime of the page.
    secure_storage = fss.SecureStorage()
    remembered_login = RememberedLogin(repo, secure_storage)
    signed_in_user: User | None = None
    remembered_email = ""

    def show_message(message: str) -> None:
        page.show_dialog(ft.SnackBar(content=ft.Text(message)))

    def page_frame(content: ft.Control) -> None:
        # page.width is in logical pixels. Do not use fixed desktop-only widths.
        width = min(420, max(240, (page.width or 390) - 32))
        page.clean()
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    controls=[
                        ft.Container(
                            width=width,
                            padding=22,
                            bgcolor=CARD,
                            border_radius=20,
                            content=content,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            )
        )
        page.update()

    def brand_header(title: str, subtitle: str) -> list[ft.Control]:
        return [
            ft.Icon(ft.Icons.ACCOUNT_CIRCLE_OUTLINED, size=54, color=ACCENT),
            ft.Text(title, size=26, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Text(subtitle, size=13, color=MUTED, text_align=ft.TextAlign.CENTER),
        ]

    def inline_error() -> ft.Text:
        return ft.Text("", size=12, color=ERROR, visible=False)

    def render_updates() -> None:
        """Check public GitHub Releases and offer an APK download in the browser."""
        checking = False
        status = ft.Text(
            "Нажмите кнопку для проверки новой версии на GitHub.",
            color=MUTED,
            size=13,
        )
        details = ft.Column(spacing=9, controls=[])
        check_button = ft.Button(
            content="Проверить обновления",
            icon=ft.Icons.REFRESH,
            bgcolor=ACCENT,
            color=BG,
            height=46,
        )

        async def check_updates(_e=None) -> None:
            nonlocal checking
            if checking:
                return
            checking = True
            check_button.disabled = True
            details.controls = []
            status.color = MUTED
            status.value = "Проверяем GitHub…"
            page.update()
            try:
                latest = await asyncio.to_thread(
                    fetch_latest_release, GITHUB_OWNER, GITHUB_REPOSITORY
                )
                if is_newer(latest.version, APP_VERSION):
                    status.value = f"Доступно обновление: {latest.version}"
                    status.color = "#85E2B5"
                    details.controls = [
                        ft.Text(latest.title, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text(
                            latest.description or "Описание изменений не указано.",
                            color=MUTED,
                            size=12,
                        ),
                    ]
                    if latest.apk_url:
                        details.controls.append(
                            ft.Button(
                                content="Скачать APK обновления",
                                icon=ft.Icons.DOWNLOAD,
                                action=ft.OpenUrl(latest.apk_url),
                                height=46,
                                bgcolor="#2D735C",
                                color=TEXT,
                            )
                        )
                    else:
                        details.controls.append(
                            ft.Text(
                                "В выпуске нет единственного APK для установки. "
                                "Откройте страницу выпуска и выберите подходящий файл.",
                                size=12,
                                color=MUTED,
                            )
                        )
                        details.controls.append(
                            ft.OutlinedButton(
                                content="Открыть GitHub Release",
                                action=ft.OpenUrl(latest.page_url),
                            )
                        )
                    details.controls.append(
                        ft.Text(
                            "После загрузки откройте APK в телефоне и подтвердите "
                            "установку Android. Это не выполняется автоматически.",
                            size=11,
                            color=MUTED,
                        )
                    )
                else:
                    status.value = f"Установлена актуальная версия {APP_VERSION}."
                    status.color = "#85E2B5"
            except UpdateCheckError as exc:
                status.value = str(exc)
                status.color = ERROR
            except Exception:
                status.value = "Не удалось проверить обновления. Попробуйте ещё раз."
                status.color = ERROR
            finally:
                checking = False
                check_button.disabled = False
                page.update()

        check_button.on_click = check_updates
        page_frame(
            ft.Column(
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Icon(ft.Icons.UPDATE, size=44, color=ACCENT),
                    ft.Text("Обновление приложения", size=23, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(f"Установленная версия: {APP_VERSION}", size=14, color=TEXT),
                    ft.Text(
                        "Проверяем опубликованные APK в GitHub Releases. "
                        "Изменения исходного кода без сборки APK на телефон не попадут.",
                        color=MUTED,
                        size=12,
                    ),
                    check_button,
                    status,
                    details,
                    ft.OutlinedButton(
                        content="Назад в личный кабинет" if signed_in_user else "Назад ко входу",
                        height=42,
                        on_click=lambda _e: render_home() if signed_in_user else render_login(),
                    ),
                ],
            )
        )

    def render_login() -> None:
        nonlocal remembered_email
        email = ft.TextField(
            label="Электронная почта",
            hint_text="you@example.com",
            value=remembered_email,
            keyboard_type=ft.KeyboardType.EMAIL,
            autocorrect=False,
        )
        password = ft.TextField(
            label="Пароль", password=True, can_reveal_password=True
        )
        remember_checkbox = ft.Checkbox(label="Запомнить меня", value=False)
        error = inline_error()
        login_button = ft.Button(
            content="Войти",
            bgcolor=ACCENT,
            color=BG,
            height=48,
        )

        async def do_login(_e=None) -> None:
            nonlocal signed_in_user, remembered_email
            if login_button.disabled:
                return
            login_button.disabled = True
            error.visible = False
            page.update()
            try:
                user = await asyncio.to_thread(repo.authenticate, email.value or "", password.value or "")
                if user is None:
                    error.value = "Неверная почта или пароль."
                    error.visible = True
                    page.update()
                    return
                if remember_checkbox.value:
                    saved = await remembered_login.remember(user)
                    remembered_email = user.email if saved else ""
                else:
                    await remembered_login.clear(user, keep_email=False)
                    remembered_email = ""
                    saved = True
                signed_in_user = user
                render_home()
                if not saved:
                    show_message("Вход выполнен, но запомнить его не удалось. Проверьте настройки устройства.")
            finally:
                login_button.disabled = False

        login_button.on_click = do_login
        password.on_submit = do_login
        page_frame(
            ft.Column(
                spacing=17,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    *brand_header("С возвращением!", "Войдите в свой аккаунт"),
                    ft.Container(height=6),
                    email,
                    password,
                    remember_checkbox,
                    ft.Text(
                        "Если включить, приложение запомнит вход на этом устройстве на 90 дней. "
                        "Сам пароль не сохраняется.",
                        size=11,
                        color=MUTED,
                    ),
                    error,
                    login_button,
                    ft.OutlinedButton(
                        content="Создать аккаунт", height=44, on_click=lambda _e: render_register()
                    ),
                    ft.TextButton(
                        content=f"Обновления · v{APP_VERSION}",
                        on_click=lambda _e: render_updates(),
                    ),
                    ft.Text(
                        "Тестовая версия: данные хранятся на этом устройстве.",
                        size=11,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            )
        )

    def render_register() -> None:
        name = ft.TextField(label="Ваше имя", hint_text="Например, Алексей")
        email = ft.TextField(
            label="Электронная почта",
            hint_text="you@example.com",
            keyboard_type=ft.KeyboardType.EMAIL,
            autocorrect=False,
        )
        password = ft.TextField(
            label="Пароль (не менее 8 символов)", password=True, can_reveal_password=True
        )
        confirm = ft.TextField(
            label="Повторите пароль", password=True, can_reveal_password=True
        )
        error = inline_error()

        def do_register(_e=None) -> None:
            nonlocal signed_in_user
            if (password.value or "") != (confirm.value or ""):
                error.value = "Пароли не совпадают."
                error.visible = True
                page.update()
                return
            try:
                user = repo.register(
                    name.value or "", email.value or "", password.value or ""
                )
            except ValueError as exc:
                error.value = str(exc)
                error.visible = True
                page.update()
                return
            signed_in_user = user
            render_home()
            show_message("Аккаунт успешно создан!")

        confirm.on_submit = do_register
        page_frame(
            ft.Column(
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    *brand_header("Регистрация", "Создайте свой локальный аккаунт"),
                    name,
                    email,
                    password,
                    confirm,
                    error,
                    ft.Button(
                        content="Зарегистрироваться",
                        bgcolor=ACCENT,
                        color=BG,
                        height=48,
                        on_click=do_register,
                    ),
                    ft.OutlinedButton(
                        content="У меня уже есть аккаунт",
                        height=44,
                        on_click=lambda _e: render_login(),
                    ),
                ],
            )
        )

    def render_home() -> None:
        nonlocal signed_in_user
        if signed_in_user is None:
            render_login()
            return

        async def logout(_e=None) -> None:
            nonlocal signed_in_user, remembered_email
            previous_user = signed_in_user
            # Revoke the remembered session in the DB before showing login.
            await remembered_login.clear(previous_user, keep_email=True)
            signed_in_user = None
            _user, remembered_email = await remembered_login.restore()
            render_login()
            show_message("Вы вышли из аккаунта. Автоматический вход отключён.")

        placeholder_buttons = [
            ("Мой профиль", ft.Icons.PERSON_OUTLINE),
            ("Мои заявки", ft.Icons.DESCRIPTION_OUTLINED),
            ("Уведомления", ft.Icons.NOTIFICATIONS_OUTLINED),
            ("Настройки", ft.Icons.SETTINGS_OUTLINED),
        ]
        page_frame(
            ft.Column(
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    ft.Icon(ft.Icons.HOME_OUTLINED, size=46, color=ACCENT),
                    ft.Text("Личный кабинет", size=25, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(f"Здравствуйте, {signed_in_user.name}!", size=17, color=TEXT),
                    ft.Text(signed_in_user.email, color=MUTED, size=13),
                    ft.Container(height=5),
                    ft.Text("Разделы приложения", size=13, color=MUTED),
                    *[
                        ft.OutlinedButton(
                            content=label,
                            icon=icon,
                            height=47,
                            on_click=lambda _e, button_name=label: show_message(
                                f"«{button_name}» — раздел в разработке"
                            ),
                        )
                        for label, icon in placeholder_buttons
                    ],
                    ft.Container(height=5),
                    ft.Button(
                        content=f"Проверить обновления · v{APP_VERSION}",
                        icon=ft.Icons.UPDATE,
                        height=47,
                        on_click=lambda _e: render_updates(),
                    ),
                    ft.Container(height=7),
                    ft.Button(
                        content="Выйти из аккаунта",
                        icon=ft.Icons.LOGOUT,
                        height=47,
                        bgcolor="#29374F",
                        color=TEXT,
                        on_click=logout,
                    ),
                    ft.Text(
                        "Прототип работает без интернета и сервера.",
                        size=11,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            )
        )

    # Restore local remembered session after each cold launch of the app.
    signed_in_user, remembered_email = await remembered_login.restore()
    if signed_in_user is not None:
        render_home()
    else:
        render_login()


if __name__ == "__main__":
    ft.run(main)
