"""Qt process lifecycle, framing, and shutdown separated from widgets."""

import sys
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from .protocol import OutputDecoder

ROOT = Path(__file__).resolve().parents[1]


class PipelineController(QObject):
    log = Signal(str)
    event = Signal(dict)
    running_changed = Signal(bool)
    completed = Signal(int, bool)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.process = None
        self.stopping = False
        self.decoders = []
        self.kill_timer = QTimer(self)
        self.kill_timer.setSingleShot(True)
        self.kill_timer.timeout.connect(self._kill)

    @property
    def running(self):
        return self.process is not None

    def start(self, mode):
        if self.running:
            return
        self.stopping = False
        self.decoders = [OutputDecoder(), OutputDecoder()]
        process = self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        for key, value in {
            "JOBHUNTER_GUI_MODE": mode,
            "JOBHUNTER_GUI_EVENTS": "1",
            "JOBHUNTER_GUI_BRIDGE_PORT": str(self.bridge.server_address[1]),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        }.items():
            env.insert(key, value)
        env.remove("JOBHUNTER_GUI_CONFIRMED")
        process.setProcessEnvironment(env)
        process.setWorkingDirectory(str(ROOT))
        process.setProgram(sys.executable)
        process.setArguments(["-u", str(ROOT / "apply.py")])
        process.readyReadStandardOutput.connect(self.read_output)
        process.readyReadStandardError.connect(self.read_output)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._error)
        self.running_changed.emit(True)
        process.start()

    def _dispatch(self, decoder, data, final=False):
        for kind, value in decoder.feed(data, final):
            if kind == "event":
                self.event.emit(value)
            else:
                self.log.emit(value)

    def read_output(self):
        if self.process is None:
            return
        self._dispatch(self.decoders[0], bytes(self.process.readAllStandardOutput()))
        self._dispatch(self.decoders[1], bytes(self.process.readAllStandardError()))

    def _error(self, error):
        if error == QProcess.FailedToStart:
            self.log.emit("Не удалось запустить Python: " + self.process.errorString())
            self._finished(-1, QProcess.CrashExit)

    def _finished(self, code, status):
        if self.process is None:
            return
        self.read_output()
        for decoder in self.decoders:
            self._dispatch(decoder, b"", final=True)
        self.kill_timer.stop()
        process, self.process = self.process, None
        process.deleteLater()
        self.bridge.cancel_pending()
        self.running_changed.emit(False)
        self.completed.emit(code, self.stopping)

    def stop(self):
        if self.process is not None:
            self.stopping = True
            self.bridge.cancel_pending()
            self.process.terminate()
            self.kill_timer.start(2500)

    def _kill(self):
        if self.process is not None:
            self.process.kill()

    def close(self):
        if self.process is not None:
            self.stop()
            process = self.process
            if not process.waitForFinished(1000):
                process.kill()
                process.waitForFinished(1500)
