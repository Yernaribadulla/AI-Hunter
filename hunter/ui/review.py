"""Explicit native review of the actual worker browser session and letters."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit
from .components import label, button


class ReviewDialog(QDialog):
    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.response = {"action": "skip"}
        login = payload.get("type") == "session_confirmation"
        self.setWindowTitle("Вход в HeadHunter" if login else "Проверка отклика")
        self.resize(720, 490 if login else 660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(
            label(
                "HEADHUNTER / ПОДТВЕРЖДЕНИЕ" if login else "ОТКЛИК / РУЧНАЯ ПРОВЕРКА",
                "eyebrow",
            )
        )
        layout.addWidget(
            label(
                "Подтвердите вход в браузере" if login else "Письмо готово к проверке",
                "pageTitle",
                True,
            )
        )
        layout.addWidget(
            label(
                "Войдите в аккаунт в окне Chromium, которое открыл AI-Hunter. Пройдите CAPTCHA, если она появилась, затем вернитесь сюда."
                if login
                else "Прочитайте письмо целиком. Отправка произойдёт после нажатия «Отправить отклик».",
                wrap=True,
            )
        )
        if not login:
            preview = QPlainTextEdit()
            preview.setPlainText(str(payload.get("cover_letter", "")))
            preview.setReadOnly(True)
            preview.setAccessibleName("Подготовленное сопроводительное письмо")
            layout.addWidget(preview, 1)
            self.instruction = QPlainTextEdit()
            self.instruction.setPlaceholderText("Инструкция для перегенерации письма…")
            self.instruction.setAccessibleName("Инструкция для перегенерации")
            self.instruction.setMaximumHeight(90)
            layout.addWidget(self.instruction)
        else:
            layout.addStretch()
        actions = QHBoxLayout()
        actions.addWidget(
            button("Отменить запуск" if login else "Пропустить", self.reject)
        )
        actions.addStretch()
        if not login:
            rewrite = button("Переписать", self.rewrite)
            rewrite.setEnabled(False)
            self.instruction.textChanged.connect(
                lambda: rewrite.setEnabled(bool(self.instruction.toPlainText().strip()))
            )
            actions.addWidget(rewrite)
        actions.addWidget(
            button(
                "Я вошёл — продолжить" if login else "Отправить отклик",
                lambda: self.respond("confirm" if login else "send"),
                True,
            )
        )
        layout.addLayout(actions)

    def respond(self, action, instruction=""):
        self.response = {"action": action, "instruction": instruction}
        self.accept()

    def rewrite(self):
        instruction = self.instruction.toPlainText().strip()
        if instruction:
            self.respond("regenerate", instruction)
