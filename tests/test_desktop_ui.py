"""Headless native Qt regression tests with a harmless subprocess fixture."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication
from hunter.health import ModelHealth
from hunter.history import HistoryStore
from hunter.ui.window import MainWindow
from hunter.ui.review import ReviewDialog
import desktop

APP = QApplication.instance() or QApplication([])
APP.setStyle("Fusion")
APP.setStyleSheet(desktop.STYLE)


def wait_until(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        QTest.qWait(10)
    return bool(predicate())


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "history.jsonl"
        self.window = MainWindow(history_path=self.path, check_health=False)

    def tearDown(self):
        if self.window.controller.running:
            self.window.controller.close()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.tmp.cleanup()

    def test_offline_can_navigate_history_and_settings_but_cannot_launch(self):
        self.window.on_health(ModelHealth(False, "LM Studio выключен"))
        self.assertFalse(self.window.run_panel.start_button.isEnabled())
        self.window.start_run()
        self.assertFalse(self.window.controller.running)
        QTest.mouseClick(self.window.nav_buttons[1], Qt.LeftButton)
        self.assertEqual(self.window.stack.currentIndex(), 1)
        QTest.mouseClick(self.window.nav_buttons[2], Qt.LeftButton)
        self.assertEqual(self.window.stack.currentIndex(), 2)
        self.assertIn("Настройки", self.window.page_title.text())

    def test_numeric_sort_and_filter_survive_reload(self):
        store = HistoryStore(self.path)
        for title, company, score in [
            ("First", "Alpha", 9),
            ("Second", "Beta", 100),
            ("Third", "Beta", 65),
        ]:
            store.append(
                {
                    "vacancy": {"title": title, "company": company},
                    "result": {"score": score},
                }
            )
        panel = self.window.vacancies
        panel.load()
        panel.proxy.sort(2, Qt.DescendingOrder)
        self.assertEqual(panel.proxy.index(0, 0).data(), "Second")
        self.assertEqual(panel.proxy.index(0, 1).data(), "Beta")
        panel.filter.setText("Alpha")
        self.assertEqual(panel.proxy.rowCount(), 1)
        panel.load()
        self.assertEqual(panel.proxy.rowCount(), 1)
        self.assertEqual(panel.proxy.index(0, 0).data(), "First")

    def test_manual_default_and_real_event_counters(self):
        panel = self.window.run_panel
        self.assertEqual(panel.mode.currentData(), "manual")
        panel.on_event(
            {
                "type": "decision_made",
                "processed": 5,
                "apply": 2,
                "review": 1,
                "reject": 2,
                "total": 10,
            }
        )
        self.assertEqual(
            [metric.value.text() for metric in panel.metrics], ["5", "2", "1", "2"]
        )
        self.assertEqual(panel.progress.value(), 50)

    def test_rewrite_and_cancel_have_explicit_responses(self):
        dialog = ReviewDialog(
            {"type": "application_review", "cover_letter": "<b>literal text</b>"}
        )
        dialog.instruction.setPlainText("Сделай короче")
        dialog.rewrite()
        self.assertEqual(
            dialog.response, {"action": "regenerate", "instruction": "Сделай короче"}
        )
        dialog.close()
        login = ReviewDialog({"type": "session_confirmation"})
        login.reject()
        self.assertEqual(login.response, {"action": "skip"})
        login.close()

    def test_inherited_environment_event_stream_and_nonzero_exit(self):
        fixture = Path(self.tmp.name) / "apply.py"
        fixture.write_text(
            "import os,sys,json\n"
            "assert os.environ.get('PATH')\n"
            "assert os.environ['JOBHUNTER_GUI_MODE']=='manual'\n"
            "assert 'JOBHUNTER_GUI_CONFIRMED' not in os.environ\n"
            "sys.stderr.buffer.write(('__AIH_EVENT__'+json.dumps({'type':'decision_made','processed':1,'apply':1})+'\\n').encode())\n"
            "sys.stderr.flush()\n"
            "sys.stdout.buffer.write('Готово без перевода строки'.encode())\n"
            "sys.stdout.flush()\n"
            "sys.exit(2)\n",
            encoding="utf-8",
        )
        controller = self.window.controller
        completed = QSignalSpy(controller.completed)
        events = QSignalSpy(controller.event)
        with patch("hunter.process.ROOT", Path(self.tmp.name)):
            controller.start("manual")
            self.assertTrue(wait_until(lambda: completed.count() == 1))
        self.assertEqual(completed.at(0), [2, False])
        self.assertEqual(events.count(), 1)
        self.assertIn(
            "Готово без перевода строки", self.window.run_panel.events.toPlainText()
        )
        self.assertFalse(controller.running)

    def test_failed_start_returns_to_idle(self):
        controller = self.window.controller
        completed = QSignalSpy(controller.completed)
        with patch(
            "hunter.process.sys.executable",
            str(Path(self.tmp.name) / "missing-python.exe"),
        ):
            controller.start("manual")
            self.assertTrue(wait_until(lambda: completed.count() == 1))
        self.assertFalse(controller.running)
        self.assertEqual(completed.at(0)[0], -1)

    def test_stop_terminates_worker_and_marks_interrupted(self):
        (Path(self.tmp.name) / "apply.py").write_text(
            'import time\nprint("ready",flush=True)\ntime.sleep(30)\n', encoding="utf-8"
        )
        controller = self.window.controller
        completed = QSignalSpy(controller.completed)
        with patch("hunter.process.ROOT", Path(self.tmp.name)):
            controller.start("manual")
            self.assertTrue(
                wait_until(
                    lambda: "ready" in self.window.run_panel.events.toPlainText()
                )
            )
            controller.stop()
            self.assertTrue(wait_until(lambda: completed.count() == 1))
        self.assertTrue(completed.at(0)[1])
        self.assertFalse(controller.running)


if __name__ == "__main__":
    unittest.main()
