from __future__ import annotations

import asyncio
import json
import httpx
import logging

from lemur_shop.api.lolz import LolzApiError, lolz
from lemur_shop.config import settings

log = logging.getLogger(__name__)

# Конфіг категорій
# macro=True  → USA-style: ітеративний pmin-bump при чорному списку
#   pmax        — максимальна ціна покупки на lolz
#   pmin_start  — стартовий pmin (None = без обмеження знизу)
#   macro_steps — кількість макро-ітерацій
#   micro_attempts — спроб купівлі за ітерацію
# pmax_tiers  → стандартний режим: перебираємо тири pmax
CATEGORIES: dict[str, dict] = {
    "us": {
        "country": "US", "title": "USA", "title_ru": "США", "title_ua": "США",
        "flag": "🇺🇸", "phone_prefix": "+1",
        "price_usd": 0.65,
        "macro": True, "pmax": 0.50, "pmin_start": None,
        "pmin_fallbacks": [0.30, 0.35], "micro_attempts": 15,
    },
    "mm": {
        "country": "MM", "title": "Myanmar", "title_ru": "Мьянма", "title_ua": "М'янма",
        "flag": "🇲🇲", "phone_prefix": "+95",
        "price_usd": 0.65,
        "macro": True, "pmax": 0.40, "pmin_start": 0.20,
        "pmin_fallbacks": [0.30, 0.35], "micro_attempts": 15,
    },
    "co": {
        "country": "CO", "title": "Colombia", "title_ru": "Колумбия", "title_ua": "Колумбія",
        "flag": "🇨🇴", "phone_prefix": "+57",
        "price_usd": 0.78,
        "pmax_tiers": [0.60], "pmin": 0.30,
    },
    "de": {
        "country": "DE", "title": "Germany", "title_ru": "Германия", "title_ua": "Німеччина",
        "flag": "🇩🇪", "phone_prefix": "+49",
        "price_usd": 1.95,
        "macro": True, "pmax": 1.50, "pmin_start": None,
        "pmin_fallbacks": [1.00, 1.25], "micro_attempts": 15,
    },
    "ua": {
        "country": "UA", "title": "Ukraine", "title_ru": "Украина", "title_ua": "Україна",
        "flag": "🇺🇦", "phone_prefix": "+380",
        "price_usd": 3.25,
        "pmax_tiers": [2.50],
    },
    "kz": {
        "country": "KZ", "title": "Kazakhstan", "title_ru": "Казахстан", "title_ua": "Казахстан",
        "flag": "🇰🇿", "phone_prefix": "+7",
        "price_usd": 3.25,
        "pmax_tiers": [1.50, 2.00],
    },
}

# Тимчасово приховані категорії — не показуються в магазині й недоступні для
# покупки (UI не рендерить плашку, /buy повертає помилку). Щоб повернути —
# прибрати код країни з набору.
DISABLED_CATEGORIES: set[str] = {"ua"}


# ═══════════════════════════════════════════════════════════════════════════════
#  ОВЕРАЙДИ КАТЕГОРІЙ (керуються з адмін-панелі, зберігаються в БД)
#  Для кожної категорії адмін може задати:
#    pmin        — мінімальна ціна закупки на lolz (нижня межа пошуку)
#    pmax        — максимальна ціна закупки на lolz (верхня межа / ліміт)
#    price_stars — ціна продажу користувачу (у ⭐)
#  Порожнє значення (None) = використовувати дефолт із CATEGORIES.
# ═══════════════════════════════════════════════════════════════════════════════
_OVERRIDES_KEY = "category_overrides"
_OVERRIDES: dict[str, dict] = {}


async def load_overrides() -> None:
    """Завантажує оверайди з БД у памʼять. Викликається на старті та після зміни."""
    global _OVERRIDES
    try:
        from lemur_shop.db.models import AppSetting
        from lemur_shop.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            row = await s.get(AppSetting, _OVERRIDES_KEY)
        if row and row.value:
            data = json.loads(row.value)
            if isinstance(data, dict):
                _OVERRIDES = {k: v for k, v in data.items() if isinstance(v, dict)}
                log.info("Category overrides loaded: %s", list(_OVERRIDES) or "none")
                return
    except Exception as e:
        log.warning("load_overrides failed: %s", e)
    _OVERRIDES = {}


def get_overrides() -> dict[str, dict]:
    return _OVERRIDES


async def save_category_override(code: str, *, pmin, pmax, price_stars) -> dict:
    """Зберігає/очищає оверайди категорії. None у полі → прибрати оверайд цього поля."""
    if code not in CATEGORIES:
        raise ValueError("unknown category")
    cur = dict(_OVERRIDES.get(code) or {})
    for field, val in (("pmin", pmin), ("pmax", pmax), ("price_stars", price_stars)):
        if val is None:
            cur.pop(field, None)
        else:
            cur[field] = val
    data = {k: dict(v) for k, v in _OVERRIDES.items()}
    if cur:
        data[code] = cur
    else:
        data.pop(code, None)

    from lemur_shop.db.models import AppSetting
    from lemur_shop.db.session import AsyncSessionLocal
    payload = json.dumps(data)
    async with AsyncSessionLocal() as s:
        async with s.begin():
            row = await s.get(AppSetting, _OVERRIDES_KEY)
            if row:
                row.value = payload
            else:
                s.add(AppSetting(key=_OVERRIDES_KEY, value=payload))
    await load_overrides()
    log.info("Category override saved for %s: %s", code, cur or "cleared")
    return _OVERRIDES.get(code, {})


def effective_category(code: str) -> dict | None:
    """Базовий конфіг категорії з накладеними оверайдами адміна."""
    base = CATEGORIES.get(code)
    if not base:
        return None
    eff = dict(base)
    ov = _OVERRIDES.get(code) or {}
    pmax = ov.get("pmax")
    pmin = ov.get("pmin")
    if pmax is not None:
        eff["pmax"] = pmax
        if "pmax_tiers" in eff:
            eff["pmax_tiers"] = [pmax]
    if pmin is not None:
        if eff.get("macro"):
            eff["pmin_start"] = pmin
        else:
            eff["pmin"] = pmin
    if ov.get("price_stars") is not None:
        eff["price_stars_override"] = ov["price_stars"]
    return eff


def sell_price_stars(code: str) -> int:
    """Ціна продажу користувачу у ⭐ з урахуванням оверайда/знижки."""
    eff = effective_category(code)
    if not eff:
        return 0
    if eff.get("price_stars_override") is not None:
        return int(eff["price_stars_override"])
    if eff.get("discount_stars"):
        return int(eff["discount_stars"])
    return round(eff["price_usd"] / settings.STAR_DISPLAY_USD)


def category_defaults(code: str) -> dict:
    """Кодові (дефолтні) значення pmin/pmax/price_stars — для показу в адмінці."""
    base = CATEGORIES.get(code) or {}
    if base.get("macro"):
        d_pmin = base.get("pmin_start")
        d_pmax = base.get("pmax")
    else:
        d_pmin = base.get("pmin")
        d_pmax = (base.get("pmax_tiers") or [None])[0]
    d_price = base.get("discount_stars") or round(base.get("price_usd", 0) / settings.STAR_DISPLAY_USD)
    return {"pmin": d_pmin, "pmax": d_pmax, "price_stars": d_price}


def effective_bounds(code: str) -> dict:
    """Поточні діючі pmin/pmax (з оверайдами) — для показу в адмінці."""
    eff = effective_category(code) or {}
    if eff.get("macro"):
        return {"pmin": eff.get("pmin_start"), "pmax": eff.get("pmax")}
    return {"pmin": eff.get("pmin"), "pmax": (eff.get("pmax_tiers") or [None])[0]}


async def check_stock(country: str, pmax: float, pmin: float | None) -> dict:
    """Живий пошук для адмін-кнопки «Перевірити». Скільки акаунтів знайдено зараз."""
    items = await lolz.search_telegram(
        country=country, pmax=pmax, pmin=pmin, count=100,
        spam="no", password="no",
    )
    prices = sorted(float(i.get("price") or i.get("price_usd") or 0) for i in items)
    return {
        "count": len(items),
        "cheapest": round(prices[0], 2) if prices else None,
        "most_expensive": round(prices[-1], 2) if prices else None,
        "sample": [round(p, 2) for p in prices[:6]],
    }


async def _search_with_pmax(country: str, pmax: float, limit: int = 10) -> list[dict]:
    try:
        return await lolz.search_telegram(country=country, pmax=pmax, count=limit)
    except LolzApiError:
        return []


async def search_accounts(category: str, limit: int = 8) -> list[dict]:
    cat = effective_category(category)
    if not cat:
        return []
    country = cat["country"]
    for pmax in cat.get("pmax_tiers", [cat.get("pmax", 2.50)]):
        items = await _search_with_pmax(country, pmax, limit)
        if items:
            return items
    return []


async def auto_buy(item_id: int, price: float) -> str:
    """Купує акаунт і повертає телефон."""
    try:
        item = await lolz.fast_buy(item_id, price)
    except httpx.ReadTimeout:
        log.warning("fast_buy timeout for #%s, trying get_item", item_id)
        item = await lolz.get_item(item_id)

    phone = str(item.get("telegram_phone") or "").strip()
    if phone and not phone.startswith("+"):
        phone = "+" + phone

    if not phone:
        item = await lolz.get_item(item_id)
        phone = str(item.get("telegram_phone") or "").strip()
        if phone and not phone.startswith("+"):
            phone = "+" + phone

    if not phone:
        raise ValueError(f"Phone not found in item #{item_id}. Keys: {list(item.keys())}")

    log.info("Bought item #%s, phone=%r", item_id, phone)
    return phone


SKIP_ERRORS = (
    "user_inactive", "already_sold", "item_sold", "not_found", "forbidden",
    "invalid_account", "account_not_valid", "verification", "check_failed",
    "account_invalid", "phone_banned", "banned", "spam", "deactivated",
    "проверк",
    "ошибок во",
    "более 20",
)

BLACKLIST_MSG = "черный список"


async def _try_buy_batch(
    items: list[dict], max_cost: float, micro_limit: int
) -> tuple[tuple[str, int, float] | None, float]:
    """Пробує купити з батчу.
    Повертає (result_or_None, max_blacklisted_price).
    """
    micro = 0
    max_bl_price: float = 0.0
    for item in items:
        if micro >= micro_limit:
            break
        item_id = int(item.get("item_id") or item.get("id"))
        lolz_price = float(item.get("price") or item.get("price_usd") or 0)
        if lolz_price > max_cost:
            break
        micro += 1
        try:
            phone = await auto_buy(item_id, lolz_price)
            return (phone, item_id, lolz_price), max_bl_price
        except (LolzApiError, ValueError) as e:
            err_text = str(e).lower()
            is_blacklist = BLACKLIST_MSG in str(e)
            is_skip = any(skip in err_text for skip in SKIP_ERRORS) or (
                isinstance(e, LolzApiError) and e.status == 403
            )
            if is_skip:
                if is_blacklist:
                    max_bl_price = max(max_bl_price, lolz_price)
                log.warning("Item #%s skipped (%s), micro %d/%d", item_id, e, micro, micro_limit)
                continue
            raise
    return None, max_bl_price


async def _macro_buy(cat: dict) -> tuple[str, int, float]:
    """Macro-цикл для категорій з macro=True (USA, Myanmar тощо).

    Йдемо по ступенях мінімальної ціни (pmin): спершу без нижньої межі,
    потім — явні "підлоги" з ``pmin_fallbacks`` (напр. 0.30, потім 0.35).
    Найдешевші акаунти найчастіше в чорному списку / не купуються, тож якщо
    з поточним pmin купити не вдалося — піднімаємо поріг і беремо трохи
    дорожчі, "живіші" акаунти. Кожна ступінь фіксується у звіті, який
    потрапляє в Telegram-алерт адміну.
    """
    country   = cat["country"]
    pmax      = cat["pmax"]
    micro_att = cat.get("micro_attempts", 15)

    # Ступені нижньої межі: старт (може бути None = без межі) + явні фолбеки.
    # Фолбеки нижче стартового порога відкидаємо (напр. якщо адмін підняв pmin).
    _start = cat.get("pmin_start")
    _fallbacks = [f for f in cat.get("pmin_fallbacks", []) if _start is None or f > _start]
    pmin_tiers: list[float | None] = [_start] + _fallbacks

    seen_total       = 0             # скільки item-ів взагалі повернув пошук
    cheapest_overall = float("inf")  # найдешевший знайдений (для діагностики)
    report: list[str] = []           # порядок дій — піде адміну в алерт

    for step, pmin in enumerate(pmin_tiers):
        # pmin, що перевищує pmax, робити немає сенсу
        if pmin is not None and pmin >= pmax:
            report.append(f"pmin≥${pmin:.2f}: пропущено (≥ ліміту ${pmax:.2f})")
            continue

        items: list[dict] = []
        for attempt in range(3):
            try:
                items = await lolz.search_telegram(
                    country=country, pmax=pmax, pmin=pmin, count=50,
                    spam="no", password="no",
                )
                break
            except (LolzApiError, httpx.TimeoutException) as e:
                log.warning("%s step %d search attempt %d failed: %s (%s)",
                            country, step, attempt + 1, type(e).__name__, e)
                if attempt < 2:
                    await asyncio.sleep(2)

        pmin_lbl = f"${pmin:.2f}" if pmin is not None else "—"
        if not items:
            log.info("%s step %d: no items at pmin=%s pmax=%.2f", country, step, pmin, pmax)
            report.append(f"pmin={pmin_lbl}: знайдено 0")
            continue

        items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
        seen_total += len(items_sorted)
        _cheapest = float(items_sorted[0].get("price") or items_sorted[0].get("price_usd") or 0)
        cheapest_overall = min(cheapest_overall, _cheapest)

        log.info("%s step %d: %d items, cheapest=%.2f (pmin=%s pmax=%.2f)",
                 country, step, len(items_sorted), _cheapest, pmin, pmax)

        result, max_bl_price = await _try_buy_batch(items_sorted, max_cost=pmax, micro_limit=micro_att)
        if result:
            return result

        report.append(
            f"pmin={pmin_lbl}: {len(items_sorted)} шт (від ${_cheapest:.2f}) — купити не вдалося"
        )
        log.info("%s step %d: %d items but none purchasable (blacklist up to %.2f)",
                 country, step, len(items_sorted), max_bl_price)

    # Всі ступені вичерпані — формуємо звіт для адміна.
    report_txt = "; ".join(report) if report else "спроб не було"
    if seen_total == 0:
        raise LolzApiError(
            f"Пошук не повернув жодного акаунта {country} "
            f"(pmax=${pmax:.2f}, origin=autoreg+self_registration, spam=no, password=no). "
            f"Схоже, в наявності немає акаунтів цих origin за цією ціною — "
            f"варто підняти pmax або розширити origin. Ступені: {report_txt}"
        )
    raise LolzApiError(
        f"Знайдено {seen_total} акаунтів {country} (найдешевший ${cheapest_overall:.2f}, "
        f"ліміт ${pmax:.2f}), але жоден не вдалося купити (чорний список / 403 / продано). "
        f"Ступені: {report_txt}"
    )


async def auto_buy_category(category: str) -> tuple[str, int, float]:
    cat = effective_category(category)
    if not cat:
        raise LolzApiError("Unknown category")

    if cat.get("macro"):
        return await _macro_buy(cat)

    # ── Стандартний режим: тири pmax ──────────────────────────────────────────
    country    = cat["country"]
    shop_price = cat.get("price_usd", 9999)
    tiers: list[float] = cat.get("pmax_tiers", [2.50])
    pmin = cat.get("pmin")
    items: list[dict] = []
    for pmax in tiers:
        try:
            items = await lolz.search_telegram(country=country, pmax=pmax, pmin=pmin, count=50, spam="no")
        except (LolzApiError, httpx.TimeoutException):
            items = []
        if items:
            log.info("Found %d accounts for %s at pmax=%.2f", len(items), category, pmax)
            break
        log.info("No accounts for %s at pmax=%.2f, trying next tier", category, pmax)

    if not items:
        raise LolzApiError("No accounts available in this category")

    items_sorted = sorted(items, key=lambda x: float(x.get("price") or x.get("price_usd") or 999))
    log.info("Price range for %s: top5=%s", category,
             [float(i.get("price") or i.get("price_usd") or 0) for i in items_sorted[:5]])

    result, _ = await _try_buy_batch(items_sorted, max_cost=shop_price, micro_limit=5)
    if result:
        return result

    raise LolzApiError("No purchasable accounts found after trying all candidates")
