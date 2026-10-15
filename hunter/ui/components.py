from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QFrame,
    QVBoxLayout,
    QPushButton,
    QScrollArea,
    QWidget,
)


def label(text, name="body", wrap=False):
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextFormat(Qt.PlainText)
    return widget


def button(text, callback=None, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primaryButton")
    if callback:
        widget.clicked.connect(callback)
    return widget


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(22, 20, 22, 20)
        self.box.setSpacing(10)


class Metric(Card):
    def __init__(self, title, caption, accent=False):
        super().__init__()
        self.box.setContentsMargins(18, 12, 18, 12)
        self.box.setSpacing(3)
        self.box.addWidget(label(title, "eyebrow"))
        self.value = label("0", "metricAccent" if accent else "metricValue")
        self.box.addWidget(self.value)
        self.box.addWidget(label(caption, "muted"))


def scroll_page(content):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(content)
    return area


def page_layout(widget: QWidget):
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(30, 22, 30, 24)
    layout.setSpacing(20)
    return layout
