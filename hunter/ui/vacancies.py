"""Typed table model: sorting never changes the record associated with a row."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTableView,
    QHeaderView,
    QDialog,
    QPlainTextEdit,
)
from ..history import vacancy_values
from .components import label, button, page_layout


class VacancyModel(QAbstractTableModel):
    headers = ["Вакансия", "Компания", "Балл", "Формат", "Решение", "Статус"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.records = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        value = vacancy_values(self.records[index.row()])[index.column()]
        if role == Qt.DisplayRole:
            return str(value) if value is not None else "—"
        if role == Qt.UserRole:
            if index.column() == 2:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return -1.0
            return str(value or "").casefold()
        if role == Qt.ForegroundRole and index.column() == 4:
            return QColor(
                {
                    "APPLY": "#9fe5c5",
                    "REJECT": "#eea99c",
                    "MANUAL_REVIEW": "#e5c78d",
                }.get(str(value), "#becfc8")
            )
        if role == Qt.ToolTipRole:
            return str(value or "")

    def replace(self, records):
        self.beginResetModel()
        self.records = records
        self.endResetModel()


class VacanciesPanel(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        layout = page_layout(self)
        heading = QHBoxLayout()
        heading.addWidget(label("История решений", "sectionTitle"))
        heading.addStretch()
        heading.addWidget(button("Обновить", self.load))
        layout.addLayout(heading)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(
            "Поиск по вакансии, компании, решению или статусу…"
        )
        self.filter.setAccessibleName("Фильтр истории вакансий")
        layout.addWidget(self.filter)
        self.model = VacancyModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setSortRole(Qt.UserRole)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 135)
        self.table.setColumnWidth(5, 145)
        self.table.doubleClicked.connect(self.show_details)
        layout.addWidget(self.table, 1)
        self.summary = label("", "muted", True)
        layout.addWidget(self.summary)
        self.proxy.rowsInserted.connect(self.update_summary)
        self.proxy.rowsRemoved.connect(self.update_summary)
        self.filter.textChanged.connect(self.update_summary)
        self.load()

    def load(self):
        try:
            self.model.replace(self.store.records())
            self.update_summary()
        except OSError as exc:
            self.summary.setText(f"Не удалось прочитать историю: {exc}")

    def update_summary(self, *_):
        total = len(self.model.records)
        self.summary.setText(
            f"Показано {self.proxy.rowCount()} из {total} записей · Двойной щелчок открывает решение и письмо."
            if total
            else "История пока пуста. После первого запуска здесь появятся решения и сопроводительные письма."
        )

    def show_details(self, index):
        source = self.proxy.mapToSource(index)
        record = self.model.records[source.row()]
        values = vacancy_values(record)
        result = record["result"]
        dialog = QDialog(self)
        dialog.setWindowTitle(str(values[0]))
        dialog.resize(740, 580)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label(str(values[0]), "sectionTitle", True))
        layout.addWidget(
            label(
                f"{values[1]} · {values[4]} · {values[2] if values[2] is not None else '—'} баллов",
                "muted",
                True,
            )
        )
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            f"Причина решения\n{result.get('decision_reason') or result.get('reason') or 'Не указана'}\n\n"
            f"Сопроводительное письмо\n{result.get('cover_letter') or 'Не сохранено'}\n\n"
            f"Вакансия\n{record['vacancy'].get('url') or record['vacancy'].get('alternate_url') or 'URL не сохранён'}\n\n"
            f"Запись: {record.get('timestamp', '—')}\nМодель: {result.get('model', '—')}"
        )
        layout.addWidget(text)
        layout.addWidget(button("Закрыть", dialog.accept))
        dialog.exec()
