from app.core.niche_manager import NicheFilters
from app.db.models import Account


def _acc(**kwargs) -> Account:
    defaults = dict(
        item_id=1,
        title="Test",
        category="telegram",
        country="UA",
        price=10.0,
        amount=1,
        cost=5.0,
        tags=[],
    )
    defaults.update(kwargs)
    return Account(**defaults)


def test_no_tag_means_no_match():
    """Ниша без tag_id не классифицирует ни один аккаунт."""
    assert not NicheFilters().matches(_acc(tags=[{"id": 42}]))


def test_tag_id_match():
    f = NicheFilters(tag_id=42)
    assert f.matches(_acc(tags=[{"id": 42, "title": "UA"}]))
    assert f.matches(_acc(tags=[{"id": 1}, {"id": 42}]))
    assert not f.matches(_acc(tags=[{"id": 1, "title": "RU"}]))
    assert not f.matches(_acc(tags=[]))


def test_tag_id_robust_to_string_keys():
    f = NicheFilters(tag_id=7)
    assert f.matches(_acc(tags=[{"id": "7", "title": ""}]))
