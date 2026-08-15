from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BOT_TOKEN: str = ""
    ADMIN_IDS: list[int] = []

    DATABASE_URL: str = "postgresql+asyncpg://lemur:lemur@localhost:5432/lemur"

    LOLZ_API_TOKEN: str = ""
    LOLZ_API_BASE_URL: str = "https://prod-api.lzt.market/"

    REFERRAL_BONUS_PERCENT: float = 5.0

    WEBAPP_URL: str = ""   # https://your-domain.com — URL задеплоєного Mini App

    CHANNEL_USERNAME: str = "@LEMUR_SHOP"
    SUPPORT_USERNAME: str = "@LEMUR_MANEGER"
    # Публічний канал з відгуками покупців (для банку — реальні відгуки)
    REVIEWS_CHANNEL_USERNAME: str = "@LEMUR_SHOP_REP"
    # E-mail підтримки (необов'язково; якщо порожньо — показуємо лише юзернейм)
    SUPPORT_EMAIL: str = ""
    # Канал-вітрина, куди бот постить кожну покупку (соц-докз для покупців)
    SELL_CHANNEL_USERNAME: str = "@LEMUR_SHOP_SELL"
    # Keywords for tier-2 detection — any match (normalized) alongside lemurshop = tier 2
    # "накрутка" covers UA+RU phrase, "cheap" covers EN phrase
    BIO_PROMO_PHRASE_KEYWORDS: list[str] = ["накрутка", "cheap"]
    # 1 Star ≈ $0.013 (курс при поповненні балансу зірками)
    STAR_DISPLAY_USD: float = 0.013
    # Stars з користувача за $1 ціни товару (= round(1/STAR_DISPLAY_USD))
    STARS_PER_PRODUCT_USD: int = 77
    # Stars за $1 при поповненні через бот-команду /topup
    STARS_PER_USD: int = 77

    CRYPTOBOT_TOKEN: str = ""

    # Heleket (крипто-платіжка, ex-Cryptomus). Обидва значення — з розділу API
    # твого проєкту в дешборді Heleket.
    HELEKET_MERCHANT_ID: str = ""
    HELEKET_API_KEY: str = ""

    # Platega (СБП / карти). MERCHANT_ID + SECRET з дешборду Platega.
    PLATEGA_MERCHANT_ID: str = ""
    PLATEGA_SECRET: str = ""
    # Код методу СБП у Platega (перевір у доках; зазвичай 2). Card = 1.
    PLATEGA_SBP_METHOD: int = 2

    SMMWAY_API_KEY: str = ""
    PREVIEW_MODE: bool = False

    # ─── Fragment (прямий продаж Telegram Stars / Premium) ──────────────────────
    # Куки Fragment беремо по API з LemurPanel (не зберігаємо в себе — протухають).
    LEMURPANEL_URL: str = "https://www.lemurpanel.org"   # база LemurPanel
    SHOP_API_KEY: str = ""            # ключ доступу (надсилається як X-Shop-Key)
    # Точний шлях cookie-API LemurPanel (пробується першим).
    LEMURPANEL_COOKIE_PATH: str = "/api/shop/fragment/cookies"
    # Скільки секунд кешувати куки Fragment (протухають → тримаємо коротко).
    FRAGMENT_COOKIE_TTL: int = 480    # 8 хв
    # Резервні куки Fragment напряму (якщо LemurPanel недоступний) — рядок виду
    # "stel_ssid=...; stel_token=...; stel_dt=...; stel_ton_token=..."
    FRAGMENT_COOKIES_FALLBACK: str = ""
    # User-Agent, з яким ходимо на fragment.com (має збігатися з тим, під яким
    # видані куки — інакше Fragment інвалідуватиме сесію).
    FRAGMENT_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    # ─── Гаманець бота (pytoniq) для оплати Fragment ────────────────────────────
    WALLET_SEED: str = ""             # 24 слова мнемоніки гаманця бота (через пробіл)
    # Jetton-master USDT у мережі TON (mainnet).
    USDT_JETTON_MASTER: str = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
    # TON API endpoint для pytoniq LiteClient (порожньо = глобальний конфіг mainnet).
    TON_CONFIG_URL: str = "https://ton.org/global.config.json"
    # Запобіжник: макс. сума однієї покупки в TON (щоб не злити гаманець при баге).
    FRAGMENT_MAX_TON_PER_BUY: float = 20.0
    # Сухий прогін: рахуємо/логуємо все, але НЕ шлемо TON (для тестів).
    FRAGMENT_DRY_RUN: bool = True

    # ─── Ціноутворення продажу Stars / Premium ──────────────────────────────────
    # Оплата Fragment у USDT (стейбл) → собівартість фіксована в $, курс TON не
    # впливає. Єдине в TON — газ за переказ (~$0.05/тx), його покриває фікс. збір.
    # Собівартість з Fragment (звіряй періодично на fragment.com):
    FRAGMENT_STAR_COST_USD: float = 0.015          # 50⭐ = $0.75
    FRAGMENT_PREMIUM_3M_COST_USD: float = 11.99
    FRAGMENT_PREMIUM_6M_COST_USD: float = 15.99
    FRAGMENT_PREMIUM_12M_COST_USD: float = 28.99
    # Націнка на зірки: маржа у % + невеликий фікс. збір на газ TON.
    FRAGMENT_STARS_MARGIN_PCT: float = 10.0        # ~10% прибутку
    FRAGMENT_STARS_FEE_USD: float = 0.05
    # Націнка Premium: рівно +$2 (собівартість у USDT стабільна).
    FRAGMENT_PREMIUM_MARKUP_USD: float = 2.00
    # Валюта оплати Fragment: USDT / USDC / TON.
    FRAGMENT_PAY_CURRENCY: str = "USDT"
    # Проксі для запитів до fragment.com (residential), напр.
    # http://user:pass@host:port — Fragment часто блокує покупки з серверних IP.
    FRAGMENT_PROXY: str = ""


settings = Settings()
