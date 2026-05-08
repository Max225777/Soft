"""Мінімальний UI: одна форма + лог.

Функціонал:
- обрати приватний тег
- задати скільки bump за один цикл, скільки всього за добу, інтервал циклу
- 3 чекбокси фільтру спамблоку
- кнопка ▶ Запустити / ⏸ Зупинити
- блок прогресу + журнал останніх дій
"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import desc, func, select

from app.api.client import LolzMarketClient
from app.core import niche_manager
from app.core.tags import fetch_tags
from app.db.models import Account, ActionLog, Niche
from app.db.session import get_session
from app.services import settings_store
from app.ui.widgets.async_worker import AsyncCall


SINGLE_NICHE_NAME = "Default"


class SimpleForm(QWidget):
    def __init__(self, client: LolzMarketClient, trigger_refresh, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.trigger_refresh = trigger_refresh
        self._tags_cache: list[dict] = []
        self._tags_call: AsyncCall | None = None
        self._prune_legacy_niches()
        self._build_ui()
        self._load_state()
        QTimer.singleShot(100, self._reload_tags)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(3000)

    @staticmethod
    def _prune_legacy_niches() -> None:
        """Прибираємо всі ніші окрім «Default» — мінімалістичний UI."""
        with get_session() as s:
            old = list(s.execute(select(Niche).where(Niche.name != SINGLE_NICHE_NAME)).scalars())
            for o in old:
                logger.info("Видаляю стару нішу '{}' (id={}) — мінімалістичний UI", o.name, o.id)
                s.delete(o)
            if old:
                s.commit()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Top toolbar
        top = QHBoxLayout()
        top.addWidget(QLabel("<h2>Lolzteam Bumper</h2>"))
        top.addStretch()
        btn_fetch = QPushButton("🔄 Оновити з API")
        btn_fetch.clicked.connect(self._fetch_now)
        top.addWidget(btn_fetch)
        btn_settings = QPushButton("⚙ Налаштування")
        btn_settings.clicked.connect(self._open_settings)
        top.addWidget(btn_settings)
        root.addLayout(top)

        # ---- Параметри ----
        params = QGroupBox("Параметри підйомів")
        form = QFormLayout(params)

        tag_row = QHBoxLayout()
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("— завантаження тегів… —", None)
        tag_row.addWidget(self.tag_combo, 1)
        btn_reload_tags = QPushButton("🔄")
        btn_reload_tags.setToolTip("Оновити список тегів з API")
        btn_reload_tags.clicked.connect(self._reload_tags)
        tag_row.addWidget(btn_reload_tags)
        form.addRow("Приватний тег:", tag_row)

        self.bumps_per_tick_spin = QSpinBox()
        self.bumps_per_tick_spin.setRange(1, 1000)
        self.bumps_per_tick_spin.setValue(5)
        form.addRow("Аккаунтів за раз (на цикл):", self.bumps_per_tick_spin)

        self.bumps_per_day_spin = QSpinBox()
        self.bumps_per_day_spin.setRange(0, 100000)
        self.bumps_per_day_spin.setValue(0)
        form.addRow("Макс за добу (0 = без обмеження):", self.bumps_per_day_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setValue(20)
        self.interval_spin.setSuffix(" хв")
        form.addRow("Інтервал циклу:", self.interval_spin)

        root.addWidget(params)

        # ---- Фільтр спамблоку ----
        filt = QGroupBox("Фільтр спамблоку")
        fb = QVBoxLayout(filt)
        self.chk_skip_spam = QCheckBox("Не піднімати акк зі спамблоком (telegram_spam_block ≥ 1)")
        fb.addWidget(self.chk_skip_spam)
        hint_filt = QLabel(
            "<i>Якщо галочка стоїть — програма пропускає акк лише з telegram_spam_block "
            "= 0 (чисто) або = -1 (не перевірено). Все що ≥1 (включно з гео-спамблоком) — "
            "пропускаємо. Якщо галочки немає — піднімаємо всіх.</i>"
        )
        hint_filt.setWordWrap(True)
        hint_filt.setStyleSheet("color:#9e9e9e; font-size:10pt;")
        fb.addWidget(hint_filt)
        root.addWidget(filt)

        # ---- Старт/Стоп ----
        ctrl = QHBoxLayout()
        self.btn_toggle = QPushButton("▶ Запустити підйоми")
        self.btn_toggle.setObjectName("primary")
        self.btn_toggle.setMinimumHeight(38)
        self.btn_toggle.clicked.connect(self._toggle_running)
        ctrl.addWidget(self.btn_toggle, 1)
        root.addLayout(ctrl)

        # ---- Прогрес ----
        self.status_label = QLabel("Не запущено")
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "padding:10px; background:#1f1f1f; border:1px solid #2a2a2a; "
            "border-radius:6px; font-size:11pt;"
        )
        root.addWidget(self.status_label)

        # ---- Журнал ----
        log_box = QGroupBox("Журнал останніх дій")
        log_lay = QVBoxLayout(log_box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background:#0e0e0e; color:#cfcfcf; font-family: Consolas, monospace; font-size:10pt;")
        self.log_view.setMinimumHeight(180)
        log_lay.addWidget(self.log_view)
        root.addWidget(log_box, 1)

    # ---------- state ----------
    def _get_or_create_niche(self) -> Niche:
        with get_session() as s:
            niche = s.execute(
                select(Niche).where(Niche.name == SINGLE_NICHE_NAME)
            ).scalar_one_or_none()
            if niche is None:
                niche = Niche(name=SINGLE_NICHE_NAME, auto_bump=False, bumps_per_tick=5)
                s.add(niche)
                s.commit()
                s.refresh(niche)
            return niche

    def _load_state(self) -> None:
        n = self._get_or_create_niche()
        self.bumps_per_tick_spin.setValue(n.bumps_per_tick or 5)
        self.bumps_per_day_spin.setValue(n.bumps_per_day or 0)
        sf = n.spamblock_filter or {}
        self.chk_skip_spam.setChecked(bool(sf.get("skip_spamblock")))
        # Інтервал — глобальний
        win = self.window()
        settings = getattr(win, "settings", None)
        if settings is not None:
            self.interval_spin.setValue(int(settings.cycle_interval_minutes or 20))
        self._update_toggle_button(n.auto_bump)

    def _update_toggle_button(self, running: bool) -> None:
        if running:
            self.btn_toggle.setText("⏸ Зупинити підйоми")
            self.btn_toggle.setObjectName("danger")
        else:
            self.btn_toggle.setText("▶ Запустити підйоми")
            self.btn_toggle.setObjectName("primary")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)

    # ---------- tags ----------
    def _reload_tags(self) -> None:
        if self._tags_call is not None:
            try:
                self._tags_call.cancel()
            except Exception:  # noqa: BLE001
                pass
        self.tag_combo.clear()
        self.tag_combo.addItem("— завантаження тегів… —", None)
        self._tags_call = AsyncCall(
            fetch_tags, self.client,
            on_done=self._tags_loaded,
            on_error=self._tags_failed,
            parent=self,
        )
        self._tags_call.start()

    def _tags_loaded(self, tags) -> None:
        tags = list(tags or [])
        self._tags_cache = tags
        n = self._get_or_create_niche()
        current = n.tag_id

        self.tag_combo.clear()
        self.tag_combo.addItem("— оберіть тег —", None)
        seen = set()
        for t in tags:
            tid = int(t["id"])
            seen.add(tid)
            label = f"#{tid}  {t.get('title') or ''}".strip()
            if t.get("isDefault"):
                label += "  (default)"
            self.tag_combo.addItem(label, tid)
        # Якщо в ніші вже є тег а в API його не повернули — додаємо синтетично
        if current and int(current) not in seen:
            self.tag_combo.addItem(f"#{current}  {n.tag_name or ''}".strip(), int(current))
        if current:
            idx = self.tag_combo.findData(int(current))
            if idx >= 0:
                self.tag_combo.setCurrentIndex(idx)

    def _tags_failed(self, exc: Exception) -> None:
        logger.error("SimpleForm: помилка завантаження тегів: {}", exc)
        self.tag_combo.clear()
        self.tag_combo.addItem(f"⚠ помилка: {exc}", None)

    # ---------- actions ----------
    def _toggle_running(self) -> None:
        n = self._get_or_create_niche()
        try:
            if n.auto_bump:
                self._save_form(running=False)
                self.window().statusBar().showMessage("Підйоми зупинено", 4000)
            else:
                tag_id = self.tag_combo.currentData()
                if tag_id is None:
                    QMessageBox.warning(self, "Немає тегу", "Спочатку оберіть приватний тег зі списку.")
                    return
                self._save_form(running=True)
                self.window().statusBar().showMessage("Підйоми запущено", 4000)
                # Запуск негайного циклу
                try:
                    self.trigger_refresh()
                except Exception:  # noqa: BLE001
                    pass
            self._load_state()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Помилка зміни стану: {}", exc)
            QMessageBox.warning(self, "Помилка", str(exc))

    def _save_form(self, running: bool) -> None:
        tag_id = self.tag_combo.currentData()
        tag_title = ""
        if tag_id is not None:
            for t in self._tags_cache:
                if int(t["id"]) == int(tag_id):
                    tag_title = t.get("title") or ""
                    break

        spam_filter = {
            "skip_spamblock": self.chk_skip_spam.isChecked(),
        }

        n = self._get_or_create_niche()
        niche_manager.update_niche(
            n.id,
            tag_id=int(tag_id) if tag_id is not None else None,
            tag_name=tag_title,
            auto_bump=running,
            bumps_per_tick=int(self.bumps_per_tick_spin.value()),
            bumps_per_day=int(self.bumps_per_day_spin.value()),
            spamblock_filter=spam_filter,
        )

        # Зберігаємо інтервал у налаштуваннях додатку
        win = self.window()
        if hasattr(win, "settings"):
            new_interval = int(self.interval_spin.value())
            win.settings.cycle_interval_minutes = new_interval
            settings_store.set_kv("cycle_interval_minutes", str(new_interval))
            # Перезапуск циклу з новим інтервалом
            cycle = getattr(win, "cycle", None)
            if cycle is not None:
                cycle.interval_minutes = new_interval
                cycle.stop()
                cycle.start(run_now=running)

        # Перекласифікація щоб ніша одразу побачила свої акк
        niche_manager.reclassify_accounts()

    def _fetch_now(self) -> None:
        try:
            self.trigger_refresh()
            self.window().statusBar().showMessage("Запит до API… акаунти оновляться через хвилину", 8000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Помилка", str(exc))

    def _open_settings(self) -> None:
        win = self.window()
        if hasattr(win, "_open_settings"):
            win._open_settings()  # noqa: SLF001

    # ---------- status & log ----------
    def _refresh_status(self) -> None:
        try:
            from app.core.cycle import _matches_spamblock_filter

            n = self._get_or_create_niche()
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            with get_session() as s:
                acc_total = s.execute(
                    select(func.count(Account.id)).where(Account.status == "active")
                ).scalar_one() or 0
                in_niche_accounts = list(s.execute(
                    select(Account).where(
                        Account.niche_id == n.id,
                        Account.status == "active",
                    )
                ).scalars())
                in_niche = len(in_niche_accounts)
                ready = sum(1 for a in in_niche_accounts if a.bumps_available > 0)
                ready_after_filter = sum(
                    1 for a in in_niche_accounts
                    if a.bumps_available > 0 and _matches_spamblock_filter(a, n.spamblock_filter)
                )
                # Breakdown по telegram_spam_block у нішевих акк
                sb_counts = {"clean": 0, "spamblock": 0, "geo": 0, "unchecked": 0, "unknown": 0}
                for a in in_niche_accounts:
                    raw = a.raw or {}
                    sb = raw.get("telegram_spam_block")
                    if sb is None:
                        sb_counts["unknown"] += 1
                    else:
                        try:
                            sb_int = int(sb)
                        except (TypeError, ValueError):
                            sb_counts["unknown"] += 1
                            continue
                        if sb_int == 0:
                            sb_counts["clean"] += 1
                        elif sb_int == -1:
                            sb_counts["unchecked"] += 1
                        elif sb_int == 1:
                            sb_counts["spamblock"] += 1
                        else:
                            sb_counts["geo"] += 1
                bumps_today = s.execute(
                    select(func.count(ActionLog.id)).where(
                        ActionLog.action == "bump",
                        ActionLog.level == "INFO",
                        ActionLog.created_at >= today_start,
                    )
                ).scalar_one() or 0

            status = "🟢 Запущено" if n.auto_bump else "⏸ Зупинено"
            limit_str = f"{n.bumps_per_day}" if n.bumps_per_day else "∞"
            tag_str = f"#{n.tag_id} {n.tag_name}" if n.tag_id else "не обрано"
            filter_active = any((n.spamblock_filter or {}).values())
            ready_line = (
                f"готові до bump: <b>{ready_after_filter}</b> з {ready} (фільтр)"
                if filter_active else
                f"готові до bump: <b>{ready}</b>"
            )
            sb_breakdown = (
                f"<span style='color:#9e9e9e'>Спамблок: "
                f"<span style='color:#4caf50'>чистих {sb_counts['clean']}</span>, "
                f"непровірено {sb_counts['unchecked']}, "
                f"<span style='color:#f44336'>з блоком {sb_counts['spamblock']}</span>, "
                f"гео {sb_counts['geo']}"
                + (f", невідомо {sb_counts['unknown']}" if sb_counts["unknown"] else "")
                + "</span>"
            )
            self.status_label.setText(
                f"<b>{status}</b>  |  Тег: <b>{tag_str}</b><br>"
                f"Bump сьогодні: <b style='color:#4caf50'>{bumps_today}</b> / {limit_str}<br>"
                f"У тегу акк: <b>{in_niche}</b>  |  {ready_line}  |  "
                f"всього на продажі: {acc_total}<br>"
                f"{sb_breakdown}"
            )

            # Журнал — підтягуємо title акаунту (через outerjoin по item_id)
            with get_session() as s:
                rows = list(s.execute(
                    select(ActionLog, Account.title)
                    .outerjoin(Account, Account.item_id == ActionLog.item_id)
                    .order_by(desc(ActionLog.created_at))
                    .limit(50)
                ))
            lines = []
            for log_row, title in rows:
                t = log_row.created_at.strftime("%H:%M:%S") if log_row.created_at else "??"
                emoji = "✓" if log_row.level == "INFO" else ("⚠" if log_row.level == "WARNING" else "✗")
                # Імʼя акаунта (перші 50 символів) замість item_id
                if title:
                    name = title[:50]
                elif log_row.item_id:
                    name = f"#{log_row.item_id}"
                else:
                    name = "—"
                lines.append(f"{t}  {emoji}  {log_row.action:<8} {name}  {log_row.message[:60]}")
            self.log_view.setPlainText("\n".join(lines))
        except Exception:  # noqa: BLE001
            logger.exception("SimpleForm._refresh_status")

    def reload(self) -> None:
        """Сумісність з MainWindow._refresh_ui.

        ВАЖЛИВО: НЕ перезавантажуємо поля форми (_load_state) —
        інакше періодичний таймер MainWindow затирав би дані які
        користувач щойно ввів. _load_state викликається лише раз —
        у __init__. Сюди — лише оновлення статусу і журналу.
        """
        self._refresh_status()
