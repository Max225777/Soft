from pathlib import Path

from app.core import niche_manager
from app.core.sale_tracker import sync_accounts_snapshot
from app.db.init import init_db
from app.db.session import get_session


def test_db_smoke(tmp_path: Path):
    db = tmp_path / "smoke.db"
    init_db(db)

    niche = niche_manager.create_niche(
        name="UA Telegram",
        category="telegram",
        country="UA",
        price_min=1.0,
        price_max=100.0,
        keywords="premium",
        default_cost=2.0,
        markup_percent=20.0,
    )
    assert niche.id is not None

    snapshot = [
        {"item_id": 1001, "title": "UA Premium", "category_name": "telegram", "item_origin": "UA", "price": 15.5, "amount": 1, "item_state": "active"},
        {"item_id": 1002, "title": "RU plain", "category_name": "telegram", "item_origin": "RU", "price": 5.0, "amount": 1, "item_state": "active"},
    ]
    summary = sync_accounts_snapshot(snapshot)
    assert summary["added"] == 2

    counts = niche_manager.reclassify_accounts()
    assert counts[niche.id] == 1

    # второй снимок — одного из аккаунтов нет → регистрируем продажу
    summary2 = sync_accounts_snapshot([snapshot[1]])
    assert summary2["sold"] == 1

    with get_session() as s:
        from app.db.models import Sale
        sales = s.query(Sale).all()
        assert len(sales) == 1
        assert sales[0].item_id == 1001
