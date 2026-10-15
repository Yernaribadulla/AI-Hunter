"""Composition root for native widgets and local services."""

import queue
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QStackedWidget,
    QMessageBox,
)
from ..bridge import BridgeServer
from ..health import HealthWorker
from ..history import HistoryStore
from ..process import PipelineController, ROOT
from .components import label, button, scroll_page
from .workspace import RunPanel, SettingsPanel
from .vacancies import VacanciesPanel
from .review import ReviewDialog


class MainWindow(QMainWindow):
    def __init__(self, history_path=None, check_health=True):
        super().__init__()
        self.setWindowTitle("AI-Hunter · Рабочее пространство")
        self.resize(1320, 960)
        self.setMinimumSize(1000, 760)
        self.model_ready = False
        self.health_worker = None
        self.active_dialog = None
        self._closed = False
        self.bridge = BridgeServer()
        self.controller = PipelineController(self.bridge, self)
        self.store = HistoryStore(
            Path(history_path) if history_path else ROOT / "results.jsonl"
        )
        self.run_panel = RunPanel(self.controller)
        self.vacancies = VacanciesPanel(self.store)
        self.settings = SettingsPanel()
        self.stack = QStackedWidget()
        for page in (
            scroll_page(self.run_panel),
            self.vacancies,
            scroll_page(self.settings),
        ):
            self.stack.addWidget(page)
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(218)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(18, 28, 18, 24)
        nav.setSpacing(8)
        nav.addWidget(label("H /", "brandMark"))
        nav.addWidget(label("AI-HUNTER", "brand"))
        nav.addWidget(label("КАРЬЕРНЫЙ АГЕНТ", "eyebrow"))
        nav.addSpacing(34)
        nav.addWidget(label("РАБОЧЕЕ ПРОСТРАНСТВО", "eyebrow"))
        self.nav_buttons = []
        for index, title in enumerate(
            ("01   Центр управления", "02   История вакансий", "03   Настройки")
        ):
            item = button(title, lambda _=False, i=index: self.navigate(i))
            item.setObjectName("navButton")
            item.setCheckable(True)
            nav.addWidget(item)
            self.nav_buttons.append(item)
        nav.addStretch()
        nav.addWidget(label("LOCAL FIRST", "eyebrow"))
        self.provider_status = label("Проверка LM Studio…", "muted", True)
        nav.addWidget(self.provider_status)
        nav.addWidget(label("Данные и история\nостаются на компьютере.", "muted", True))
        nav.addSpacing(18)
        nav.addWidget(label("HEADHUNTER / АСТАНА", "eyebrow"))
        root.addWidget(sidebar)
        workspace = QVBoxLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setSpacing(0)
        top = QHBoxLayout()
        top.setContentsMargins(30, 24, 30, 8)
        self.page_title = label("", "pageTitle")
        top.addWidget(self.page_title)
        top.addStretch()
        self.status = label("Проверка модели", "status")
        self.status.setAccessibleName("Состояние локальной модели")
        top.addWidget(self.status)
        self.recheck = button("Проверить связь", self.check_health)
        top.addWidget(self.recheck)
        workspace.addLayout(top)
        workspace.addWidget(self.stack, 1)
        root.addLayout(workspace, 1)
        self.setCentralWidget(central)
        self.run_panel.start_button.clicked.connect(self.start_run)
        self.controller.running_changed.connect(self.on_running)
        self.controller.completed.connect(lambda *_: self.refresh_history())
        self.history_timer = QTimer(self)
        self.history_timer.setSingleShot(True)
        self.history_timer.setInterval(500)
        self.history_timer.timeout.connect(self.refresh_history)
        self.controller.event.connect(self.schedule_history)
        self.bridge_timer = QTimer(self)
        self.bridge_timer.timeout.connect(self.process_bridge_events)
        self.bridge_timer.start(100)
        self.navigate(0)
        if check_health:
            QTimer.singleShot(0, self.check_health)

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        self.page_title.setText(
            ("Центр управления", "История вакансий", "Настройки")[index]
        )
        for i, item in enumerate(self.nav_buttons):
            item.setChecked(i == index)
        if index == 1:
            self.refresh_history()

    def check_health(self):
        if self.health_worker and self.health_worker.isRunning():
            return
        self.recheck.setEnabled(False)
        self.model_ready = False
        self.run_panel.start_button.setEnabled(False)
        self.status.setText("Проверка модели…")
        if self.health_worker:
            self.health_worker.deleteLater()
        self.health_worker = HealthWorker(self)
        self.health_worker.result.connect(self.on_health)
        self.health_worker.finished.connect(lambda: self.recheck.setEnabled(True))
        self.health_worker.start()

    def on_health(self, result):
        self.model_ready = result.ready
        self.status.setText(
            "LM Studio подключён" if result.ready else "Модель недоступна"
        )
        self.status.setProperty("ready", result.ready)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.provider_status.setText(
            "Модель готова к работе" if result.ready else "Модель недоступна"
        )
        self.run_panel.health_text.setText(result.message)
        self.run_panel.notice.setVisible(not result.ready)
        self.run_panel.start_button.setEnabled(
            result.ready and not self.controller.running
        )
        self.run_panel.start_button.setToolTip(
            "Запустить поиск вакансий" if result.ready else result.message
        )

    def start_run(self):
        if not self.model_ready or self.controller.running:
            return
        if self.run_panel.mode.currentData() == "auto":
            confirm = QMessageBox.question(
                self,
                "Автоматические отклики",
                "Подходящие вакансии получат реальные отклики без проверки каждого письма. Запустить автоматический режим?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return
        self.run_panel.reset()
        self.controller.start(self.run_panel.mode.currentData())

    def on_running(self, running):
        self.run_panel.start_button.setEnabled(not running and self.model_ready)
        self.run_panel.stop_button.setEnabled(running)
        self.run_panel.mode.setEnabled(not running)
        if not running and self.active_dialog:
            self.active_dialog.reject()

    def schedule_history(self, event):
        if (
            event.get("type") in {"decision_made", "run_finished"}
            and not self.history_timer.isActive()
        ):
            self.history_timer.start()

    def refresh_history(self):
        self.vacancies.load()

    def process_bridge_events(self):
        if self.active_dialog:
            return
        try:
            request = self.bridge.requests.get_nowait()
        except queue.Empty:
            return
        if request.event.is_set():
            return
        if request.payload.get("type") not in {
            "session_confirmation",
            "application_review",
        }:
            request.resolve({"action": "skip"})
            return
        self.active_dialog = dialog = ReviewDialog(request.payload, self)
        try:
            dialog.exec()
            request.resolve(dialog.response)
        finally:
            self.active_dialog = None
            dialog.deleteLater()

    def closeEvent(self, event):
        if self._closed:
            event.accept()
            return
        if self.controller.running:
            answer = QMessageBox.question(
                self,
                "Остановить процесс?",
                "Закрытие окна остановит текущий поиск. Уже сохранённые результаты останутся в истории.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self._closed = True
        self.bridge_timer.stop()
        self.history_timer.stop()
        if self.active_dialog:
            self.active_dialog.reject()
        self.controller.close()
        self.bridge.close()
        if self.health_worker:
            self.health_worker.wait()
        event.accept()
