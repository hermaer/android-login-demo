"""Native ERA screens backed by the existing Beget database via /api/mobile/v1."""
from __future__ import annotations

import asyncio
from datetime import date
from urllib.parse import urlsplit

import flet as ft
from era_client import ERAError

BG_CARD = '#1D2A40'
BG_ALT = '#223651'
PALE = '#A4B2C9'
WHITE = '#F2F6FF'
BLUE = '#5793FA'
GREEN = '#85E2B5'


class MobileScreens:
    def __init__(self, page, api, token, current_user, update_user, view, home, notify, invoke, stop_poll, require_login):
        self.page = page
        self.api = api
        self.token = token
        self.current_user = current_user
        self.update_user = update_user
        self.view = view
        self.home = home
        self.notify = notify
        self.invoke = invoke
        self.stop_poll = stop_poll
        self.require_login = require_login

    async def request(self, func, *args):
        try:
            return await self.invoke(func, self.token(), *args)
        except ERAError as exc:
            self.notify(str(exc))
            return None

    def launch(self, coro):
        asyncio.create_task(coro)

    def go(self, title, controls, back=None, subtitle=None):
        self.stop_poll()
        self.view(title, controls, back=back or self.home, subtitle=subtitle)

    def text(self, value, size=13, color=WHITE, weight=None):
        return ft.Text(str(value), size=size, color=color, weight=weight)

    def small(self, value):
        return self.text(value, 12, PALE)

    def panel(self, contents, title=None):
        rows = []
        if title:
            rows.append(ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=WHITE))
        rows.extend(contents)
        return ft.Container(
            border_radius=16,
            bgcolor=BG_CARD,
            padding=12,
            border=ft.Border.all(1, '#29415F'),
            content=ft.Column(controls=rows, spacing=8),
        )

    def action(self, label, handler, icon=None, primary=False):
        kwargs = dict(content=label, icon=icon, on_click=lambda e: self.launch(handler()))
        if primary:
            kwargs.update(bgcolor=BLUE, color='#0B1220')
            return ft.Button(**kwargs)
        return ft.OutlinedButton(**kwargs)

    def section(self, title, subtitle=None):
        rows = [self.text(title, 16, weight=ft.FontWeight.BOLD)]
        if subtitle:
            rows.append(self.small(subtitle))
        return ft.Column(controls=rows, spacing=2)

    def stats_row(self, items):
        cards = []
        for label, value, color in items:
            cards.append(ft.Container(
                expand=True,
                padding=10,
                bgcolor=BG_ALT,
                border_radius=12,
                content=ft.Column(controls=[self.small(label), self.text(value, 18, color)], spacing=3),
            ))
        return ft.Row(controls=cards, spacing=8)

    def date_ok(self, value):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            self.notify('Дата должна быть в формате ГГГГ-ММ-ДД')
            return None

    def media(self, url, width=275):
        if isinstance(url, str) and url.startswith('/static/') and not url.startswith('//'):
            return ft.Image(src=self.api.base_url + url, width=width, fit=ft.ImageFit.CONTAIN)
        return None

    def safe_open(self, url):
        """Only trust HTTPS link supplied by the server, not arbitrary schemes."""
        if not url: return None
        if url.startswith('/') and not url.startswith('//'):
            url = self.api.base_url + url
        p = urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password:
            return None
        return ft.Button(content='Открыть', icon=ft.Icons.OPEN_IN_NEW, action=ft.OpenUrl(url))

    async def dashboard(self):
        data = await self.request(self.api.dashboard)
        if data is None: return
        user = data['user']
        self.update_user(user)
        event_cards = [self.panel([self.text(x['title'], 14), self.small(x['event_date'])])
                       for x in data['upcoming_events']] or [self.small('Ближайших событий пока нет')]
        self.go('ЭРА · Главная', [
            self.panel([self.text('Добро пожаловать, ' + (user.get('username') or ''), 18),
                        self.small('Один аккаунт на сайте и Android')]),
            self.stats_row([
                ('Монеты', f"{user['balance_coin']:,.0f}", GREEN),
                ('Уровень', str(user['level']), WHITE),
            ]),
            self.stats_row([
                ('Непрочитанные сообщения', str(data['unread_messages']), WHITE),
                ('Расходы за месяц', f"{data['month_expenses']:,.2f}", GREEN),
            ]),
            self.section('Ближайшие события', 'Краткий обзор календаря ЭРА'),
            *event_cards,
            self.section('Быстрые действия'),
            self.action('Лента новостей', self.news, ft.Icons.ARTICLE),
            self.action('Читать внешние новости', self.feed, ft.Icons.PUBLIC),
            self.action('Календарь', self.calendar, ft.Icons.CALENDAR_MONTH),
            self.action('Мои расходы', self.expenses, ft.Icons.RECEIPT_LONG),
            self.action('Магазин', self.shop, ft.Icons.SHOPPING_BAG),
        ], subtitle='Короткая сводка по аккаунту, событиям и финансам.')

    async def profile(self):
        data = await self.request(self.api.profile)
        if data is None: return
        self.update_user(data)
        avatar = self.media(data.get('avatar_url'), 95)
        elems = [
            *([avatar] if avatar else []),
            self.panel([self.text(data['username'], 19),
                        self.small(f"Уровень {data['level']} · Опыт {data['experience']}"),
                        self.small(f"Монеты: {data['balance_coin']:,.2f}"),
                        self.small(f"Баланс: {data['balance']:,.2f}")]),
            self.panel([self.text('Email: ' + (data['email'] or 'не указан')),
                        self.text('Телефон: ' + (data['phone'] or 'не указан')),
                        self.text('О себе: ' + (data['about'] or '—'))]),
            self.action('Изменить аватар', self.avatar_picker, ft.Icons.ADD_A_PHOTO),
            self.action('Редактировать профиль', lambda: self.edit_profile(data), ft.Icons.EDIT),
            self.action('Сменить пароль', self.password, ft.Icons.LOCK),
            self.action('Мои покупки', self.inventory, ft.Icons.INVENTORY_2),
            self.action('Шрифт чата', self.chat_fonts, ft.Icons.FONT_DOWNLOAD),
        ]
        self.go('Мой профиль', elems, subtitle='Данные синхронизируются с профилем на сайте ЭРА.')

    async def avatar_picker(self):
        try:
            files = await ft.FilePicker().pick_files(allow_multiple=False, with_data=True)
        except Exception:
            self.notify('Не удалось открыть выбор файла'); return
        if not files: return
        picked = files[0]
        if not picked.bytes or len(picked.bytes) > 3 * 1024 * 1024:
            self.notify('Выберите изображение до 3 МБ'); return
        try:
            updated = await asyncio.to_thread(self.api.upload_file, self.token(),
                    '/api/mobile/v1/profile/avatar', picked.name, picked.bytes)
            self.update_user(updated)
            self.notify('Аватар обновлён на сайте ЭРА')
            await self.profile()
        except ERAError as exc:
            self.notify(str(exc))

    async def edit_profile(self, data):
        email = ft.TextField(label='Email', value=data.get('email', ''))
        phone = ft.TextField(label='Телефон', value=data.get('phone', ''))
        about = ft.TextField(label='О себе', value=data.get('about', ''), multiline=True,
                             min_lines=2, max_lines=5)

        async def submit():
            result = await self.request(self.api.edit_profile,
                                        email.value or '', phone.value or '', about.value or '')
            if result is not None:
                self.update_user(result)
                self.notify('Профиль обновлён на сервере ЭРА')
                await self.profile()
        self.go('Редактировать профиль', [email, phone, about,
                self.action('Сохранить', submit, ft.Icons.SAVE, True)], back=lambda: self.launch(self.profile()))

    async def password(self):
        old = ft.TextField(label='Текущий пароль', password=True, can_reveal_password=True)
        new = ft.TextField(label='Новый пароль (от 6 символов)', password=True, can_reveal_password=True)
        repeat = ft.TextField(label='Повтор нового пароля', password=True, can_reveal_password=True)

        async def submit():
            if (new.value or '') != (repeat.value or ''):
                self.notify('Пароли не совпадают'); return
            if len(new.value or '') < 6:
                self.notify('Минимум 6 символов'); return
            result = await self.request(self.api.change_password, old.value or '', new.value or '')
            if result is not None:
                self.notify('Пароль изменён. Войдите заново на телефоне.')
                # Old token revoked on server. Trigger clean logout in host screen.
                self.require_login()
        self.go('Смена пароля', [self.small('После изменения все мобильные сеансы завершатся.'),
                old, new, repeat, self.action('Сменить пароль', submit, ft.Icons.LOCK, True)],
                back=lambda: self.launch(self.profile()))

    async def news(self, skip=0):
        data = await self.request(self.api.news, skip)
        if data is None: return
        contents = [self.small('Лента общая с сайтом ЭРА. Лайки начисляют опыт и монеты.')]
        for n in data:
            img = self.media(n.get('image_url'))
            contents.append(self.panel([
                self.text(('📌 ' if n.get('pinned') else '') + n['title'], 15),
                *([img] if img else []),
                self.small((n.get('created_at') or '')[:10] + ' · ♥ ' + str(n['likes'])),
                self.small(n.get('content', '')[:220]),
                self.action('Читать · Комментарии', lambda id=n['id']: self.news_detail(id), ft.Icons.CHAT),
            ]))
        if not data: contents.append(self.small('Новостей пока нет'))
        if skip > 0:
            contents.append(self.action('Предыдущие', lambda: self.news(max(0, skip - 20)), ft.Icons.ARROW_BACK))
        if len(data) == 20:
            contents.append(self.action('Следующие', lambda: self.news(skip + 20), ft.Icons.ARROW_FORWARD))
        if self.current_user().get('is_admin'):
            contents.append(self.action('Добавить новость (администратор)', self.admin_news_form, ft.Icons.ADD))
        self.go('Новости ЭРА', contents, subtitle='Лента новостей и публикаций сайта ЭРА.')

    async def news_detail(self, news_id):
        n = await self.request(self.api.news_item, news_id)
        if n is None: return
        comment = ft.TextField(label='Ваш комментарий', multiline=True, min_lines=2, max_lines=4)
        contents = [
            self.text(n['title'], 18), self.small('♥ ' + str(n['likes'])),
            self.text(n['content'], 13),
        ]
        image = self.media(n.get('image_url'))
        if image: contents.insert(1, image)

        async def like():
            result = await self.request(self.api.news_like, news_id)
            if result is not None: await self.news_detail(news_id)

        async def post():
            content = (comment.value or '').strip()
            if not content: self.notify('Введите комментарий'); return
            result = await self.request(self.api.news_comment, news_id, content)
            if result is not None: await self.news_detail(news_id)

        if not n['liked']: contents.append(self.action('Нравится (+10 опыта, +100 монет)', like, ft.Icons.FAVORITE))
        contents.extend([self.text('Комментарии', 16),
                        *[self.panel([self.small(c['username'] + ' · ' + (c.get('created_at') or '')[:10]),
                                      self.text(c['content'])]) for c in n['comments']],
                        comment, self.action('Отправить комментарий', post, ft.Icons.SEND, True)])
        if self.current_user().get('is_admin'):
            contents.append(self.action('Редактировать новость', lambda: self.admin_news_form(n), ft.Icons.EDIT))
            contents.append(self.action('Удалить новость', lambda: self.confirm_news_delete(n), ft.Icons.DELETE))
        self.go('Новость ЭРА', contents, back=lambda: self.launch(self.news()))

    async def feed(self, category='', keyword=''):
        rows = await self.request(self.api.feed, category, keyword)
        if rows is None: return
        category_box = ft.TextField(label='Категория (например crypto)', value=category)
        search = ft.TextField(label='Поиск', value=keyword)
        contents = [category_box, search,
                    self.action('Найти новости', lambda: self.feed((category_box.value or '').strip(),
                                                           (search.value or '').strip()), ft.Icons.SEARCH)]
        for x in rows:
            entry = [self.text(x['title'] or 'Новость', 15),
                     self.small(f"{x['source'] or 'Источник'} · {(x['published_at'] or '')[:10]}"),
                     self.small(x['content'][:260])]
            action = self.safe_open(x.get('url'))
            if action: entry.append(action)
            contents.append(self.panel(entry))
        if not rows: contents.append(self.small('По запросу ничего не найдено'))
        self.go('Внешняя лента', contents, subtitle='Поиск новостей из внешних источников.')

    async def calendar(self):
        rows = await self.request(self.api.calendar)
        if rows is None: return
        contents = [self.action('Добавить событие', self.calendar_form, ft.Icons.ADD, True)]
        for x in sorted(rows, key=lambda r: r['event_date'], reverse=True):
            contents.append(self.panel([
                self.text(x['title'], 15), self.small(x['event_date'] + ' · ' + x['event_type']),
                self.small(x.get('description') or ''),
                self.action('Удалить', lambda a=x: self.calendar_confirm_delete(a), ft.Icons.DELETE),
            ]))
        if not rows: contents.append(self.small('Событий нет'))
        self.go('Календарь', contents, subtitle='Личные события и напоминания.')

    async def calendar_form(self):
        title = ft.TextField(label='Название события')
        when = ft.TextField(label='Дата ГГГГ-ММ-ДД', value=date.today().isoformat())
        kind = ft.TextField(label='Тип (event, birthday, holiday)', value='event')
        desc = ft.TextField(label='Описание', multiline=True, min_lines=2)
        yearly = ft.Checkbox(label='Повторять ежегодно', value=False)

        async def save():
            day = self.date_ok(when.value or '')
            if not day: return
            result = await self.request(self.api.calendar_create, title.value or '', desc.value or '',
                                        day, kind.value or 'event', bool(yearly.value))
            if result is not None: await self.calendar()
        self.go('Добавить событие', [title, when, kind, desc, yearly,
                self.action('Создать', save, ft.Icons.SAVE, True)],
                back=lambda: self.launch(self.calendar()))

    async def calendar_confirm_delete(self, row):
        async def remove():
            result = await self.request(self.api.calendar_delete, row['id'])
            if result is not None: await self.calendar()
        self.go('Удалить событие?', [self.text(row['title'], 16), self.small(row['event_date']),
                self.action('Да, удалить событие', remove, ft.Icons.DELETE, True),
                self.action('Отмена', self.calendar)], back=lambda: self.launch(self.calendar()))

    async def expenses(self):
        summary, rows = await asyncio.gather(self.request(self.api.expense_summary),
                                             self.request(self.api.expenses))
        if summary is None or rows is None: return
        contents = [
            self.panel([self.text(f"За месяц: {summary['month']:,.2f}", 20, GREEN),
                        self.small(f"За всё время: {summary['total']:,.2f}")]),
            self.action('Добавить расход', self.expense_form, ft.Icons.ADD, True),
            self.action('Добавить категорию', self.category_form, ft.Icons.CREATE_NEW_FOLDER),
            self.text('По категориям за месяц', 16),
            *[self.panel([self.text(x['name'] + f" · {x['amount']:,.2f}")])
              for x in summary['by_category']],
            self.text('Последние расходы', 16),
        ]
        for x in rows:
            contents.append(self.panel([
                self.text(f"{x['amount']} · {x['category']}", 15),
                self.small(x['expense_date'] + ' · ' + x.get('description', '')),
                self.action('Удалить', lambda a=x: self.expense_confirm_delete(a), ft.Icons.DELETE),
            ]))
        if not rows: contents.append(self.small('Расходов пока нет'))
        self.go('Мои расходы', contents, subtitle='Расходы, категории и краткая аналитика.')

    async def expense_form(self):
        cats = await self.request(self.api.expense_categories)
        if cats is None: return
        amount = ft.TextField(label='Сумма (например 125.50)', keyboard_type=ft.KeyboardType.NUMBER)
        when = ft.TextField(label='Дата ГГГГ-ММ-ДД', value=date.today().isoformat())
        desc = ft.TextField(label='Описание')
        selected = {'id': None}
        label = self.small('Выберите категорию:')
        choices = []
        for x in cats:
            def choose(e, row=x):
                selected['id'] = row['id']
                label.value = 'Категория: ' + row['name']
                self.page.update()
            choices.append(ft.OutlinedButton(content=x['name'], on_click=choose))

        async def save():
            if selected['id'] is None:
                self.notify('Выберите категорию'); return
            day = self.date_ok(when.value or '')
            if not day: return
            result = await self.request(self.api.expense_create, (amount.value or '').strip(),
                                        selected['id'], desc.value or '', day)
            if result is not None: await self.expenses()
        self.go('Добавить расход', [amount, when, desc, label, *choices,
                self.action('Сохранить расход', save, ft.Icons.SAVE, True)],
                back=lambda: self.launch(self.expenses()))

    async def category_form(self):
        name = ft.TextField(label='Название категории')
        async def save():
            result = await self.request(self.api.expense_category_create, name.value or '')
            if result is not None:
                self.notify('Категория создана')
                await self.expenses()
        self.go('Новая категория', [name, self.action('Создать', save, ft.Icons.ADD, True)],
                back=lambda: self.launch(self.expenses()))

    async def expense_confirm_delete(self, row):
        async def remove():
            result = await self.request(self.api.expense_delete, row['id'])
            if result is not None: await self.expenses()
        self.go('Удалить расход?', [self.text(f"{row['amount']} · {row['category']}", 16),
                self.action('Да, удалить расход', remove, ft.Icons.DELETE, True),
                self.action('Отмена', self.expenses)])

    async def shop(self, category_id=None, sort=''):
        data = await self.request(self.api.shop, category_id, sort)
        if data is None: return
        contents = [self.panel([self.text(f"Ваши монеты: {data['balance_coin']:,.2f}", 18, GREEN)]),
                    self.action('Мои покупки', self.inventory, ft.Icons.INVENTORY_2),
            self.action('Шрифт чата', self.chat_fonts, ft.Icons.FONT_DOWNLOAD),
                    self.action('Все товары', lambda: self.shop(), ft.Icons.APPS),
                    self.action('По цене ↑', lambda: self.shop(category_id, 'price_asc')),
                    self.action('По цене ↓', lambda: self.shop(category_id, 'price_desc'))]
        for c in data['categories']:
            contents.append(self.action(c['name'], lambda id=c['id']: self.shop(id, sort)))
        for x in data['items']:
            img = self.media(x.get('image_url'))
            entry = [self.text(x['name'], 16), *([img] if img else []),
                     self.small(x.get('description') or ''),
                     self.text(f"{x['price']:,.2f} монет", 14, GREEN)]
            if x['owned']:
                entry.append(self.small('✓ Уже приобретено'))
            elif x.get('owner_user_id') == self.current_user().get('id'):
                entry.append(self.small('Ваш товар'))
            else:
                entry.append(self.action('Купить', lambda item=x: self.buy_confirm(item), ft.Icons.SHOPPING_CART))
            contents.append(self.panel(entry))
        if not data['items']: contents.append(self.small('Товаров нет'))
        self.go('Магазин ЭРА', contents, subtitle='Покупки за монеты и доступные товары.')

    async def buy_confirm(self, item):
        async def buy():
            result = await self.request(self.api.buy, item['id'])
            if result is not None:
                self.notify('Покупка успешна')
                await self.shop()
        self.go('Подтвердить покупку', [self.text(item['name'], 17),
                self.text(f"Цена: {item['price']:,.2f} монет", 15),
                self.action('Подтвердить оплату монетами', buy, ft.Icons.CHECK, True),
                self.action('Отмена', self.shop)], back=lambda: self.launch(self.shop()))

    async def inventory(self):
        items = await self.request(self.api.inventory)
        if items is None: return
        self.go('Мои покупки', [*[self.panel([self.text(x['name'], 15),
                                            self.small(x['description'])], title='Приобретённый товар') for x in items],
                                 *([self.small('Покупок пока нет')] if not items else [])],
                back=lambda: self.launch(self.shop()), subtitle='Все товары, которые уже приобретены.')

    async def chat_fonts(self):
        data = await self.request(self.api.fonts)
        if data is None: return
        contents = [self.small('Шрифт синхронизируется с браузерной версией ЭРА.')]
        for row in data['fonts']:
            suffix = ' ✓' if row['key'] == data['selected'] else ''
            async def save(key=row['key']):
                result = await self.request(self.api.select_font, key)
                if result is not None:
                    self.notify('Шрифт сохранён')
                    await self.chat_fonts()
            contents.append(self.action(row['name'] + suffix, save, ft.Icons.TEXT_FIELDS))
        self.go('Шрифт чата', contents, back=lambda: self.launch(self.profile()), subtitle='Настройка шрифта синхронизируется с веб-версией.')

    async def admin_news_form(self, item=None):
        if not self.current_user().get('is_admin'):
            self.notify('Нет прав администратора'); return
        title = ft.TextField(label='Заголовок', value=(item or {}).get('title', ''))
        content = ft.TextField(label='Текст / HTML', multiline=True, min_lines=4,
                               max_lines=10, value=(item or {}).get('content', ''))
        pinned = ft.Checkbox(label='Закрепить', value=(item or {}).get('pinned', False))
        async def save():
            if item:
                result = await self.request(self.api.admin_news_edit, item['id'], title.value or '',
                                            content.value or '', bool(pinned.value))
            else:
                result = await self.request(self.api.admin_news_create, title.value or '',
                                            content.value or '', bool(pinned.value))
            if result is not None:
                self.notify('Новость сохранена')
                await self.news()
        self.go('Редактор новостей', [title, content, pinned,
                self.action('Сохранить', save, ft.Icons.SAVE, True)],
                back=lambda: self.launch(self.news()))

    async def confirm_news_delete(self, item):
        async def remove():
            result = await self.request(self.api.admin_news_delete, item['id'])
            if result is not None: await self.news()
        self.go('Удалить новость?', [self.text(item['title'], 15),
                self.action('Да, удалить', remove, ft.Icons.DELETE, True),
                self.action('Отмена', self.news)])
