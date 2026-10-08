"""Thin PySide6 operator UI for the existing AI-Hunter CLI core."""

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QMessageBox,
    QRadioButton, QButtonGroup,
)

import config
from candidate import CANDIDATE


ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "results.jsonl"


class RunPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.process = None
        self.events = QTextEdit()
        self.events.setReadOnly(True)
        self.events.setObjectName("eventLog")
        self.status = QLabel("Ready")
        self.status.setObjectName("statusLabel")
        self.mode = QComboBox()
        self.mode.addItem("Automatic submission", "auto")
        self.mode.addItem("Confirm before submission", "manual")
        self.start_button = QPushButton("Start run")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)

        self.processed = QLabel("Processed\n0")
        self.applied = QLabel("APPLY\n0")
        self.reviewed = QLabel("REVIEW\n0")
        self.rejected = QLabel("REJECT\n0")
        metrics = QHBoxLayout()
        for widget in (self.processed, self.applied, self.reviewed, self.rejected):
            widget.setObjectName("metric")
            metrics.addWidget(widget)
        metrics.addStretch()

        self.current = QLabel("Waiting to start")
        self.current.setObjectName("currentActivity")
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Application mode"))
        controls.addWidget(self.mode)
        controls.addStretch()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)

        header = QHBoxLayout()
        title = QLabel("Current run")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addLayout(controls)
        layout.addLayout(metrics)
        layout.addWidget(QLabel("Current activity"))
        layout.addWidget(self.current)
        layout.addWidget(QLabel("Activity log"))
        layout.addWidget(self.events, 1)

    def start(self):
        if self.process:
            return
        self.events.append("Starting AI-Hunter core...")
        self.current.setText("Starting browser and preparing HH session")
        self.status.setText("Running")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.process = QProcess(self)
        env = self.process.processEnvironment()
        env.insert("JOBHUNTER_GUI_MODE", self.mode.currentData())
        env.insert("JOBHUNTER_GUI_CONFIRMED", "1")
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(ROOT))
        self.process.setProgram(sys.executable)
        self.process.setArguments([str(ROOT / "apply.py")])
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.start()

    def read_output(self):
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        error = bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
        text = (data + error).strip()
        if text:
            self.events.append(text)
            self.update_activity(text)
            self.window.refresh_history()

    def update_activity(self, text):
        compact = " ".join(text.split())
        if compact:
            self.current.setText(compact[-220:])
        counts = {"APPLY": 0, "REVIEW": 0, "REJECT": 0}
        for line in self.events.toPlainText().splitlines():
            upper = line.upper()
            for key in counts:
                if key in upper:
                    counts[key] += 1
        processed = sum(counts.values())
        self.processed.setText(f"Processed\n{processed}")
        self.applied.setText(f"APPLY\n{counts['APPLY']}")
        self.reviewed.setText(f"REVIEW\n{counts['REVIEW']}")
        self.rejected.setText(f"REJECT\n{counts['REJECT']}")

    def finished(self, code, _status):
        self.events.append(f"Run finished with exit code {code}.")
        self.status.setText("Ready" if code == 0 else "Error")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.process = None
        self.window.refresh_history()

    def stop(self):
        if self.process:
            self.process.terminate()
            self.events.append("Stop requested.")


class VacanciesPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by title, company or decision")
        self.filter.textChanged.connect(self.apply_filter)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Title", "Company", "Score", "Remote", "Decision", "Status"])
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.show_details)
        layout = QVBoxLayout(self)
        title = QLabel("Vacancies")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addWidget(self.filter)
        layout.addWidget(self.table, 1)
        self.load()

    def load(self):
        self.table.setRowCount(0)
        if not STATE_FILE.exists():
            return
        for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            vacancy = record.get("vacancy", {})
            result = record.get("result", {})
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                vacancy.get("title", vacancy.get("name", "")),
                vacancy.get("company", vacancy.get("employer", "")),
                str(result.get("score", "")),
                "Yes" if result.get("is_remote") else "No",
                str(result.get("decision", "")).upper(),
                result.get("status", ""),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def apply_filter(self, text):
        needle = text.lower().strip()
        for row in range(self.table.rowCount()):
            visible = not needle or any(
                needle in (self.table.item(row, column).text().lower() if self.table.item(row, column) else "")
                for column in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not visible)

    def show_details(self, row, _column):
        values = [self.table.item(row, column).text() for column in range(self.table.columnCount())]
        QMessageBox.information(
            self,
            "Vacancy details",
            "\n".join(
                f"{self.table.horizontalHeaderItem(i).text()}: {values[i]}"
                for i in range(6)
            ),
        )


class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        form = QFormLayout()
        values = [
            ("Apply threshold", config.MIN_SCORE_TO_APPLY),
            ("Remote threshold", config.REMOTE_MIN_SCORE_TO_APPLY),
            ("Review threshold", config.MIN_SCORE_TO_REVIEW),
            ("Minimum salary", CANDIDATE["minimum_salary"]),
            ("LM Studio endpoint", config.LM_STUDIO_URL),
            ("Model", config.LM_MODEL),
            ("Prompt version", config.PROMPT_VERSION),
        ]
        for label, value in values:
            field = QLineEdit(str(value))
            field.setReadOnly(True)
            form.addRow(label, field)
        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addStretch()


class AuthPanel(QWidget):
    def __init__(self, on_confirm):
        super().__init__()
        title = QLabel("AI-Hunter")
        title.setObjectName("pageTitle")
        heading = QLabel("HH account")
        heading.setObjectName("sectionTitle")
        text = QLabel(
            "The browser will open HeadHunter. Sign in to the account you want to use, "
            "then return here and confirm the session."
        )
        text.setWordWrap(True)
        open_button = QPushButton("Open HH")
        open_button.clicked.connect(lambda: webbrowser.open(config.HH_URL))
        confirm = QPushButton("Подтвердить")
        confirm.setObjectName("primaryButton")
        confirm.clicked.connect(on_confirm)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addSpacing(28)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addSpacing(12)
        layout.addWidget(open_button, 0, Qt.AlignLeft)
        layout.addWidget(confirm, 0, Qt.AlignLeft)
        layout.addStretch()


class ModePanel(QWidget):
    def __init__(self, on_continue, on_back):
        super().__init__()
        title = QLabel("Application mode")
        title.setObjectName("pageTitle")
        self.auto = QRadioButton("Automatic submission")
        self.auto.setChecked(True)
        self.manual = QRadioButton("Confirm before submission")
        self.group = QButtonGroup(self)
        self.group.addButton(self.auto)
        self.group.addButton(self.manual)
        note = QLabel(
            "Automatic sends accepted applications after all checks. "
            "Confirmation mode pauses before the final click."
        )
        note.setWordWrap(True)
        back = QPushButton("Back")
        back.clicked.connect(on_back)
        proceed = QPushButton("Continue")
        proceed.setObjectName("primaryButton")
        proceed.clicked.connect(lambda: on_continue("auto" if self.auto.isChecked() else "manual"))
        buttons = QHBoxLayout()
        buttons.addWidget(back)
        buttons.addStretch()
        buttons.addWidget(proceed)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(QLabel("Choose how accepted applications should be sent."))
        layout.addSpacing(16)
        layout.addWidget(self.auto)
        layout.addWidget(note)
        layout.addSpacing(14)
        layout.addWidget(self.manual)
        layout.addWidget(QLabel("Review, skip or rewrite each prepared cover letter before sending."))
        layout.addStretch()
        layout.addLayout(buttons)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-Hunter")
        self.resize(1180, 760)
        self.run_panel = RunPanel(self)
        self.vacancies = VacanciesPanel()
        self.stack = QStackedWidget()
        self.auth = AuthPanel(self.show_mode)
        self.mode_panel = ModePanel(self.start_from_mode, lambda: self.stack.setCurrentWidget(self.auth))
        self.stack.addWidget(self.auth)
        self.stack.addWidget(self.mode_panel)
        self.stack.addWidget(self.run_panel)
        self.stack.addWidget(self.vacancies)
        self.settings = SettingsPanel()
        self.stack.addWidget(self.settings)

        nav = QVBoxLayout()
        brand = QLabel("AI-Hunter")
        brand.setObjectName("brand")
        nav.addWidget(brand)
        for label, index in (("Run", 2), ("Vacancies", 3), ("Settings", 4)):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.clicked.connect(lambda _checked=False, i=index: self.stack.setCurrentIndex(i))
            nav.addWidget(button)
        nav.addStretch()
        nav_frame = QFrame()
        nav_frame.setObjectName("navFrame")
        nav_frame.setLayout(nav)
        splitter = QSplitter()
        splitter.addWidget(nav_frame)
        splitter.addWidget(self.stack)
        splitter.setSizes([180, 1000])
        self.setCentralWidget(splitter)

    def show_mode(self):
        self.stack.setCurrentWidget(self.mode_panel)

    def start_from_mode(self, mode):
        self.run_panel.mode.setCurrentIndex(0 if mode == "auto" else 1)
        self.stack.setCurrentWidget(self.run_panel)
        QTimer.singleShot(100, self.run_panel.start)

    def refresh_history(self):
        self.vacancies.load()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


STYLE = """
QWidget { background: #f5f6f7; color: #20252b; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background: #f5f6f7; }
#navFrame { background: #e9ecef; border-right: 1px solid #d3d8dd; }
#brand { font-size: 19px; font-weight: 600; padding: 18px 12px 24px; }
#navButton { text-align: left; border: 0; border-radius: 4px; padding: 10px 12px; background: transparent; }
#navButton:hover { background: #dce2e7; }
#pageTitle { font-size: 20px; font-weight: 600; padding: 14px 0 8px; }
#statusLabel { color: #356b58; font-weight: 600; }
#sectionTitle { font-size: 16px; font-weight: 600; }
#metric { background: #ffffff; border: 1px solid #cbd1d6; border-radius: 3px; padding: 9px 18px; min-width: 90px; }
#currentActivity { background: #ffffff; border-left: 3px solid #5a8f82; padding: 10px; }
#primaryButton { background: #356b58; color: #ffffff; border-color: #356b58; }
QPushButton { background: #ffffff; border: 1px solid #b9c1c8; border-radius: 4px; padding: 7px 13px; }
QPushButton:hover { background: #edf1f3; }
QLineEdit, QComboBox { background: #ffffff; border: 1px solid #b9c1c8; border-radius: 3px; padding: 7px; }
QTextEdit, QTableWidget { background: #ffffff; border: 1px solid #cbd1d6; border-radius: 3px; }
#eventLog { font-family: 'Cascadia Mono'; font-size: 12px; padding: 8px; }
QHeaderView::section { background: #e9ecef; border: 0; border-bottom: 1px solid #cbd1d6; padding: 7px; font-weight: 600; }
QTableWidget { gridline-color: #e2e5e8; selection-background-color: #dbe9e5; selection-color: #20252b; }
"""


if __name__ == "__main__":
    raise SystemExit(main())
