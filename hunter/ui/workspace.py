from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QGridLayout,
    QComboBox,
    QPlainTextEdit,
    QProgressBar,
)
import config
from candidate import CANDIDATE
from .components import Card, Metric, label, button, page_layout


class RunPanel(QWidget):
    def __init__(self, controller):
        super().__init__()
        layout = page_layout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(30, 16, 30, 18)
        hero = Card()
        hero.setObjectName("hero")
        hero.box.addWidget(label("ВАШ СЛЕДУЮЩИЙ КАРЬЕРНЫЙ ШАГ", "eyebrow"))
        hero.box.addWidget(label("Поиск под вашим контролем.", "heroTitle", True))
        hero.box.addWidget(
            label(
                "Поиск на HeadHunter, оценка локальной моделью и персональное письмо — в одном рабочем процессе.",
                wrap=True,
            )
        )
        layout.addWidget(hero)
        self.notice = Card()
        self.notice.setObjectName("notice")
        self.notice.box.setContentsMargins(16, 12, 16, 12)
        self.health_text = label("Проверяем подключение к LM Studio…", wrap=True)
        self.notice.box.addWidget(self.health_text)
        layout.addWidget(self.notice)
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metrics = [
            Metric("ОБРАБОТАНО", "в текущем запуске"),
            Metric("ПОДХОДЯТ", "решение APPLY", True),
            Metric("НА ПРОВЕРКУ", "решение REVIEW"),
            Metric("ОТКЛОНЕНЫ", "решение REJECT"),
        ]
        for metric in self.metrics:
            metrics.addWidget(metric, 1)
        layout.addLayout(metrics)
        controls = Card()
        controls.box.setContentsMargins(20, 16, 20, 16)
        controls.box.setSpacing(8)
        controls.box.addWidget(label("Параметры запуска", "sectionTitle"))
        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Подтверждать каждый отклик", "manual")
        self.mode.addItem("Отправлять автоматически", "auto")
        self.mode.setAccessibleName("Режим отправки откликов")
        mode_label = label("Отправка")
        mode_label.setBuddy(self.mode)
        row.addWidget(mode_label)
        row.addWidget(self.mode, 1)
        self.start_button = button("Начать поиск  →", primary=True)
        self.start_button.setEnabled(False)
        self.stop_button = button("Остановить", controller.stop)
        self.stop_button.setEnabled(False)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        controls.box.addLayout(row)
        controls.box.addWidget(
            label(
                f"Астана + удалённо  /  от {CANDIDATE['minimum_salary']:,} ₸  /  до {config.MAX_TOTAL_VACANCIES} вакансий",
                "muted",
                True,
            )
        )
        self.mode_note = label("", "muted", True)
        controls.box.addWidget(self.mode_note)
        self.mode.currentIndexChanged.connect(self.update_mode_note)
        self.update_mode_note()
        layout.addWidget(controls)
        self.current = label(
            "Ожидаем запуска. История доступна и без подключения к модели.", wrap=True
        )
        self.current.setAccessibleName("Текущий этап")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.events = QPlainTextEdit()
        self.events.setObjectName("eventLog")
        self.events.setReadOnly(True)
        self.events.document().setMaximumBlockCount(2500)
        self.events.setMinimumHeight(120)
        self.events.setAccessibleName("Журнал текущего запуска")
        self.events.setPlaceholderText(
            "Здесь появятся этапы поиска, решения и сообщения процесса."
        )
        layout.addWidget(self.current)
        layout.addWidget(self.progress)
        log_heading = QHBoxLayout()
        log_heading.addWidget(label("Журнал процесса", "sectionTitle"))
        log_heading.addStretch()
        log_heading.addWidget(button("Очистить журнал", self.events.clear))
        layout.addLayout(log_heading)
        layout.addWidget(self.events, 1)
        controller.log.connect(self.events.appendPlainText)
        controller.event.connect(self.on_event)
        controller.completed.connect(self.on_completed)

    def update_mode_note(self):
        self.mode_note.setText(
            "Перед отправкой можно прочитать письмо, пропустить вакансию или попросить модель переписать текст."
            if self.mode.currentData() == "manual"
            else "Подходящие отклики отправляются без отдельного подтверждения после проверок. Используется профиль HH."
        )

    def reset(self):
        for metric in self.metrics:
            metric.value.setText("0")
        self.progress.setValue(0)
        self.current.setText("Запускаем процесс и проверяем модель…")
        self.events.appendPlainText("── Новый запуск ──")

    def on_event(self, event):
        kind = event.get("type", "")
        message = str(event.get("message", kind))
        self.events.appendPlainText(f"{event.get('timestamp', '')}  {message}")
        activity = {
            "run_started": "Подготовка запуска…",
            "browser_starting": "Открываем рабочую сессию HeadHunter…",
            "hh_ready": "Вход подтверждён. Собираем вакансии…",
            "vacancies_collected": f"Найдено {event.get('total', 0)} вакансий. Начинаем анализ…",
            "vacancy_started": f"Анализ {event.get('vacancy_index', 0)} / {event.get('total', 0)} · {event.get('title', '')}",
            "run_finished": "Обработка завершена. Результаты сохранены в истории.",
        }
        self.current.setText(activity.get(kind, message))
        for metric, key in zip(
            self.metrics, ("processed", "apply", "review", "reject")
        ):
            if event.get(key) is not None:
                metric.value.setText(str(event[key]))
        total = event.get("total")
        if total and event.get("processed") is not None:
            self.progress.setValue(min(100, int(event["processed"] * 100 / total)))

    def on_completed(self, code, stopped):
        text = (
            "Процесс остановлен. Проверьте историю перед повторным запуском."
            if stopped
            else f"Процесс завершился с ошибкой ({code}). Подробности — в журнале."
            if code
            else "Процесс завершён. Сохранённые результаты доступны в истории."
        )
        self.current.setText(text)
        self.events.appendPlainText(text)


class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = page_layout(self)
        layout.addWidget(label("Локальная конфигурация", "sectionTitle"))
        layout.addWidget(
            label(
                "Значения загружаются из config.py и candidate.py. Настройки показаны только для чтения.",
                "muted",
                True,
            )
        )
        model = Card()
        model.box.addWidget(label("01 / ЛОКАЛЬНАЯ МОДЕЛЬ", "eyebrow"))
        model.box.addWidget(label(config.LM_MODEL, "sectionTitle", True))
        model.box.addWidget(label(config.LM_STUDIO_URL, "muted", True))
        model.box.addWidget(
            label(
                "Включите Local Server в LM Studio и загрузите указанную модель. Проверка подключения не запускает генерацию.",
                wrap=True,
            )
        )
        layout.addWidget(model)
        policy = Card()
        policy.box.addWidget(label("02 / ПРАВИЛА ОТБОРА", "eyebrow"))
        grid = QGridLayout()
        for index, (title, value) in enumerate(
            [
                ("Порог отклика", config.MIN_SCORE_TO_APPLY),
                ("Удалённая работа", config.REMOTE_MIN_SCORE_TO_APPLY),
                ("Ручная проверка", config.MIN_SCORE_TO_REVIEW),
                ("Минимальная зарплата", f"{CANDIDATE['minimum_salary']:,} ₸"),
                ("Версия промпта", config.PROMPT_VERSION),
                ("Лимит вакансий", config.MAX_TOTAL_VACANCIES),
            ]
        ):
            grid.addWidget(label(title, "muted"), index, 0)
            grid.addWidget(label(str(value)), index, 1)
        grid.setVerticalSpacing(14)
        policy.box.addLayout(grid)
        layout.addWidget(policy)
        profile = Card()
        profile.box.addWidget(label("03 / ПРОФИЛЬ КАНДИДАТА", "eyebrow"))
        profile.box.addWidget(label(CANDIDATE["name"], "sectionTitle"))
        profile.box.addWidget(
            label(
                f"{CANDIDATE['location']} · {CANDIDATE['commercial_experience_years']} года подтверждённого опыта",
                "muted",
                True,
            )
        )
        profile.box.addWidget(label(" · ".join(sorted(CANDIDATE["skills"])), wrap=True))
        layout.addWidget(profile)
        layout.addStretch()
