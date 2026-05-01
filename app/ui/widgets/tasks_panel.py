"""Панель найближчих запланованих задач циклу."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout

from sqlalchemy import select

from app.db.models import Account, Niche
from app.db.session import get_session


class TasksPanel(QGroupBox):
    """Показує що буде робити бот найближчим часом.

    Список оновлюється раз на секунду. Враховує час до наступного циклу
    і запланований hourly_schedule по нішах.
    """

    def __init__(self, parent=None) -> None:
        super().__init__("📋 Заплановані задачі", parent)
        self.setStyleSheet(
            "QGroupBox { background:#151515; border:1px solid #2a2a2a; border-radius:6px; margin-top:10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left:10px; color:#4caf50; font-weight:600; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(2)

        self.label = QLabel("Цикл не запущений")
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.label.setStyleSheet("color:#e6e6e6; font-size: 10pt; line-height: 140%;")
        layout.addWidget(self.label, 1)

        self.next_cycle_at: datetime | None = None
        # Раз на 3 сек (раніше 1с — забагато DB-навантаження)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)

    def set_next_cycle(self, when: datetime | None) -> None:
        self.next_cycle_at = when
        self._refresh()

    def _refresh(self) -> None:
        lines: list[str] = []

        # 1. Найближчий tick циклу
        if self.next_cycle_at:
            delta = (self.next_cycle_at - datetime.now(timezone.utc)).total_seconds()
            mins, secs = divmod(max(int(delta), 0), 60)
            lines.append(
                f"⏱ <b>Через {mins:02d}:{secs:02d}</b> — повний цикл: "
                "перевірити проданих, синхронізувати, виконати авто-дії"
            )
        else:
            lines.append("⏸ Цикл не запущений (Меню «Цикл» → «Запустити»)")

        # 2. Заплановані bumps по нішах
        from sqlalchemy import func
        with get_session() as s:
            niches = list(s.execute(select(Niche)).scalars())
            now_hour = datetime.now(timezone.utc).hour

            if not niches:
                lines.append("<i style='color:#9e9e9e'>Ще немає ніш. Створіть нішу через «+ Нова».</i>")

            for n in niches:
                acc_count = s.execute(
                    select(func.count(Account.id)).where(
                        Account.niche_id == n.id,
                        Account.status == "active",
                    )
                ).scalar_one() or 0
                stuck_count = s.execute(
                    select(func.count(Account.id)).where(
                        Account.niche_id == n.id,
                        Account.is_stuck.is_(True),
                        Account.status == "active",
                    )
                ).scalar_one() or 0

                if not (n.auto_bump or n.auto_stick or n.auto_bump_stuck):
                    lines.append(
                        f"⏸ <b>{n.name}</b> ({acc_count} акк): "
                        "<span style='color:#ffc107'>автоматизація вимкнена</span> — "
                        "відкрийте редактор ніші щоб увімкнути авто-bump/stick"
                    )
                    continue

                niche_status: list[str] = [f"<b>{n.name}</b> ({acc_count} акк):"]

                if n.auto_bump:
                    if n.bumps_per_day == 0:
                        niche_status.append(
                            "<span style='color:#ffc107'>🔺 auto-bump увімкнено, але bumps_per_day=0 — задайте число</span>"
                        )
                    else:
                        schedule = list(n.hourly_schedule or [])
                        if len(schedule) == 24 and sum(schedule) > 0:
                            target_so_far = sum(schedule[: now_hour + 1])
                            target_total = sum(schedule)
                            niche_status.append(
                                f"🔺 до {now_hour:02d}:00 — {target_so_far} bump, "
                                f"всього {target_total}/добу"
                            )
                        else:
                            niche_status.append(f"🔺 {n.bumps_per_day} bump/добу (рівномірно)")

                if n.auto_stick and n.stick_slots:
                    if stuck_count < n.stick_slots:
                        niche_status.append(
                            f"📌 закріпити ще {n.stick_slots - stuck_count} акк ({stuck_count}/{n.stick_slots})"
                        )
                    else:
                        niche_status.append(f"📌 закріплено {stuck_count}/{n.stick_slots} ✓")

                if n.auto_bump_stuck and n.stuck_bumps_per_day:
                    niche_status.append(
                        f"🔺📌 bump закріплених {n.stuck_bumps_per_day}/добу"
                    )

                lines.append(" • ".join(niche_status))

        self.label.setText("<br>".join(lines))


