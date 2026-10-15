"""Vacancy normalization, language checks and validated model output."""

import re
import json
from models import VacancyAnalysis


def detect_remote(vacancy_data):

    text = (
        vacancy_data.get("title", "") + "\n" + vacancy_data.get("description", "")
    ).lower()

    remote_patterns = [
        "удалённая работа",
        "удаленная работа",
        "работа из дома",
        "можно удалённо",
        "можно удаленно",
        "полностью удалённая",
        "полностью удаленная",
        "remote",
        "fully remote",
        "remote work",
        "work remotely",
        "work from home",
        "дистанционная работа",
        "дистанционно",
    ]

    return any(pattern in text for pattern in remote_patterns)


def detect_text_language(text):
    """
    Грубая эвристика: считаем кириллические и латинские буквы.
    Больше латиницы -> английский, иначе -> русский.
    """

    if not text:
        return "rus"

    cyrillic_count = len(re.findall(r"[а-яА-ЯёЁ]", text))

    latin_count = len(re.findall(r"[a-zA-Z]", text))

    if latin_count > cyrillic_count:
        return "eng"

    return "rus"


def validate_cover_letter_language(description, cover_letter):
    """Запрещает смешанные письма и письмо не на языке описания вакансии."""
    if not cover_letter:
        return False, "Пустое сопроводительное письмо."

    cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", cover_letter))
    latin = len(re.findall(r"[a-zA-Z]", cover_letter))

    if cyrillic >= 20 and latin >= 20:
        ratio = cyrillic / max(latin, 1)
        if 0.4 <= ratio <= 2.5:
            return False, "Сопроводительное письмо содержит смешанные языки."

    expected = detect_text_language(description)
    actual = detect_text_language(cover_letter)

    if expected != actual:
        return False, "Язык сопроводительного письма не совпадает с языком вакансии."

    return True, ""


def parse_llm_response(text) -> VacancyAnalysis | None:

    if not text:
        return None

    text = text.strip()

    # Markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        print()
        print("LLM НЕ ВЕРНУЛА JSON:")
        print(text)

        return None

    json_text = text[start : end + 1]

    try:
        result = json.loads(json_text)

    except json.JSONDecodeError as e:
        print()
        print("=" * 70)
        print("ОШИБКА JSON")
        print("=" * 70)
        print(e)
        print()
        print(json_text)

        return None

    if not isinstance(result, dict):
        return None

    try:
        return VacancyAnalysis.model_validate(result)
    except Exception as e:
        print()
        print("ОШИБКА СХЕМЫ LLM:")
        print(e)
        print("Отклик отклонён без отправки заявки.")
        return None
