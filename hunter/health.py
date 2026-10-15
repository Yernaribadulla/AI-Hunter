"""Bounded model readiness probe; no inference or model auto-start."""

from dataclasses import dataclass
import requests
from PySide6.QtCore import QThread, Signal
import config


@dataclass(frozen=True)
class ModelHealth:
    ready: bool
    message: str


def probe_model() -> ModelHealth:
    try:
        response = requests.get(config.LM_MODELS_URL, timeout=(1, 2))
        response.raise_for_status()
        models = response.json().get("data", [])
        ids = [item.get("id") for item in models if isinstance(item, dict)]
        if config.LM_MODEL not in ids:
            return ModelHealth(
                False, f"Загрузите модель {config.LM_MODEL} в LM Studio."
            )
        return ModelHealth(True, "Модель загружена. Можно запускать поиск.")
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        return ModelHealth(
            False,
            "LM Studio выключен или сервер недоступен. Включите Local Server и загрузите модель.",
        )


class HealthWorker(QThread):
    result = Signal(object)

    def run(self):
        self.result.emit(probe_model())
