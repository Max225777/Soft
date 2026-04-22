"""Вкладка «Главная»: ниши + аккаунты + массовые действия."""

from __future__ import annotations

from typing import Callable

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
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
from sqlalchemy import select

from app.api.client import LolzMarketClient
from app.core import bulk_actions, niche_manager
from app.db.models import Account
from app.db.session import get_session
from app.ui.niche_editor import NicheEditor
from app.ui.widgets.accounts_table import AccountsTable
from app.ui.widgets.niche_card import NicheCard


class HomeTab(QWidget):
    def __init__(self, client: LolzMarketClient, refresh_cb: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.refresh_cb = refresh_cb
        self._current_niche_id: int | None = None
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- левая панель: ниши ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        header = QHBoxLayout()
        header.addWidget(QLabel("<h3>Ниши</h3>"))
        header.addStretch()
        btn_new = QPushButton("+ Новая")
        btn_new.setObjectName("primary")
        btn_new.clicked.connect(self._create_niche)
        header.addWidget(btn_new)
        left_layout.addLayout(header)

        self.niche_list = QListWidget()
        self.niche_list.itemSelectionChanged.connect(self._on_niche_selected)
        left_layout.addWidget(self.niche_list, 1)

        niche_actions = QHBoxLayout()
        self.btn_edit = QPushButton("Редактировать")
        self.btn_edit.clicked.connect(self._edit_niche)
        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete_niche)
        niche_actions.addWidget(self.btn_edit)
        niche_actions.addWidget(self.btn_delete)
        left_layout.addLayout(niche_actions)

        splitter.addWidget(left)

        # --- правая панель: аккаунты ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.right_header = QLabel("<h3>Аккаунты ниши</h3>")
        right_layout.addWidget(self.right_header)

        self.table = AccountsTable()
        self.table.price_changed.connect(self._on_price_changed)
        self.table.cost_changed.connect(self._on_cost_changed)
        right_layout.addWidget(self.table, 1)

        right_layout.addLayout(self._bulk_actions_bar())

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

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

        btn_markup = QPushButton("% Наценка")
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
        self.niche_list.clear()
        for n in niches:
            item = QListWidgetItem()
            card = NicheCard(n)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, n.id)
            self.niche_list.addItem(item)
            self.niche_list.setItemWidget(item, card)

        if self._current_niche_id is not None:
            for i in range(self.niche_list.count()):
                if self.niche_list.item(i).data(Qt.ItemDataRole.UserRole) == self._current_niche_id:
                    self.niche_list.setCurrentRow(i)
                    break

        self._reload_accounts()

    def _reload_accounts(self) -> None:
        if self._current_niche_id is None:
            self.table.set_accounts([])
            self.right_header.setText("<h3>Аккаунты ниши</h3><i>Выберите нишу слева</i>")
            return
        with get_session() as s:
            stmt = select(Account).where(Account.niche_id == self._current_niche_id).order_by(Account.price.desc())
            accounts = list(s.execute(stmt).scalars())
        self.right_header.setText(f"<h3>Аккаунты в нише — {len(accounts)} шт.</h3>")
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
        dlg = NicheEditor(parent=self)
        if dlg.exec() == NicheEditor.DialogCode.Accepted:
            values = dlg.values()
            if not values["name"]:
                QMessageBox.warning(self, "Ошибка", "Введите название ниши")
                return
            niche_manager.create_niche(**values)
            niche_manager.reclassify_accounts()
            self.reload()

    def _edit_niche(self) -> None:
        if self._current_niche_id is None:
            return
        with get_session() as s:
            from app.db.models import Niche
            niche = s.get(Niche, self._current_niche_id)
            if niche is None:
                return
            dlg = NicheEditor(niche=niche, parent=self)
        if dlg.exec() == NicheEditor.DialogCode.Accepted:
            niche_manager.update_niche(self._current_niche_id, **dlg.values())
            niche_manager.reclassify_accounts()
            self.reload()

    def _delete_niche(self) -> None:
        if self._current_niche_id is None:
            return
        ok = QMessageBox.question(self, "Удаление", "Удалить нишу?") == QMessageBox.StandardButton.Yes
        if not ok:
            return
        niche_manager.delete_niche(self._current_niche_id)
        self._current_niche_id = None
        self.reload()

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
        pct, ok = QInputDialog.getDouble(self, "Наценка", "Процент наценки:", 20, -50, 1000, 1)
        if not ok:
            return
        results = bulk_actions.apply_markup(self.client, ids, pct)
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
