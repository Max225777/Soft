from app.core.niche_manager import NicheFilters
from app.db.models import Account


def _acc(**kwargs) -> Account:
    defaults = dict(item_id=1, title="Test", category="telegram", country="UA", price=10.0, amount=1, cost=5.0)
    defaults.update(kwargs)
    return Account(**defaults)


def test_empty_filter_matches_anything():
    assert NicheFilters().matches(_acc())


def test_category_filter():
    f = NicheFilters(category="telegram")
    assert f.matches(_acc(category="telegram"))
    assert not f.matches(_acc(category="steam"))


def test_price_range():
    f = NicheFilters(price_min=5, price_max=20)
    assert f.matches(_acc(price=10))
    assert not f.matches(_acc(price=3))
    assert not f.matches(_acc(price=25))


def test_keywords_match_any():
    f = NicheFilters(keywords="premium, verified")
    assert f.matches(_acc(title="Telegram Premium aged"))
    assert f.matches(_acc(title="Verified seller"))
    assert not f.matches(_acc(title="plain account"))
