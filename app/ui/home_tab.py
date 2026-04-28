"""Вкладка «Главная»: ниши + аккаунты + массовые действия."""

from __future__ import annotations

from typing import Callable

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from app.api.client import LolzMarketClient
from app.core import bulk_actions, niche_manager
from app.db.models import Account
from app.db.session import get_session
from app.ui.niche_editor import NicheEditor
from app.ui.widgets.accounts_table import AccountsTable
from app.ui.widgets.niche_card import NicheCard


UNCLASSIFIED_ID = -1  # псевдо-ID для «Без классификации»


class HomeTab(QWidget):
    def __init__(
        self,
        client: LolzMarketClient,
        trigger_refresh: Callable[[], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.trigger_refresh = trigger_refresh  # дёргает цикл (fetch аккаунтов)
        self._current_niche_id: int | None = None
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- верхній бар: статистика + кнопки ---
        top_bar = QHBoxLayout()
        self.summary_label = QLabel("Всього на продажі: —")
        self.summary_label.setStyleSheet("font-size: 13pt; color: #4caf50;")
        top_bar.addWidget(self.summary_label)
        top_bar.addStretch()
        btn_limits = QPushButton("⚙ Ліміти")
        btn_limits.clicked.connect(self._open_limits_dialog)
        top_bar.addWidget(btn_limits)
        btn_fetch = QPushButton("🔄 Оновити з API")
        btn_fetch.setObjectName("primary")
        btn_fetch.clicked.connect(self._fetch_now)
        top_bar.addWidget(btn_fetch)
        root.addLayout(top_bar)

        # --- прогрес автоматизації (завжди видно) ---
        self.progress_label = QLabel("Прогрес автоматизації: —")
        self.progress_label.setStyleSheet(
            "color:#e6e6e6; padding:10px; "
            "background:#1f1f1f; border:1px solid #2a2a2a; border-radius:6px; "
            "font-size: 11pt;"
        )
        self.progress_label.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self.progress_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- ліва панель: ніші (тепер ширше) ---
        left = QWidget()
        left.setMinimumWidth(380)
        left_layout = QVBoxLayout(left)
        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Ніші</h3>"))
        header.addStretch()
        btn_new = QPushButton("+ Нова")
        btn_new.setObjectName("primary")
        btn_new.clicked.connect(self._create_niche)
        header.addWidget(btn_new)
        left_layout.addLayout(header)

        self.niche_list = QListWidget()
        self.niche_list.itemSelectionChanged.connect(self._on_niche_selected)
        left_layout.addWidget(self.niche_list, 1)

        niche_actions = QHBoxLayout()
        self.btn_edit = QPushButton("Редагувати")
        self.btn_edit.clicked.connect(self._edit_niche)
        self.btn_delete = QPushButton("Видалити")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete_niche)
        niche_actions.addWidget(self.btn_edit)
        niche_actions.addWidget(self.btn_delete)
        left_layout.addLayout(niche_actions)

        splitter.addWidget(left)

        # --- права панель: аккаунти + панель задач знизу ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.right_header = QLabel("<h3>Акаунти ніші</h3>")
        right_layout.addWidget(self.right_header)

        # вертикальний splitter: верх — таблиця, низ — список задач
        right_split = QSplitter(Qt.Orientation.Vertical)

        # верх — таблиця акаунтів + bulk actions
        accounts_box = QWidget()
        accounts_layout = QVBoxLayout(accounts_box)
        accounts_layout.setContentsMargins(0, 0, 0, 0)
        self.table = AccountsTable()
        self.table.price_changed.connect(self._on_price_changed)
        self.table.cost_changed.connect(self._on_cost_changed)
        accounts_layout.addWidget(self.table, 1)
        accounts_layout.addLayout(self._bulk_actions_bar())
        right_split.addWidget(accounts_box)

        # низ — панель задач
        from app.ui.widgets.tasks_panel import TasksPanel
        self.tasks_panel = TasksPanel()
        right_split.addWidget(self.tasks_panel)
        right_split.setStretchFactor(0, 2)
        right_split.setStretchFactor(1, 1)

        right_layout.addWidget(right_split, 1)
        splitter.addWidget(right)
        # ніші займають більше місця, ~40% ширини головного вікна
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

    def _bulk_actions_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        select_all = QPushButton("Выделить всё")
        select_all.clicked.connect(lambda: self.table.select_all(True))
        bar.addWidget(select_all)

        clear_sel = QPushButton("Снять выделение")
        clear_sel.clicked.connect(lambda: self.table.select_all(False))
        bar.addWidget(clear_sel)

        btn_bump = QPushButton("🔺 Поднять")
        btn_bump.clicked.connect(self._bulk_bump)
        bar.addWidget(btn_bump)

        btn_stick = QPushButton("📌 Закрепить")
        btn_stick.clicked.connect(self._bulk_stick)
        bar.addWidget(btn_stick)

        btn_label = QPushButton("🏷 Метка +")
        btn_label.clicked.connect(self._bulk_label_add)
        bar.addWidget(btn_label)

        btn_label_rm = QPushButton("🏷 Метка −")
        btn_label_rm.clicked.connect(self._bulk_label_remove)
        bar.addWidget(btn_label_rm)

        btn_price = QPushButton("% Цена")
        btn_price.clicked.connect(self._bulk_price)
        bar.addWidget(btn_price)

        btn_markup = QPushButton("$ Наценка")
        btn_markup.clicked.connect(self._bulk_markup)
        bar.addWidget(btn_markup)

        btn_cost = QPushButton("S Себестоимость")
        btn_cost.clicked.connect(self._bulk_cost)
        bar.addWidget(btn_cost)

        btn_off = QPushButton("✕ Снять с продажи")
        btn_off.setObjectName("danger")
        btn_off.clicked.connect(self._bulk_deactivate)
        bar.addWidget(btn_off)

        bar.addStretch()
        return bar

    # ---------- state ----------
    def reload(self) -> None:
        niches = niche_manager.list_niches()
        logger.info(
            "home_tab.reload: {} ніш у БД: {}",
            len(niches),
            [(n.id, n.name, f"tag={n.tag_id}") for n in niches],
        )

        with get_session() as s:
            total_on_sale = s.execute(
                select(func.count(Account.id)).where(Account.status == "active")
            ).scalar_one() or 0
            unclassified_count = s.execute(
                select(func.count(Account.id)).where(
                    Account.status == "active", Account.niche_id.is_(None)
                )
            ).scalar_one() or 0

        self.summary_label.setText(
            f"Всього на продажі: <b>{total_on_sale}</b>  |  "
            f"Ніш: <b>{len(niches)}</b>  |  "
            f"Без класифікації: <b>{unclassified_count}</b>"
        )

        # --- прогрес автоматизації ---
        from app.services import settings_store
        planned_bumps = sum(n.bumps_per_day for n in niches if n.auto_bump)
        planned_stuck_bumps = sum(n.stuck_bumps_per_day for n in niches if n.auto_bump_stuck)
        planned_stick_slots = sum(n.stick_slots for n in niches if n.auto_stick)
        bumps_done = niche_manager.global_bumps_today(stuck=False)
        stuck_bumps_done = niche_manager.global_bumps_today(stuck=True)
        stuck_now = niche_manager.total_stuck_count()
        global_slots = settings_store.get_global_stick_slots()
        global_max = settings_store.get_global_bumps_per_day()

        # Реальний стан з API: скільки акк зараз не можна bump-ати
        with get_session() as s:
            on_cooldown = s.execute(
                select(func.count(Account.id)).where(
                    Account.bumps_available == 0, Account.status == "active"
                )
            ).scalar_one() or 0
            ready_to_bump = max(0, total_on_sale - on_cooldown)

        plan_str = str(planned_bumps) if planned_bumps else "∞"
        if global_max:
            plan_str += f" (ліміт {global_max})"

        self.progress_label.setText(
            "🔺 Bump додатком сьогодні: "
            f"<b style='color:#4caf50'>{bumps_done}</b> / {plan_str}  &nbsp;|&nbsp;  "
            "🔺📌 Bump закріплених: "
            f"<b style='color:#4caf50'>{stuck_bumps_done}</b> / {planned_stuck_bumps or '∞'}  &nbsp;|&nbsp;  "
            "📌 Закріплено зараз: "
            f"<b style='color:#2196f3'>{stuck_now}</b> / {global_slots}<br>"
            f"<span style='color:#9e9e9e'>На cooldown зараз (вже bump-нуто): "
            f"<b>{on_cooldown}</b>  |  Готові до bump: <b>{ready_to_bump}</b>  |  "
            f"планових stick-слотів: {planned_stick_slots}</span>"
        )

        self.niche_list.clear()
        for n in niches:
            item = QListWidgetItem()
            card = NicheCard(n)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, n.id)
            self.niche_list.addItem(item)
            self.niche_list.setItemWidget(item, card)

        # псевдо-ниша «Без классификации»
        pseudo = QListWidgetItem(f"📦 Без классификации ({unclassified_count})")
        pseudo.setData(Qt.ItemDataRole.UserRole, UNCLASSIFIED_ID)
        pseudo.setForeground(Qt.GlobalColor.yellow)
        self.niche_list.addItem(pseudo)

        if self._current_niche_id is not None:
            for i in range(self.niche_list.count()):
                if self.niche_list.item(i).data(Qt.ItemDataRole.UserRole) == self._current_niche_id:
                    self.niche_list.setCurrentRow(i)
                    break

        self._reload_accounts()

    def _reload_accounts(self) -> None:
        if self._current_niche_id is None:
            self.table.set_accounts([])
            self.right_header.setText("<h3>Аккаунты</h3><i>Выберите нишу слева</i>")
            return

        with get_session() as s:
            if self._current_niche_id == UNCLASSIFIED_ID:
                stmt = (
                    select(Account)
                    .where(Account.niche_id.is_(None), Account.status == "active")
                    .order_by(Account.price.desc())
                )
                title = "Без классификации"
            else:
                stmt = (
                    select(Account)
                    .where(Account.niche_id == self._current_niche_id)
                    .order_by(Account.price.desc())
                )
                title = "в нише"
            accounts = list(s.execute(stmt).scalars())

        self.right_header.setText(f"<h3>Аккаунты {title} — {len(accounts)} шт.</h3>")
        self.table.set_accounts(accounts)

    # ---------- niche slots ----------
    def _on_niche_selected(self) -> None:
        items = self.niche_list.selectedItems()
        if not items:
            self._current_niche_id = None
        else:
            self._current_niche_id = items[0].data(Qt.ItemDataRole.UserRole)
        self._reload_accounts()

    def _create_niche(self) -> None:
        dlg = NicheEditor(client=self.client, parent=self)
        if dlg.exec() != NicheEditor.DialogCode.Accepted:
            return
        values = dlg.values()
        if not values["name"]:
            QMessageBox.warning(self, "Ошибка", "Введите название ниши")
            return
        new_niche = niche_manager.create_niche(**values)
        # Якщо вказана закупівельна ціна — застосувати до вже зафіксованих
        # продажів цієї ніші (перерахувати прибуток ретроактивно)
        if new_niche.default_cost > 0:
            updated = niche_manager.apply_niche_default_cost_to_sales(
                new_niche.id, new_niche.default_cost
            )
            if updated:
                logger.info("Перераховано прибуток у {} продажах ніші", updated)

        # При создании ниши с тегом — всегда подтягиваем аккаунты с API,
        # чтобы сразу увидеть результат классификации по тегу.
        QMessageBox.information(
            self,
            "Ниша создана",
            "Ниша сохранена. Запускаю обновление аккаунтов с Lolzteam Market — "
            "это может занять до минуты, классификация по тегу применится автоматически.",
        )
        self._fetch_now()

    def _edit_niche(self) -> None:
        if self._current_niche_id is None or self._current_niche_id == UNCLASSIFIED_ID:
            return
        with get_session() as s:
            from app.db.models import Niche
            niche = s.get(Niche, self._current_niche_id)
            if niche is None:
                return
            dlg = NicheEditor(niche=niche, client=self.client, parent=self)
        if dlg.exec() == NicheEditor.DialogCode.Accepted:
            values = dlg.values()
            niche_manager.update_niche(self._current_niche_id, **values)
            if values.get("default_cost", 0) > 0:
                niche_manager.apply_niche_default_cost_to_sales(
                    self._current_niche_id, float(values["default_cost"])
                )
            niche_manager.reclassify_accounts()
            self.reload()

    def _open_limits_dialog(self) -> None:
        # відкриваємо діалог налаштувань і ОДРАЗУ після закриття оновлюємо UI
        from app.config import Settings as _Settings
        from app.ui.settings_dialog import SettingsDialog

        win = self.window()
        settings = getattr(win, "settings", None) or _Settings.load()
        dlg = SettingsDialog(settings, parent=self)
        # Знаходимо в дереві предків об'єкт що має client (MainWindow)
        # — щоб autodetect-кнопка змогла знайти client
        dlg.client = self.client
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self.window().statusBar().showMessage("Ліміти збережено", 4000)
        self.reload()

    def _delete_niche(self) -> None:
        if self._current_niche_id is None or self._current_niche_id == UNCLASSIFIED_ID:
            return
        ok = QMessageBox.question(self, "Удаление", "Удалить нишу?") == QMessageBox.StandardButton.Yes
        if not ok:
            return
        niche_manager.delete_niche(self._current_niche_id)
        self._current_niche_id = None
        niche_manager.reclassify_accounts()
        self.reload()

    def _fetch_now(self) -> None:
        try:
            started = self.trigger_refresh()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Помилка оновлення", str(exc))
            return
        if started is False:
            self.window().statusBar().showMessage(
                "Цикл вже виконується — зачекайте до завершення", 6000,
            )
        else:
            self.window().statusBar().showMessage(
                "Запит до API… акаунти з'являться у нішах коли цикл завершиться", 12000,
            )

    @staticmethod
    def _accounts_count() -> int:
        with get_session() as s:
            return s.execute(select(func.count(Account.id))).scalar_one() or 0

    # ---------- table slots ----------
    def _on_price_changed(self, item_id: int, new_price: float) -> None:
        try:
            self.client.update_item(item_id, price=new_price)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "API ошибка", str(exc))
            self._reload_accounts()
            return
        with get_session() as s:
            acc = s.execute(select(Account).where(Account.item_id == item_id)).scalar_one_or_none()
            if acc:
                acc.price = new_price
            s.commit()

    def _on_cost_changed(self, item_id: int, new_cost: float) -> None:
        bulk_actions.set_cost([item_id], new_cost)

    # ---------- bulk slots ----------
    def _bulk_bump(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        results = bulk_actions.bump_items(self.client, ids)
        self._toast_results("Поднятие", results)
        self._reload_accounts()

    def _bulk_stick(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        results = bulk_actions.stick_items(self.client, ids)
        self._toast_results("Закрепление", results)
        self._reload_accounts()

    def _bulk_label_add(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        text, ok = QInputDialog.getText(self, "Публичная метка", "Текст метки:")
        if not ok or not text.strip():
            return
        results = bulk_actions.add_public_label(self.client, ids, text.strip())
        self._toast_results("Метка +", results)
        self._reload_accounts()

    def _bulk_label_remove(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        text, ok = QInputDialog.getText(self, "Удалить метку", "Что удалить:")
        if not ok or not text.strip():
            return
        results = bulk_actions.remove_public_label(self.client, ids, text.strip())
        self._toast_results("Метка −", results)
        self._reload_accounts()

    def _bulk_price(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        pct, ok = QInputDialog.getDouble(self, "Изменить цену", "Процент (−50..+100):", 5, -90, 500, 1)
        if not ok:
            return
        results = bulk_actions.change_prices_by_percent(self.client, ids, pct)
        self._toast_results("Цена", results)
        self._reload_accounts()

    def _bulk_markup(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        amount, ok = QInputDialog.getDouble(
            self, "Наценка", "Сумма наценки ($, прибавится к себестоимости):",
            1.0, 0.0, 1_000_000.0, 2,
        )
        if not ok:
            return
        results = bulk_actions.apply_markup(self.client, ids, amount)
        self._toast_results("Наценка", results)
        self._reload_accounts()

    def _bulk_cost(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        cost, ok = QInputDialog.getDouble(self, "Себестоимость", "Значение в $:", 1, 0, 1_000_000, 2)
        if not ok:
            return
        bulk_actions.set_cost(ids, cost)
        self._reload_accounts()

    def _bulk_deactivate(self) -> None:
        ids = self.table.selected_item_ids()
        if not ids:
            return
        confirm = QMessageBox.question(self, "Снять с продажи", f"Снять {len(ids)} аккаунтов с продажи?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        results = bulk_actions.deactivate_items(self.client, ids)
        self._toast_results("Снятие", results)
        self._reload_accounts()

    def _toast_results(self, action: str, results: dict) -> None:
        ok = sum(1 for v in results.values() if v == "ok" or (isinstance(v, str) and v.startswith("ok")))
        total = len(results)
        logger.info("{}: {}/{}", action, ok, total)
        self.window().statusBar().showMessage(f"{action}: {ok}/{total} успешно", 5000)
