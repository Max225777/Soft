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
        # Магазин — категорії
        "shop_title":       "🛍 <b>Магазин</b>\n\nОберіть категорію акаунтів:",
        "cat_ua":           "🇺🇦 UA акаунти",
        "cat_kz":           "🇰🇿 KZ акаунти",
        "cat_ru":           "🇷🇺 RU акаунти",
        "no_items":         "😔 Товарів у цій категорії немає.",
        "item_buy":         "Купити",
        "order_contact":    "✅ Замовлення #{id} прийнято!\n\nДля оформлення напишіть адміну: {admin}",
        # Видача акаунту
        "account_data": (
            "✅ <b>Ваше замовлення #{id} виконано!</b>\n\n"
            "📱 Номер: <code>{phone}</code>\n"
            "🔑 Код: <code>{code}</code>\n\n"
            "📋 <b>Інструкція (justrunmy.app):</b>\n"
            "1. Перейдіть на https://justrunmy.app/panel/add\n"
            "2. Вставте номер <code>{phone}</code>\n"
            "3. Введіть код <code>{code}</code>\n"
            "4. Натисніть <b>Add account</b>\n\n"
            "⚠️ Не показуйте ці дані нікому."
        ),
        "resend_btn":       "🔄 Отримати ще раз ({left} з 5)",
        "resend_limit":     "❌ Ліміт запитів вичерпано (5/5).",
        "resend_ok":        "🔑 Дані замовлення #{id}:\n\n📱 <code>{phone}</code>\n🔑 <code>{code}</code>",
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
        "btn_add_item":     "➕ Додати товар",
        "no_access":        "❌ Немає доступу.",
        "orders_list":      "📋 <b>Останні замовлення</b>",
        "btn_deliver":      "✅ Видати",
        "deliver_prompt":   "Введіть дані для видачі у форматі:\n<code>+380XXXXXXXXX\n12345</code>\n\n(перший рядок — номер, другий — код)",
        "delivered_ok":     "✅ Замовлення #{id} — видано.",
        "deliver_bad_fmt":  "❌ Невірний формат. Потрібно:\n<code>+номер\nкод</code>",
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
        "shop_title":       "🛍 <b>Магазин</b>\n\nВыберите категорию аккаунтов:",
        "cat_ua":           "🇺🇦 UA аккаунты",
        "cat_kz":           "🇰🇿 KZ аккаунты",
        "cat_ru":           "🇷🇺 RU аккаунты",
        "no_items":         "😔 В этой категории нет товаров.",
        "item_buy":         "Купить",
        "order_contact":    "✅ Заказ #{id} принят!\n\nДля оформления напишите админу: {admin}",
        "account_data": (
            "✅ <b>Ваш заказ #{id} выполнен!</b>\n\n"
            "📱 Номер: <code>{phone}</code>\n"
            "🔑 Код: <code>{code}</code>\n\n"
            "📋 <b>Инструкция (justrunmy.app):</b>\n"
            "1. Перейдите на https://justrunmy.app/panel/add\n"
            "2. Вставьте номер <code>{phone}</code>\n"
            "3. Введите код <code>{code}</code>\n"
            "4. Нажмите <b>Add account</b>\n\n"
            "⚠️ Не показывайте эти данные никому."
        ),
        "resend_btn":       "🔄 Получить ещё раз ({left} из 5)",
        "resend_limit":     "❌ Лимит запросов исчерпан (5/5).",
        "resend_ok":        "🔑 Данные заказа #{id}:\n\n📱 <code>{phone}</code>\n🔑 <code>{code}</code>",
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
        "btn_add_item":     "➕ Добавить товар",
        "no_access":        "❌ Нет доступа.",
        "orders_list":      "📋 <b>Последние заказы</b>",
        "btn_deliver":      "✅ Выдать",
        "deliver_prompt":   "Введите данные для выдачи в формате:\n<code>+7XXXXXXXXXX\n12345</code>\n\n(первая строка — номер, вторая — код)",
        "delivered_ok":     "✅ Заказ #{id} — выдан.",
        "deliver_bad_fmt":  "❌ Неверный формат. Нужно:\n<code>+номер\nкод</code>",
    },
}


def t(lang: str, key: str, **kwargs: object) -> str:
    text = TEXTS.get(lang, TEXTS["ru"]).get(key, key)
    return text.format(**kwargs) if kwargs else text
