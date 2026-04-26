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
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(1000)

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

            for n in niches:
                if not (n.auto_bump or n.auto_stick or n.auto_bump_stuck):
                    continue
                stuck_count = s.execute(
                    select(func.count(Account.id)).where(
                        Account.niche_id == n.id,
                        Account.is_stuck.is_(True),
                        Account.status == "active",
                    )
                ).scalar_one() or 0

                if n.auto_bump and n.bumps_per_day:
                    schedule = list(n.hourly_schedule or [])
                    if len(schedule) == 24 and sum(schedule) > 0:
                        target_so_far = sum(schedule[: now_hour + 1])
                        target_total = sum(schedule)
                        lines.append(
                            f"🔺 <b>{n.name}</b>: до цієї години — {target_so_far} bump, "
                            f"всього на день {target_total}"
                        )
                    else:
                        lines.append(
                            f"🔺 <b>{n.name}</b>: {n.bumps_per_day} bump/добу (рівномірно)"
                        )

                if n.auto_stick and n.stick_slots:
                    if stuck_count < n.stick_slots:
                        lines.append(
                            f"📌 <b>{n.name}</b>: треба ще закріпити "
                            f"{n.stick_slots - stuck_count} акк (поточно {stuck_count}/{n.stick_slots})"
                        )

                if n.auto_bump_stuck and n.stuck_bumps_per_day:
                    lines.append(
                        f"🔺📌 <b>{n.name}</b>: bump закріплених — {n.stuck_bumps_per_day}/добу "
                        f"(пауза {n.stuck_bump_cooldown_min} хв)"
                    )

        if len(lines) == 1:  # тільки час до циклу
            lines.append("<i style='color:#9e9e9e'>Жодна ніша не має активних авто-дій.</i>")

        self.label.setText("<br>".join(lines))


