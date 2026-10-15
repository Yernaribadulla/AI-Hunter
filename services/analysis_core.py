import asyncio
import json
import re
import requests
import atexit
from models import Decision, VacancyAnalysis
from safety import evaluate as evaluate_safety
from config import LM_MODEL, LM_MODELS_URL, LM_STUDIO_URL
from services.prompts import SYSTEM_PROMPT, build_vacancy_prompt

ACTIVE_MODEL = None
HTTP = requests.Session()
atexit.register(HTTP.close)


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


def get_lm_model():

    response = HTTP.get(LM_MODELS_URL, timeout=5)

    response.raise_for_status()

    models = response.json().get("data", [])

    model_ids = [model.get("id") for model in models if model.get("id")]

    if not model_ids:
        raise RuntimeError("LM Studio работает, но загруженных моделей нет.")

    print()
    print("Доступные модели:")

    for model_id in model_ids:
        print(" -", model_id)

    if LM_MODEL in model_ids:
        print()
        print("Использую модель:", LM_MODEL)

        return LM_MODEL

    selected = model_ids[0]

    print()
    print("Модель", LM_MODEL, "не найдена.")

    print("Использую первую доступную:", selected)

    return selected


def ask_llm(prompt):

    if not ACTIVE_MODEL:
        raise RuntimeError("ACTIVE_MODEL не установлен.")

    response = HTTP.post(
        LM_STUDIO_URL,
        json={
            "model": ACTIVE_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1500,
        },
        timeout=300,
    )

    response.raise_for_status()

    data = response.json()

    choices = data.get("choices", [])

    if not choices:
        raise RuntimeError("LM Studio не вернула choices.")

    message = choices[0].get("message", {})

    content = message.get("content", "")

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))

        content = "".join(parts)

    return str(content)


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


def apply_safety_filter(analysis, is_remote=False, vacancy_data=None):

    return evaluate_safety(
        analysis,
        vacancy=vacancy_data,
        is_remote=is_remote,
    )


async def analyze_vacancy(vacancy_data, session_instruction=""):

    is_remote = detect_remote(vacancy_data)

    print()
    print("Формат:", "REMOTE" if is_remote else "ОБЫЧНАЯ")

    prompt = build_vacancy_prompt(vacancy_data, is_remote, session_instruction)

    try:
        raw = await asyncio.to_thread(ask_llm, prompt)

    except Exception as e:
        print()
        print("ОШИБКА LM STUDIO:")
        print(e)

        return {
            "error": "llm_error",
            "reason": str(e),
        }

    analysis = parse_llm_response(raw)

    if analysis is None:
        return {
            "error": "invalid_llm_json",
            "reason": ("LM Studio вернула некорректный JSON."),
        }

    decision: Decision = apply_safety_filter(
        analysis,
        is_remote=is_remote,
        vacancy_data=vacancy_data,
    )

    result = analysis.model_dump()
    result.update(decision.model_dump())
    result["decision"] = decision.action

    if decision.should_apply:
        valid_language, language_error = validate_cover_letter_language(
            vacancy_data.get("description", ""), result.get("cover_letter", "")
        )

        if not valid_language:
            result["action"] = "reject"
            result["should_apply"] = False
            result["decision"] = "reject"
            result["cover_letter"] = ""
            result["reason"] = (
                language_error
                + " Отклик заблокирован до повторной генерации корректного письма."
            )

    return result
