from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "ua": {
        # Старт
        "choose_lang":      "🦎 Оберіть мову / Выберите язык:",
        "welcome_new":      "🦎 Ласкаво просимо до <b>Лемур</b>!\n\nЦифровий магазин TG-акаунтів.",
        "welcome_back":     "🦎 <b>Лемур</b>\n\nОберіть дію:",
        # Меню
        "btn_shop":         "🛍 Магазин",
        "btn_profile":      "👤 Профіль",
        "btn_referral":     "👥 Реферали",
        "btn_admin":        "⚙️ Адмін",
        "btn_back":         "◀ Назад",
        # Магазин
        "shop_title":       "🛍 <b>Магазин</b>\n\nОберіть категорію:",
        "cat_us":           "🇺🇸 USA акаунти (+1)",
        "cat_ua":           "🇺🇦 Ukraine акаунти (+380)",
        "cat_kz":           "🇰🇿 Kazakhstan акаунти (+7)",
        "no_items":         "😔 Немає доступних акаунтів. Спробуйте пізніше.",
        "buying_wait":      "⏳ Купую акаунт, зачекайте...",
        "buy_error":        "❌ Не вдалось купити цей акаунт. Спробуйте інший.",
        # Видача — два окремих повідомлення
        "phone_msg":        "📱 <b>Ваш номер:</b>\n\n<code>{phone}</code>\n\n⏳ Отримую код...",
        "code_msg": (
            "🔑 <b>Код підтвердження:</b>\n\n"
            "<code>{code}</code>\n\n"
            "📋 <b>Інструкція:</b>\n"
            "1. Відкрийте https://justrunmy.app/panel/add\n"
            "2. Вставте номер <code>{phone}</code>\n"
            "3. Введіть код <code>{code}</code>\n"
            "4. Натисніть <b>Add account</b>\n\n"
            "⚠️ Збережіть дані — вони видаються лише 5 разів."
        ),
        "resend_btn":       "🔄 Надіслати ще раз ({left} з 5)",
        "resend_limit":     "❌ Ліміт вичерпано (5/5).",
        "resend_ok":        "📱 <code>{phone}</code>\n🔑 <code>{code}</code>",
        # Профіль
        "profile_title":    "👤 <b>Профіль</b>",
        "profile_lang":     "🌍 Мова",
        "profile_bal":      "💵 Баланс",
        "profile_orders":   "🛍 Замовлень",
        "btn_change_lang":  "🌍 Змінити мову",
        # Реферали
        "ref_title":        "👥 <b>Реферальна програма</b>",
        "ref_bonus":        "Ваш бонус: <b>+{pct}%</b> з кожної покупки реферала",
        "ref_invited":      "Запрошено: <b>{n}</b> чол.",
        "ref_earned":       "Зароблено: <b>${amt}</b>",
        "ref_link":         "🔗 Ваше посилання:",
        # Адмін
        "admin_title":      "⚙️ <b>Адмін-панель</b>",
        "admin_users":      "👥 Користувачів: <b>{n}</b>",
        "admin_orders":     "🛍 Замовлень: <b>{n}</b>",
        "admin_pending":    "⏳ Очікують: <b>{n}</b>",
        "btn_orders":       "📋 Замовлення",
        "no_access":        "❌ Немає доступу.",
        "orders_list":      "📋 <b>Останні замовлення</b>",
        "btn_deliver":      "✅ Видати вручну",
        "deliver_prompt":   "Введіть дані у форматі:\n<code>+1XXXXXXXXXX\n12345</code>",
        "delivered_ok":     "✅ Замовлення #{id} — видано.",
        "deliver_bad_fmt":  "❌ Формат: номер на першому рядку, код на другому.",
    },
    "ru": {
        "choose_lang":      "🦎 Оберіть мову / Выберите язык:",
        "welcome_new":      "🦎 Добро пожаловать в <b>Лемур</b>!\n\nЦифровой магазин TG-аккаунтов.",
        "welcome_back":     "🦎 <b>Лемур</b>\n\nВыберите действие:",
        "btn_shop":         "🛍 Магазин",
        "btn_profile":      "👤 Профиль",
        "btn_referral":     "👥 Рефералы",
        "btn_admin":        "⚙️ Админ",
        "btn_back":         "◀ Назад",
        "shop_title":       "🛍 <b>Магазин</b>\n\nВыберите категорию:",
        "cat_us":           "🇺🇸 USA аккаунты (+1)",
        "cat_ua":           "🇺🇦 Ukraine аккаунты (+380)",
        "cat_kz":           "🇰🇿 Kazakhstan аккаунты (+7)",
        "no_items":         "😔 Нет доступных аккаунтов. Попробуйте позже.",
        "buying_wait":      "⏳ Покупаю аккаунт, подождите...",
        "buy_error":        "❌ Не удалось купить этот аккаунт. Попробуйте другой.",
        "phone_msg":        "📱 <b>Ваш номер:</b>\n\n<code>{phone}</code>\n\n⏳ Получаю код...",
        "code_msg": (
            "🔑 <b>Код подтверждения:</b>\n\n"
            "<code>{code}</code>\n\n"
            "📋 <b>Инструкция:</b>\n"
            "1. Откройте https://justrunmy.app/panel/add\n"
            "2. Вставьте номер <code>{phone}</code>\n"
            "3. Введите код <code>{code}</code>\n"
            "4. Нажмите <b>Add account</b>\n\n"
            "⚠️ Сохраните данные — выдаётся только 5 раз."
        ),
        "resend_btn":       "🔄 Отправить ещё раз ({left} из 5)",
        "resend_limit":     "❌ Лимит исчерпан (5/5).",
        "resend_ok":        "📱 <code>{phone}</code>\n🔑 <code>{code}</code>",
        "profile_title":    "👤 <b>Профиль</b>",
        "profile_lang":     "🌍 Язык",
        "profile_bal":      "💵 Баланс",
        "profile_orders":   "🛍 Заказов",
        "btn_change_lang":  "🌍 Сменить язык",
        "ref_title":        "👥 <b>Реферальная программа</b>",
        "ref_bonus":        "Ваш бонус: <b>+{pct}%</b> с каждой покупки реферала",
        "ref_invited":      "Приглашено: <b>{n}</b> чел.",
        "ref_earned":       "Заработано: <b>${amt}</b>",
        "ref_link":         "🔗 Ваша ссылка:",
        "admin_title":      "⚙️ <b>Админ-панель</b>",
        "admin_users":      "👥 Пользователей: <b>{n}</b>",
        "admin_orders":     "🛍 Заказов: <b>{n}</b>",
        "admin_pending":    "⏳ Ожидают: <b>{n}</b>",
        "btn_orders":       "📋 Заказы",
        "no_access":        "❌ Нет доступа.",
        "orders_list":      "📋 <b>Последние заказы</b>",
        "btn_deliver":      "✅ Выдать вручную",
        "deliver_prompt":   "Введите данные в формате:\n<code>+1XXXXXXXXXX\n12345</code>",
        "delivered_ok":     "✅ Заказ #{id} — выдан.",
        "deliver_bad_fmt":  "❌ Формат: номер первой строкой, код второй.",
    },
}


def t(lang: str, key: str, **kwargs: object) -> str:
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
