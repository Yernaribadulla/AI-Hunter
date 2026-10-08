"""Thin PySide6 operator UI for the existing AI-Hunter CLI core."""

import json
import os
import subprocess
import sys
import webbrowser
import queue
import socketserver
import threading
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QMessageBox,
    QRadioButton, QButtonGroup, QInputDialog,
)

import config
from candidate import CANDIDATE


ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "results.jsonl"


class BridgeHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            payload = json.loads(self.rfile.readline().decode("utf-8"))
            event = threading.Event()
            response = {}
            self.server.requests.put((payload, event, response))
            event.wait()
            self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception as exc:
            self.wfile.write((json.dumps({"action": "skip", "error": str(exc)}) + "\n").encode("utf-8"))


class BridgeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self):
        self.requests = queue.Queue()
        super().__init__(("127.0.0.1", 0), BridgeHandler)


class RunPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.process = None
        self.event_buffer = ""
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
        env.insert("JOBHUNTER_GUI_EVENTS", "1")
        env.insert("JOBHUNTER_GUI_BRIDGE_PORT", str(self.window.bridge.server_address[1]))
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
        self.event_buffer += error
        event_lines = self.event_buffer.split("\n")
        self.event_buffer = event_lines.pop()
        for line in event_lines:
            if line.startswith("__AIH_EVENT__"):
                try:
                    self.handle_pipeline_event(json.loads(line[len("__AIH_EVENT__"):]))
                except json.JSONDecodeError:
                    self.events.append("ERROR  Invalid pipeline event")
            elif line.strip():
                self.events.append(line)
        text = data.strip()
        if text:
            self.events.append(text)
        if data or error:
            self.events.ensureCursorVisible()
            self.window.refresh_history()

    def handle_pipeline_event(self, event):
        message = event.get("message", event.get("type", ""))
        level = "DECISION" if event.get("type") == "decision_made" else "INFO"
        self.events.append(f"{event.get('timestamp', '')}  {level:<8} {message}")
        if event.get("processed") is not None:
            self.processed.setText(f"Processed\n{event['processed']}")
            self.applied.setText(f"APPLY\n{event.get('apply', 0)}")
            self.reviewed.setText(f"REVIEW\n{event.get('review', 0)}")
            self.rejected.setText(f"REJECT\n{event.get('reject', 0)}")
        if event.get("title"):
            self.current.setText(message)
        self.events.ensureCursorVisible()

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
        self.bridge = BridgeServer()
        self.bridge_thread = threading.Thread(target=self.bridge.serve_forever, daemon=True)
        self.bridge_thread.start()
        self.bridge_timer = QTimer(self)
        self.bridge_timer.timeout.connect(self.process_bridge_events)
        self.bridge_timer.start(100)
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

    def process_bridge_events(self):
        try:
            payload, event, response = self.bridge.requests.get_nowait()
        except queue.Empty:
            return
        if payload.get("type") == "application_review":
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Application ready")
            dialog.setText("Review the prepared cover letter before sending.")
            dialog.setDetailedText(payload.get("cover_letter", ""))
            send = dialog.addButton("Send", QMessageBox.AcceptRole)
            skip = dialog.addButton("Skip", QMessageBox.DestructiveRole)
            rewrite = dialog.addButton("Rewrite", QMessageBox.ActionRole)
            dialog.exec()
            clicked = dialog.clickedButton()
            if clicked is send:
                response.update(action="send")
            elif clicked is rewrite:
                instruction, accepted = QInputDialog.getText(
                    self, "Rewrite cover letter", "Instruction for the model:"
                )
                response.update(action="rewrite" if accepted and instruction.strip() else "skip", instruction=instruction)
            else:
                response.update(action="skip")
        event.set()

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
QWidget { background: #202126; color: #eef0f4; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background: #202126; }
#navFrame { background: #191a1f; border-right: 1px solid #30323a; }
#brand { font-size: 19px; font-weight: 600; padding: 18px 12px 24px; color: #f6f7f9; }
#navButton { text-align: left; border: 0; border-radius: 6px; padding: 11px 13px; background: transparent; color: #aeb3bd; }
#navButton:hover { background: #292b32; color: #ffffff; }
#pageTitle { font-size: 23px; font-weight: 600; padding: 14px 0 8px; color: #f4f5f7; }
#statusLabel { color: #4ed28b; font-weight: 600; background: #183b2d; border-radius: 5px; padding: 7px 11px; }
#sectionTitle { font-size: 16px; font-weight: 600; }
#metric { background: #292b31; border: 1px solid #3b3e47; border-radius: 6px; padding: 11px 20px; min-width: 90px; color: #f1f2f4; }
#currentActivity { background: #292b31; border: 1px solid #3b3e47; border-left: 3px solid #5f91ff; border-radius: 5px; padding: 11px; color: #d8dce4; }
#primaryButton { background: #4b76d1; color: #ffffff; border-color: #5c87e7; }
QPushButton { background: #2b2d34; border: 1px solid #474a54; border-radius: 5px; padding: 8px 14px; color: #eef0f4; }
QPushButton:hover { background: #353843; }
QLineEdit, QComboBox { background: #292b31; border: 1px solid #474a54; border-radius: 4px; padding: 8px; color: #eef0f4; }
QTextEdit, QTableWidget { background: #18191d; border: 1px solid #3b3e47; border-radius: 6px; color: #dfe2e8; }
#eventLog { font-family: 'Cascadia Mono'; font-size: 12px; padding: 10px; }
QHeaderView::section { background: #292b31; color: #b9bec8; border: 0; border-bottom: 1px solid #3b3e47; padding: 8px; font-weight: 600; }
QTableWidget { gridline-color: #2e3037; selection-background-color: #344b75; selection-color: #ffffff; }
QLabel { color: #dfe2e8; }
QRadioButton { spacing: 8px; padding: 6px 0; }
QComboBox QAbstractItemView { background: #292b31; color: #eef0f4; selection-background-color: #344b75; }
"""


if __name__ == "__main__":
    raise SystemExit(main())
