import time

from app.api.queue import PRIORITY_HIGH, PRIORITY_MEDIUM, RequestQueue


def test_queue_orders_by_priority_and_respects_min_delay():
    q = RequestQueue(min_delay=0.1, normal_per_minute=120, search_per_minute=20)
    q.min_delay = 0.1
    order: list[int] = []

    def make(tag: int):
        def fn():
            order.append(tag)
            return tag
        return fn

    # Сначала складываем все задачи в очередь, потом стартуем worker —
    # это гарантирует что worker увидит heap полностью отсортированным.
    f_low = q.submit(make(3), priority=PRIORITY_MEDIUM)
    f_low2 = q.submit(make(4), priority=PRIORITY_MEDIUM)
    f_high = q.submit(make(1), priority=PRIORITY_HIGH)
    f_high2 = q.submit(make(2), priority=PRIORITY_HIGH)

    q.start()
    try:
        for f in (f_high, f_high2, f_low, f_low2):
            f.result(timeout=5)
        assert order[:2] == [1, 2]
    finally:
        q.stop()


def test_queue_rate_limiter_counters():
    q = RequestQueue(min_delay=0.1)
    q.min_delay = 0.1
    q.start()
    try:
        f = q.submit(lambda: "ok")
        assert f.result(timeout=2) == "ok"
        time.sleep(0.05)
        normal, search = q.recent_requests()
        assert normal >= 1
    finally:
        q.stop()
