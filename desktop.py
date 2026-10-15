"""Native AI-Hunter entry point. Run with python desktop.py."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from hunter.ui.window import MainWindow

STYLE = (Path(__file__).parent / "hunter" / "ui" / "theme.qss").read_text(
    encoding="utf-8"
)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI-Hunter")
    app.setOrganizationName("AI-Hunter")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
