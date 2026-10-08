import asyncio
import json
import re
import requests
import os
import sys

from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from candidate import CANDIDATE, CANDIDATE_PROFILE
from models import Decision, VacancyAnalysis
from safety import evaluate as evaluate_safety
from config import (
    AREA_ASTANA,
    DEFAULT_APPLICATION_MODE,
    HH_HOST,
    HH_URL,
    HH_API_URL,
    HH_USER_AGENT,
    LM_MODEL,
    LM_MODELS_URL,
    LM_STUDIO_URL,
    MAX_TOTAL_VACANCIES,
    MAX_VACANCIES_PER_SEARCH,
    MIN_SCORE_TO_APPLY,
    MIN_SCORE_TO_REVIEW,
    PROMPT_VERSION,
    REMOTE_MIN_SCORE_TO_APPLY,
)


# ============================================================
# CONFIG
# ============================================================

SEARCH_URLS = [

    # Backend / Python discovery
    "https://astana.hh.kz/search/vacancy?text=Python+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Backend+Python&area=160",
    "https://astana.hh.kz/search/vacancy?text=Python+Automation&area=160",
    "https://astana.hh.kz/search/vacancy?text=Backend+Developer&area=160",

    # Fullstack / Web discovery
    "https://astana.hh.kz/search/vacancy?text=Full-stack+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Fullstack+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Full+Stack+разработчик&area=160",
    "https://astana.hh.kz/search/vacancy?text=Фуллстак+разработчик&area=160",
    "https://astana.hh.kz/search/vacancy?text=Веб-разработчик&area=160",
    "https://astana.hh.kz/search/vacancy?text=Web+Developer&area=160",

    # JavaScript / TypeScript discovery
    "https://astana.hh.kz/search/vacancy?text=React+Node.js&area=160",
    "https://astana.hh.kz/search/vacancy?text=React+TypeScript&area=160",
    "https://astana.hh.kz/search/vacancy?text=JavaScript+Fullstack&area=160",
    "https://astana.hh.kz/search/vacancy?text=TypeScript+Developer&area=160",

    # AI / LLM / integration discovery
    "https://astana.hh.kz/search/vacancy?text=AI+Integration+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=AI+Automation&area=160",
    "https://astana.hh.kz/search/vacancy?text=AI+Engineer&area=160",
    "https://astana.hh.kz/search/vacancy?text=AI+Assistant&area=160",
    "https://astana.hh.kz/search/vacancy?text=LLM&area=160",
    "https://astana.hh.kz/search/vacancy?text=API+Integration&area=160",
    "https://astana.hh.kz/search/vacancy?text=Integration+Developer&area=160",

    # Automation / RPA / no-code discovery
    "https://astana.hh.kz/search/vacancy?text=Automation+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=RPA&area=160",
    "https://astana.hh.kz/search/vacancy?text=n8n&area=160",
    "https://astana.hh.kz/search/vacancy?text=Make.com&area=160",
    "https://astana.hh.kz/search/vacancy?text=No-Code&area=160",
    "https://astana.hh.kz/search/vacancy?text=Zapier&area=160",

    # CRM / business systems discovery
    "https://astana.hh.kz/search/vacancy?text=CRM+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=amoCRM&area=160",
    "https://astana.hh.kz/search/vacancy?text=Bitrix24&area=160",
    "https://astana.hh.kz/search/vacancy?text=Integration+Specialist&area=160",

    # Junior / entry-level discovery
    "https://astana.hh.kz/search/vacancy?text=Junior+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Стажер+Python&area=160",
    "https://astana.hh.kz/search/vacancy?text=Python+разработчик&area=160",
]

# Keep the discovery area configurable even though the query list is readable.
SEARCH_URLS = [url.replace("area=160", f"area={AREA_ASTANA}") for url in SEARCH_URLS]


# Максимум вакансий за запуск
# ============================================================
# LM STUDIO
# ============================================================

# ============================================================
# FILES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SESSION_DIR = BASE_DIR / "hh_session"
# Совместимость со старой структурой проекта, где сессия лежала в JobHunter/hh_session.
LEGACY_SESSION_DIR = BASE_DIR / "JobHunter" / "hh_session"
if not SESSION_DIR.exists() and LEGACY_SESSION_DIR.exists():
    SESSION_DIR = LEGACY_SESSION_DIR
RESULTS_FILE = BASE_DIR / "results.jsonl"

# ============================================================
# RESUME PDF ATTACHMENT
# ============================================================

# Резюме берётся из профиля HH. Загрузка локального PDF отключена.
ATTACH_RESUME_PDF = False

# Резюме должны лежать в той же папке, что и этот скрипт.
# Если у тебя другие имена файлов - поменяй пути тут.
RESUME_PATH_RUS = BASE_DIR / "output" / "pdf" / "Resume_Yernar_Ibadulla_Russian_Final.pdf"
RESUME_PATH_ENG = BASE_DIR / "output" / "pdf" / "Resume_Yernar_Ibadulla_AI_Integration_Backend_Final.pdf"

# При необходимости новые PDF можно подключить без правки кода.
RESUME_PATH_RUS = Path(os.getenv("JOBHUNTER_RESUME_RUS", str(RESUME_PATH_RUS)))
RESUME_PATH_ENG = Path(os.getenv("JOBHUNTER_RESUME_ENG", str(RESUME_PATH_ENG)))


# ============================================================
# GLOBAL
# ============================================================

ACTIVE_MODEL = None
APPLICATION_MODE = DEFAULT_APPLICATION_MODE
SESSION_LLM_INSTRUCTION = ""


# ============================================================
# TIME
# ============================================================

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# REMOTE DETECTION
# ============================================================

def detect_remote(vacancy_data):

    text = (
        vacancy_data.get("title", "")
        + "\n"
        + vacancy_data.get("description", "")
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

    return any(
        pattern in text
        for pattern in remote_patterns
    )


# ============================================================
# RESUME LANGUAGE DETECTION
# ============================================================

def detect_text_language(text):
    """
    Грубая эвристика: считаем кириллические и латинские буквы.
    Больше латиницы -> английский, иначе -> русский.
    """

    if not text:
        return "rus"

    cyrillic_count = len(
        re.findall(
            r"[а-яА-ЯёЁ]",
            text
        )
    )

    latin_count = len(
        re.findall(
            r"[a-zA-Z]",
            text
        )
    )

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


def pick_resume_path(vacancy_data, analysis):
    """
    Выбирает PDF резюме под язык вакансии.
    Смотрит на описание вакансии + сгенерированное сопроводительное письмо,
    т.к. письмо уже определено LLM на языке вакансии.
    """

    combined_text = (
        vacancy_data.get("description", "")
        + "\n"
        + str(
            analysis.get(
                "cover_letter",
                ""
            )
        )
    )

    language = detect_text_language(
        combined_text
    )

    if language == "eng":
        return RESUME_PATH_ENG

    return RESUME_PATH_RUS


# ============================================================
# PREVIOUS APPLICATIONS
# ============================================================

def load_processed_ids():

    processed = set()

    if not RESULTS_FILE.exists():
        return processed

    try:

        with RESULTS_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:

                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                vacancy = record.get("vacancy", {})
                result = record.get("result", {})

                vacancy_id = vacancy.get("id")
                status = result.get("status")

                if vacancy_id and status in {
                    # Финальные статусы: повторно не анализируем.
                    "applied",
                    "already_applied",
                    "rejected_by_ai",
                }:
                    processed.add(
                        str(vacancy_id)
                    )

    except Exception as e:

        print()
        print("Ошибка чтения results.jsonl:")
        print(e)

    return processed


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(vacancy, result):

    result = dict(result)
    result.setdefault("model", ACTIVE_MODEL or LM_MODEL)
    result.setdefault("prompt_version", PROMPT_VERSION)
    result.setdefault("application_mode", APPLICATION_MODE)
    result.setdefault("decision_reason", result.get("reason", ""))

    record = {
        "timestamp": now_iso(),
        "vacancy": vacancy,
        "result": result,
    }

    try:

        with RESULTS_FILE.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False
                )
                + "\n"
            )

    except Exception as e:

        print()
        print("ОШИБКА СОХРАНЕНИЯ:")
        print(e)


# ============================================================
# LM STUDIO
# ============================================================

def get_lm_model():

    response = requests.get(
        LM_MODELS_URL,
        timeout=5
    )

    response.raise_for_status()

    models = response.json().get(
        "data",
        []
    )

    model_ids = [
        model.get("id")
        for model in models
        if model.get("id")
    ]

    if not model_ids:

        raise RuntimeError(
            "LM Studio работает, но загруженных моделей нет."
        )

    print()
    print("Доступные модели:")

    for model_id in model_ids:
        print(" -", model_id)

    if LM_MODEL in model_ids:

        print()
        print(
            "Использую модель:",
            LM_MODEL
        )

        return LM_MODEL

    selected = model_ids[0]

    print()
    print(
        "Модель",
        LM_MODEL,
        "не найдена."
    )

    print(
        "Использую первую доступную:",
        selected
    )

    return selected


def check_lm_studio():

    global ACTIVE_MODEL

    print()
    print("=" * 70)
    print("ПРОВЕРКА LM STUDIO")
    print("=" * 70)

    try:

        ACTIVE_MODEL = get_lm_model()

        print()
        print("LM Studio доступна.")

        return True

    except Exception as e:

        print()
        print("LM Studio недоступна.")
        print(e)

        return False


def wait_for_hh_login(page):
    """Останавливает pipeline до ручного входа в HH."""
    print()
    print("=" * 70)
    print("ТРЕБУЕТСЯ ВХОД В HH")
    print("=" * 70)
    print("1. В открывшемся браузере войдите в аккаунт HH.")
    print("2. При необходимости пройдите CAPTCHA и дождитесь загрузки профиля.")
    print('3. Вернитесь в консоль и введите точно: Подтвердить')

    while True:
        confirmation = input("\nВаш ввод: ").strip().casefold()
        if confirmation == "подтвердить":
            break
        print('Ожидается команда "Подтвердить". Браузер оставлен открытым.')

    try:
        page.reload(wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        raise RuntimeError(f"Не удалось проверить сессию HH после входа: {e}") from e

    print("Сессия HH подтверждена. Переходим к сбору и анализу вакансий.")


def choose_application_mode():
    gui_mode = os.getenv("JOBHUNTER_GUI_MODE")
    if gui_mode in {"auto", "manual"}:
        print("Режим выбран GUI:", gui_mode)
        return gui_mode

    print()
    print("=" * 70)
    print("РЕЖИМ ОТПРАВКИ ОТКЛИКОВ")
    print("=" * 70)
    print("1. Автоматическая отправка откликов")
    print("2. Отправка откликов только при подтверждении")

    while True:
        choice = input("\nВыберите режим (1/2): ").strip()
        if choice == "1":
            print("Выбран автоматический режим.")
            return "auto"
        if choice == "2":
            print("Выбран режим подтверждения каждого отклика.")
            return "manual"
        print("Введите 1 или 2.")


async def review_cover_letter(cover_letter):
    print()
    print("РЕЖИМ ПОДТВЕРЖДЕНИЯ")
    print("Нажмите ENTER, чтобы отправить этот отклик.")
    print("Введите инструкцию для модели, чтобы переписать письмо для этой сессии.")
    print("Введите 'пропустить', чтобы не отправлять эту вакансию.")
    answer = input("\nВаш выбор: ").strip()

    if not answer:
        return "send", ""
    if answer.casefold() in {"пропустить", "skip", "отмена", "cancel"}:
        return "skip", ""
    return "regenerate", answer


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = r"""
Ты — AI-рекрутер, который принимает решение:
СТОИТ ЛИ КАНДИДАТУ ОТКЛИКАТЬСЯ НА ВАКАНСИЮ.

Твоя задача — оценить реальное соответствие вакансии кандидату,
а не механически сравнивать список технологий.

============================================================
ГЛАВНЫЙ ПРИНЦИП
============================================================

СНАЧАЛА ОЦЕНИ ОСНОВНУЮ РАБОТУ.

Не отклоняй вакансию только потому, что кандидат не знает
один конкретный фреймворк, библиотеку, облако или инструмент.

Смотри на:

1. Чем кандидат будет заниматься каждый день.
2. Совпадает ли это с основным профессиональным направлением.
3. Есть ли у кандидата фундаментальные навыки для выполнения работы.
4. Насколько отсутствующие технологии критичны.
5. Требуется ли реальный production/commercial experience.
6. Соответствует ли вакансия уровню кандидата.

Пример:

Python + REST API + backend
+
FastAPI + Docker + PostgreSQL

может быть хорошим match, если FastAPI/Docker/PostgreSQL
не являются единственной центральной специализацией вакансии.

Python + LLM + Function Calling + API integrations
+
LangChain

может быть хорошим AI Integration match.

Отсутствие конкретного инструмента НЕ является причиной отказа,
если у кандидата есть сильная transferable foundation.

============================================================
КАНДИДАТ
============================================================

Используй данные кандидата, переданные в запросе.

Target seniority:
Middle

Minimum acceptable seniority:
Junior+

Основные направления:

- AI Integration
- AI Developer
- AI Automation
- Python Developer
- Backend Developer
- Automation Developer
- Integration Developer
- ETL Developer
- BI Developer

Не считай отсутствие слова "Middle" в названии вакансии проблемой,
если реальные обязанности соответствуют уровню кандидата.

Кандидат НЕ должен искусственно занижаться до Junior,
если вакансия фактически соответствует Middle-профилю.

============================================================
ПРАВДИВОСТЬ
============================================================

ЭТО КРИТИЧЕСКИ ВАЖНО.

НИКОГДА не придумывай:

- работодателей;
- должности;
- commercial experience;
- годы опыта;
- технологии;
- сертификаты;
- обязанности;
- production experience;
- проекты, которых нет в данных кандидата.

Если конкретный опыт не указан как подтверждённый,
НЕ называй его подтверждённым.

Собственные проекты = practical/project experience.

Собственные проекты НЕ являются commercial experience.

Не утверждай, что кандидат работал в компании,
если этого нет в данных кандидата.

============================================================
COMMERCIAL EXPERIENCE
============================================================

S-Dental является подтверждённым commercial experience.

Подтверждённые направления:

- AI assistants
- AI-powered customer communication
- Knowledge Base Design
- Function Calling
- Google Calendar API
- amoCRM API
- Kaspi API
- workflow automation
- NextBot
- Make
- n8n

Используй этот опыт только там, где он действительно релевантен.

Не расширяй его искусственно.

============================================================
HARD BLOCKER
============================================================

hard_blocker = true разрешён ТОЛЬКО если одновременно выполняются
ВСЕ три условия:

1. Отсутствующий навык является центральной специализацией работы.
2. Без этого навыка кандидат фактически не сможет выполнять
   основную работу.
3. У кандидата нет разумной transferable foundation.

Пример настоящего hard blocker:

Junior iOS Developer
+
основная работа — Swift/iOS development.

Candidate:
Python/backend/AI.

=> hard_blocker = true.

Другие примеры:

Embedded C/C++ Engineer
+
основная работа — embedded C/C++.

ML Research Engineer
+
основная работа — mathematical ML/deep learning research.

Computer Vision Research Engineer
+
основная работа — CV research + PyTorch/TensorFlow.

CAD Engineer
+
основная работа — профессиональная CAD automation.

============================================================
НЕ СЧИТАЙ HARD BLOCKER
============================================================

Следующие технологии сами по себе НЕ являются hard blocker:

- pytest
- unittest
- Postman
- Requests
- HTTPX
- Docker
- PostgreSQL
- MySQL
- Redis
- AWS
- Azure
- GCP
- CI/CD
- LangChain
- LangGraph
- RAG
- vector databases

Если основная работа соответствует Python/backend/AI/automation,
эти технологии обычно являются transferable/learnable skills.

============================================================
CRITICAL MISSING SKILLS
============================================================

critical_missing_skills — это информационное поле.

Оно показывает важные отсутствующие навыки.

Но:

critical_missing_skills НЕ означает автоматически reject.

Если:

hard_blocker = false

то отсутствие этих навыков само по себе
не должно превращать подходящую вакансию в reject.

Пример:

Python Automation Developer

Requirements:
Python
pytest
Docker
CI/CD
Postman

Candidate:
Python
REST API
Git
Linux

pytest/Docker/CI/CD могут быть missing,
но вакансия всё ещё может быть подходящей.

============================================================
TRANSFERABLE SKILLS
============================================================

Разрешено указывать transferable skills,
если существующий опыт действительно даёт основу.

Примеры:

Python
- FastAPI
- Django
- Flask

SQL
- PostgreSQL
- MySQL

REST API
- API frameworks
- Requests
- HTTPX

Python + API
- Requests
- HTTPX

LLM
- LangChain
- LangGraph

LLM + Knowledge Base Design
- RAG concepts

Git + GitHub + Linux
- basic DevOps concepts

AI automation
- workflow automation platforms

Python
- basic pytest/unittest concepts

ВАЖНО:

transferable_skill НЕ равен confirmed_skill.

Не говори в cover letter:
"I have extensive FastAPI experience"

если FastAPI не указан среди подтверждённых навыков.

============================================================
SENIORITY
============================================================

Оценивай не только title, но и реальные обязанности.

Junior / Intern / Trainee:
будь гибким.

Junior+:
будь гибким, если основная работа хорошо совпадает.

Middle:
будь умеренно строгим.

Senior:
будь строгим.

Lead / Principal:
будь очень строгим.

Если вакансия требует:

"3-5+ years of commercial experience"
"5+ years production experience"
"proven senior production experience"

и такой опыт отсутствует,
это серьёзный негативный фактор.

Если Middle-вакансия просто перечисляет широкий стек
без жёсткого требования многолетнего production experience,
не отклоняй её автоматически.

============================================================
REMOTE
============================================================

Remote является дополнительным преимуществом.

Если remote-вакансия соответствует одному из направлений:

- Python
- Backend
- AI
- LLM
- Automation
- API
- Integrations
- Full-stack
- ETL
- BI

будь более гибким к вторичным технологиям.

Но:

REMOTE НЕ ОТМЕНЯЕТ НАСТОЯЩИЙ HARD BLOCKER.

============================================================
AI ENGINEER
============================================================

Не отклоняй вакансию только потому,
что title содержит "AI Engineer".

Определи реальные обязанности.

Если работа включает:

- LLM integrations
- AI assistants
- Function Calling
- API integrations
- business automation
- workflow automation
- AI-powered applications
- prompt engineering
- integration with external services

оценивай вакансию как AI Integration / AI Automation.

Если основная работа включает:

- ML Research
- Deep Learning Research
- Computer Vision Research
- PyTorch/TensorFlow engineering
- model training
- mathematical ML
- создание ML-моделей с нуля

это слабый match.

============================================================
ROLE FIT
============================================================

Сильные направления кандидата:

- AI Integration
- AI Developer
- AI Automation
- Python
- Backend
- Automation
- API / Integrations
- LLM Integration
- Full-stack
- ETL
- BI

Нерелевантные направления:

- Sales
- HR
- Accounting
- pure Marketing
- Legal
- Construction
- Medicine
- unrelated Engineering
- Manual QA
- Technical Support
- System Administration
- pure Frontend

Если вакансия является смешанной,
оценивай её по основной части обязанностей.

============================================================
SCORING
============================================================

Оценивай вакансию по пяти критериям:

role_fit: 0-25
core_skill_fit: 0-30
task_fit: 0-20
experience_fit: 0-15
additional_fit: 0-10

Итоговый score должен быть суммой этих пяти показателей.

Максимум = 100.

Интерпретация:

90-100 = exceptional
80-89 = strong
75-79 = good
70-74 = potentially good
60-69 = borderline
40-59 = weak
0-39 = very poor

Не завышай score только потому,
что в вакансии есть несколько знакомых технологий.

Основная работа важнее количества совпавших keywords.

============================================================
DIRECTION MATCH
============================================================

direction_match = true,
если основная профессиональная деятельность вакансии
соответствует хотя бы одному сильному направлению кандидата.

direction_match = false,
если вакансия относится к принципиально другому профессиональному
направлению.

Пример:

Python Backend Developer
=> true

AI Integration Developer
=> true

Automation Developer
=> true

Full-stack Developer с сильным backend/API компонентом
=> true

Pure Frontend React Developer
=> false

Sales Manager
=> false

Manual QA
=> false

System Administrator
=> false

============================================================
DECISION
============================================================

ОБЫЧНАЯ ВАКАНСИЯ:

should_apply = true,
если одновременно:

score >= 65
direction_match = true
hard_blocker = false
нет обязательного Senior/Lead/Principal production experience,
которого у кандидата нет.

REMOTE:

should_apply = true,
если одновременно:

score >= 60
direction_match = true
hard_blocker = false
нет обязательного Senior/Lead/Principal production experience,
которого у кандидата нет.

ВАЖНО:

Не делай reject только из-за missing secondary technologies.

Пример:

score = 78
hard_blocker = false
critical_missing_skills = ["Docker", "pytest", "CI/CD"]

Если основная работа подходит,
should_apply = true.

============================================================
КОГДА НУЖНО ОТКАЗАТЬ
============================================================

Отказывай, если:

1. hard_blocker = true;

ИЛИ

2. direction_match = false;

ИЛИ

3. вакансия требует уровень/production experience,
   который принципиально выше возможностей кандидата;

ИЛИ

4. score ниже соответствующего порога.

Не создавай дополнительные причины для отказа,
которых нет в правилах выше.

============================================================
COVER LETTER — LANGUAGE
============================================================

Язык сопроводительного письма определяется
ТОЛЬКО основным текстом DESCRIPTION вакансии.

НЕ определяй язык по:

- title;
- названию компании;
- названию технологий;
- слову Remote;
- URL.

Если description преимущественно русский:
письмо на русском.

Если description преимущественно казахский:
письмо на казахском.

Если description преимущественно английский:
письмо на английском.

Если description смешанный:
используй язык, который занимает большую часть
естественного текста описания.

Технические термины не учитывай как доказательство языка.

КРИТИЧЕСКОЕ ПРАВИЛО: cover_letter должен быть написан
только на одном языке. Не смешивай русский и английский
в одном письме. Английские названия технологий и компаний
можно оставлять как собственные названия, но все предложения
и связный текст должны быть на выбранном языке вакансии.

Например:

Title:
Python Backend Developer

Description:
"Мы ищем разработчика, который будет заниматься API..."

=> письмо на русском.

============================================================
COVER LETTER — CONTENT
============================================================

Если should_apply = true,
сгенерируй сопроводительное письмо длиной примерно 400-700 символов.

Письмо должно быть:

- естественным;
- коротким;
- профессиональным;
- конкретным;
- без шаблонного HR-пафоса;
- связано с реальными задачами вакансии;
- написано на языке вакансии.

Упоминай только подтверждённые навыки кандидата.

Можно использовать transferable knowledge
для понимания соответствия вакансии,
НО НЕЛЬЗЯ выдавать transferable skill
за подтверждённый коммерческий опыт.

Не пиши:

"I am the perfect candidate."

Не пиши:

"I have X years of experience"

если количество лет не подтверждено.

Не называй собственные проекты commercial experience.

Не придумывай опыт работы в компаниях.

============================================================
ОБЯЗАТЕЛЬНАЯ КОНЦОВКА ПИСЬМА
============================================================

КАЖДОЕ письмо ОБЯЗАНО ЗАКАНЧИВАТЬСЯ
ТОЧНО этой фразой:

"Я готов к живому интервью и готов доказать свои способности!"

Фраза должна находиться в самом конце письма.

Не изменяй её.

Не переводи её.

Не добавляй после неё никаких слов.

Даже если письмо написано на английском или казахском,
эта фраза всё равно должна остаться именно в таком виде.

============================================================
ЕСЛИ SHOULD_APPLY = FALSE
============================================================

cover_letter должен быть:

""

Не генерируй письмо для rejected вакансий.

============================================================
OUTPUT
============================================================

Верни ТОЛЬКО валидный JSON.

Никакого Markdown.

Никаких ```json.

Никаких пояснений до или после JSON.

Используй строго такую структуру:

{
    "score": 0,
    "should_apply": false,

    "job_level": "unknown",

    "direction_match": false,

    "hard_blocker": false,
    "hard_blocker_reason": "",

    "commercial_experience_required": false,
    "commercial_experience_mandatory": false,
    "required_commercial_years": null,
    "salary_known": false,
    "salary_min": null,
    "salary_max": null,

    "matched_skills": [],
    "transferable_skills": [],
    "missing_skills": [],
    "critical_missing_skills": [],
    "language": "ru",
    "is_remote": false,

    "reason": "",

    "cover_letter": ""
}

============================================================
ФИНАЛЬНАЯ ПРОВЕРКА ПЕРЕД JSON
============================================================

Перед формированием ответа проверь:

1. Основная работа вакансии соответствует кандидату?
2. direction_match определён по реальным обязанностям?
3. hard_blocker установлен только при выполнении ВСЕХ трёх условий?
4. Missing secondary technologies не использованы как автоматический reject?
5. Senior/Middle production requirements проверены?
6. Score соответствует реальному match?
7. should_apply соответствует установленному порогу?
8. Cover letter использует только подтверждённые факты?
9. Если should_apply = true, письмо присутствует?
10. Если should_apply = false, cover_letter = ""?
11. Письмо написано на языке DESCRIPTION?
12. Письмо заканчивается ТОЧНО:
"Я готов к живому интервью и готов доказать свои способности!"?
13. После этой фразы нет никакого текста?

Только после этой проверки верни JSON.
"""


# ============================================================
# VACANCY PROMPT
# ============================================================

def build_vacancy_prompt(
    vacancy_data,
    is_remote,
    session_instruction=""
):

    remote_status = (
        "REMOTE"
        if is_remote
        else "NOT CONFIRMED REMOTE"
    )

    # ВАЖНО:
    # JSON здесь НЕ является f-string interpolation.
    # Поэтому никаких проблем с { } не будет.

    return """
CANDIDATE
=========

%s

============================================================
VACANCY
============================================================

TITLE:
%s

DESCRIPTION:
%s

============================================================
WORK FORMAT
============================================================

%s

============================================================
ANALYSIS
============================================================

Analyze the vacancy using the system rules.

Pay special attention to:

1. Actual job responsibilities.
2. Actual seniority.
3. Core technologies.
4. Transferable technologies.
5. Commercial experience requirements.
6. Hard blockers.
7. Whether the candidate can realistically perform the job.

DO NOT turn every missing technology into a hard blocker.

For a Junior/Junior+ Python/backend/AI automation role,
missing pytest, Docker, PostgreSQL, CI/CD, Postman, Requests,
etc. should normally be treated as learnable/transferable
unless they are genuinely the central specialization.

IMPORTANT:

If the role is relevant and the missing skills are learnable,
the candidate should receive a good score.

============================================================
DECISION
============================================================

Normal vacancy:
apply threshold = %s.

Remote vacancy:
apply threshold = %s.

Do not reject solely because critical_missing_skills is non-empty.

A rejection based on missing skills requires:
hard_blocker = true.

============================================================
COVER LETTER
============================================================

Generate a cover letter only if should_apply = true.

The language MUST follow the dominant language
of the vacancy description.

Russian vacancy -> Russian letter.
Kazakh vacancy -> Kazakh letter.
English vacancy -> English letter.

Do not use English merely because the title is English.

SESSION-ONLY USER INSTRUCTION
=============================
%s

Apply this instruction only to the current cover letter generation session.
Do not invent experience, companies, technologies or achievements.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

{
    "score": 0,
    "should_apply": false,
    "job_level": "unknown",
    "direction_match": false,
    "hard_blocker": false,
    "hard_blocker_reason": "",
    "commercial_experience_required": false,
    "commercial_experience_mandatory": false,
    "required_commercial_years": null,
    "salary_known": false,
    "salary_min": null,
    "salary_max": null,
    "matched_skills": [],
    "transferable_skills": [],
    "missing_skills": [],
    "critical_missing_skills": [],
    "language": "ru",
    "is_remote": false,
    "reason": "",
    "cover_letter": ""
}
""" % (
        CANDIDATE_PROFILE,
        vacancy_data.get("title", ""),
        vacancy_data.get("description", "")[:20000],
        remote_status,
        MIN_SCORE_TO_APPLY,
        REMOTE_MIN_SCORE_TO_APPLY,
        session_instruction or "No additional instruction.",
    )


# ============================================================
# ASK LLM
# ============================================================

def ask_llm(prompt):

    if not ACTIVE_MODEL:
        raise RuntimeError(
            "ACTIVE_MODEL не установлен."
        )

    response = requests.post(
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

    choices = data.get(
        "choices",
        []
    )

    if not choices:
        raise RuntimeError(
            "LM Studio не вернула choices."
        )

    message = choices[0].get(
        "message",
        {}
    )

    content = message.get(
        "content",
        ""
    )

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, dict):

                if item.get("type") == "text":

                    parts.append(
                        item.get(
                            "text",
                            ""
                        )
                    )

        content = "".join(parts)

    return str(content)


# ============================================================
# PARSE JSON
# ============================================================

def parse_llm_response(text) -> VacancyAnalysis | None:

    if not text:
        return None

    text = text.strip()

    # Markdown fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:

        print()
        print("LLM НЕ ВЕРНУЛА JSON:")
        print(text)

        return None

    json_text = text[
        start:end + 1
    ]

    try:

        result = json.loads(
            json_text
        )

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


# ============================================================
# HELPERS
# ============================================================

def to_bool(value):

    if isinstance(value, bool):
        return value

    if isinstance(value, str):

        return value.strip().lower() in {
            "true",
            "yes",
            "1",
            "да",
        }

    return bool(value)


def normalize_list(value):

    if not isinstance(
        value,
        list
    ):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def salary_below_candidate_minimum(vacancy_data):
    """Return a blocking reason only when a published salary is explicit."""
    minimum = CANDIDATE.get("minimum_salary")
    if not minimum:
        return ""
    text = " ".join(
        str(vacancy_data.get(key, ""))
        for key in ("title", "description", "salary", "compensation")
    ).lower()
    amounts = [int(value.replace(" ", "")) for value in re.findall(r"(?<!\d)(\d{3}(?:[ .]\d{3})?)(?:\s*(?:₸|тг|тенге))", text)]
    if amounts and max(amounts) < minimum:
        return f"Указанная зарплата ниже минимума кандидата ({minimum:,} KZT)."
    return ""


# ============================================================
# SAFETY FILTER
# ============================================================

def apply_safety_filter(
    analysis,
    is_remote=False,
    vacancy_data=None
):

    return evaluate_safety(
        analysis,
        vacancy=vacancy_data,
        is_remote=is_remote,
    )

    if not isinstance(
        analysis,
        dict
    ):

        return {
            "score": 0,
            "should_apply": False,
            "decision": "reject",
            "reason": "Некорректный ответ AI.",
            "cover_letter": "",
        }

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    try:

        score = int(
            analysis.get(
                "score",
                0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        score = 0

    score = max(
        0,
        min(
            score,
            100
        )
    )

    # --------------------------------------------------------
    # FLAGS
    # --------------------------------------------------------

    direction_match = to_bool(
        analysis.get(
            "direction_match",
            False
        )
    )

    hard_blocker = analysis.get("hard_blocker", False)
    if not isinstance(hard_blocker, bool):
        return {
            "score": 0, "should_apply": False, "decision": "reject",
            "reason": "Некорректный hard_blocker в ответе AI.",
            "cover_letter": "",
        }

    commercial_mandatory = to_bool(
        analysis.get(
            "commercial_experience_mandatory",
            False
        )
    )

    # --------------------------------------------------------
    # LISTS
    # --------------------------------------------------------

    matched_skills = normalize_list(
        analysis.get(
            "matched_skills",
            []
        )
    )

    transferable_skills = normalize_list(
        analysis.get(
            "transferable_skills",
            []
        )
    )

    missing_skills = normalize_list(
        analysis.get(
            "missing_skills",
            []
        )
    )

    critical_missing_skills = normalize_list(
        analysis.get(
            "critical_missing_skills",
            []
        )
    )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    reason = str(
        analysis.get(
            "reason",
            ""
        )
    ).strip()

    cover_letter = str(
        analysis.get(
            "cover_letter",
            ""
        )
    ).strip()

    hard_blocker_reason = str(
        analysis.get(
            "hard_blocker_reason",
            ""
        )
    ).strip()

    job_level = str(
        analysis.get(
            "job_level",
            "unknown"
        )
    ).strip().lower()

    required_commercial_years = analysis.get("required_commercial_years")
    candidate_commercial_years = CANDIDATE.get("commercial_experience_years", 0)

    # --------------------------------------------------------
    # THRESHOLD AND CANDIDATE RULES
    # --------------------------------------------------------

    minimum_score = (
        REMOTE_MIN_SCORE_TO_APPLY
        if is_remote
        else MIN_SCORE_TO_APPLY
    )

    # --------------------------------------------------------
    # DECISION
    #
    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ:
    #
    # critical_missing_skills НЕ блокируют сами по себе.
    #
    # Блокирует только:
    # hard_blocker = true
    # --------------------------------------------------------

    salary_reason = salary_below_candidate_minimum(vacancy_data or {})

    if hard_blocker:

        decision = "reject"
        should_apply = False

        if not reason:

            reason = (
                hard_blocker_reason
                or "Есть настоящий hard blocker."
            )

    elif not direction_match:

        decision = "reject"
        should_apply = False

        if not reason:

            reason = (
                "Основное направление вакансии "
                "не соответствует профилю кандидата."
            )

    elif commercial_mandatory and required_commercial_years is not None and required_commercial_years > candidate_commercial_years:

        decision = "reject"
        should_apply = False

        if not reason:

            reason = (
                f"Вакансия требует {required_commercial_years:g} лет коммерческого опыта, "
                f"у кандидата подтверждено {candidate_commercial_years:g}."
            )

    elif salary_reason:
        decision = "reject"
        should_apply = False
        reason = reason or salary_reason

    elif score >= minimum_score:

        decision = "apply"
        should_apply = True

    elif score >= MIN_SCORE_TO_REVIEW:

        decision = "manual_review"
        should_apply = False

    else:

        decision = "reject"
        should_apply = False

    # --------------------------------------------------------
    # LETTER
    # --------------------------------------------------------

    if should_apply and not cover_letter:

        decision = "reject"
        should_apply = False

        reason = (
            reason
            + " "
            + "Отклик отменён: AI не сгенерировал "
              "сопроводительное письмо."
        ).strip()

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    return {

        "score": score,

        "should_apply":
            should_apply,

        "decision":
            decision,

        "is_remote":
            is_remote,

        "job_level":
            job_level,

        "direction_match":
            direction_match,

        "hard_blocker":
            hard_blocker,

        "hard_blocker_reason":
            hard_blocker_reason,

        "commercial_experience_required":
            to_bool(
                analysis.get(
                    "commercial_experience_required",
                    False
                )
            ),

        "commercial_experience_mandatory":
            commercial_mandatory,

        "required_commercial_years": required_commercial_years,

        "matched_skills":
            matched_skills,

        "transferable_skills":
            transferable_skills,

        "missing_skills":
            missing_skills,

        "critical_missing_skills":
            critical_missing_skills,

        "reason":
            reason,

        "cover_letter":
            cover_letter,
    }


# ============================================================
# ANALYZE VACANCY
# ============================================================

async def analyze_vacancy(
    vacancy_data,
    session_instruction=""
):

    is_remote = detect_remote(
        vacancy_data
    )

    print()
    print(
        "Формат:",
        "REMOTE"
        if is_remote
        else "ОБЫЧНАЯ"
    )

    prompt = build_vacancy_prompt(
        vacancy_data,
        is_remote,
        session_instruction
    )

    try:

        raw = await asyncio.to_thread(
            ask_llm,
            prompt
        )

    except Exception as e:

        print()
        print("ОШИБКА LM STUDIO:")
        print(e)

        return {
            "error": "llm_error",
            "reason": str(e),
        }

    analysis = parse_llm_response(
        raw
    )

    if analysis is None:

        return {
            "error": "invalid_llm_json",
            "reason": (
                "LM Studio вернула "
                "некорректный JSON."
            ),
        }

    decision: Decision = apply_safety_filter(
        analysis,
        is_remote=is_remote,
        vacancy_data=vacancy_data,
    )

    result = decision.model_dump()
    result.update(analysis.model_dump())
    result["decision"] = decision.action

    if decision.should_apply:
        valid_language, language_error = validate_cover_letter_language(
            vacancy_data.get("description", ""),
            result.get("cover_letter", "")
        )

        if not valid_language:
            result["should_apply"] = False
            result["decision"] = "reject"
            result["cover_letter"] = ""
            result["reason"] = (
                language_error
                + " Отклик заблокирован до повторной генерации корректного письма."
            )

    return result


# ============================================================
# EXTRACT VACANCY
# ============================================================

async def extract_vacancy_text(
    page
):

    title = ""

    try:

        locator = page.locator(
            '[data-qa="vacancy-title"]'
        ).first

        if await locator.count() > 0:

            title = (
                await locator.inner_text()
            ).strip()

    except Exception:
        pass

    if not title:

        try:

            title = (
                await page.title()
            ).strip()

        except Exception:

            title = ""

    description = ""

    try:

        locator = page.locator(
            '[data-qa="vacancy-description"]'
        ).first

        if await locator.count() > 0:

            description = (
                await locator.inner_text()
            ).strip()

    except Exception:
        pass

    if not description:

        try:

            description = (
                await page.locator(
                    "body"
                ).inner_text()
            ).strip()

        except Exception:

            description = ""

    return {
        "title": title,
        "description": description[:20000],
    }


# ============================================================
# CHECK ALREADY APPLIED
# ============================================================

async def check_already_applied(
    page
):

    try:

        body_text = (
            await page.locator(
                "body"
            ).inner_text()
        ).lower()

    except Exception:

        return False

    phrases = [
        "вы откликнулись",
        "вы уже откликались",
        "отклик отправлен",
        "ваш отклик отправлен",
        "вы откликались",
        "отклик был отправлен",
        "вы оставили отклик",
    ]

    return any(
        phrase in body_text
        for phrase in phrases
    )


# ============================================================
# RESPONSE BUTTON
# ============================================================

async def find_response_button(
    page
):

    selectors = [
        'a[data-qa="vacancy-response-link-top"]',
        'button[data-qa*="vacancy-response"]',
        'a[data-qa*="vacancy-response"]',
    ]

    for selector in selectors:

        locator = page.locator(
            selector
        )

        count = await locator.count()

        for i in range(count):

            candidate = locator.nth(i)

            try:

                if (
                    await candidate.is_visible()
                    and await candidate.is_enabled()
                ):

                    return candidate

            except Exception:
                continue

    try:

        locator = page.get_by_role(
            "link",
            name=re.compile(
                r"откликнуться",
                re.IGNORECASE
            )
        )

        count = await locator.count()

        for i in range(count):

            candidate = locator.nth(i)

            try:

                if (
                    await candidate.is_visible()
                    and await candidate.is_enabled()
                ):

                    return candidate

            except Exception:
                continue

    except Exception:
        pass

    return None


# ============================================================
# ADD COVER LETTER
# ============================================================

async def fill_and_verify(locator, text):
    """Заполняет поле и проверяет, что весь текст записан."""
    try:
        await locator.fill(text)
        expected = text.strip()
        try:
            actual = (await locator.input_value()).strip()
        except Exception:
            actual = (await locator.text_content() or "").strip()
        return actual == expected
    except Exception:
        return False


async def add_cover_letter(
    page,
    cover_letter
):

    if not cover_letter:
        return False

    # Existing textarea

    textareas = page.locator(
        "textarea"
    )

    count = await textareas.count()

    for i in range(count):

        candidate = textareas.nth(i)

        try:

            if await candidate.is_visible():

                if await fill_and_verify(candidate, cover_letter):
                    return True

        except Exception:
            continue

    # Add cover letter button

    try:

        button = page.get_by_role(
            "button",
            name=re.compile(
                r"добавить сопроводительное|сопроводительное письмо|добавить письмо",
                re.IGNORECASE
            )
        )

        count = await button.count()

        for i in range(count):

            candidate = button.nth(i)

            try:

                if await candidate.is_visible():

                    await candidate.click()

                    await page.wait_for_timeout(
                        700
                    )

                    break

            except Exception:
                continue

    except Exception:
        pass

    await page.wait_for_timeout(
        500
    )

    # Textarea again

    textareas = page.locator(
        "textarea"
    )

    count = await textareas.count()

    for i in range(count):

        candidate = textareas.nth(i)

        try:

            if await candidate.is_visible():

                if await fill_and_verify(candidate, cover_letter):
                    return True

        except Exception:
            continue

    # Contenteditable

    editable = page.locator(
        '[contenteditable="true"]'
    )

    count = await editable.count()

    for i in range(count):

        candidate = editable.nth(i)

        try:

            if await candidate.is_visible():

                if await fill_and_verify(candidate, cover_letter):
                    return True

        except Exception:
            continue

    # HH может отрисовать поле как ARIA textbox без textarea/contenteditable.
    textboxes = page.get_by_role("textbox")
    count = await textboxes.count()

    for i in range(count):
        candidate = textboxes.nth(i)

        try:
            if await candidate.is_visible():
                if await fill_and_verify(candidate, cover_letter):
                    return True
        except Exception:
            continue

    return False


# ============================================================
# ATTACH RESUME PDF
# ============================================================

async def find_file_input(page):

    file_inputs = page.locator(
        'input[type="file"]'
    )

    count = await file_inputs.count()

    if count > 0:
        return file_inputs.first

    return None


async def find_attach_resume_button(page):

    patterns = [
        r"прикрепить резюме",
        r"загрузить резюме",
        r"прикрепить файл",
        r"добавить файл",
        r"выбрать файл",
        r"attach resume",
        r"upload resume",
        r"attach file",
    ]

    for pattern in patterns:

        try:

            button = page.get_by_role(
                "button",
                name=re.compile(
                    pattern,
                    re.IGNORECASE
                )
            )

            count = await button.count()

            for i in range(count):

                candidate = button.nth(i)

                try:

                    if await candidate.is_visible():
                        return candidate

                except Exception:
                    continue

        except Exception:
            pass

        try:

            link = page.get_by_role(
                "link",
                name=re.compile(
                    pattern,
                    re.IGNORECASE
                )
            )

            count = await link.count()

            for i in range(count):

                candidate = link.nth(i)

                try:

                    if await candidate.is_visible():
                        return candidate

                except Exception:
                    continue

        except Exception:
            pass

    return None


async def attach_resume_pdf(
    page,
    resume_path
):
    """
    Пытается прикрепить PDF резюме к форме отклика.

    Сценарий 1:
    На форме уже есть скрытый/видимый <input type="file">
    (частый случай HH, если аккаунт без резюме в профиле).

    Сценарий 2:
    Есть кнопка "прикрепить файл", по клику на которую
    открывается системный файловый диалог
    (перехватываем через page.expect_file_chooser).

    Если ничего не найдено - просто возвращает False,
    отклик всё равно продолжает отправляться без файла
    (например если у аккаунта уже есть резюме, привязанное
    в профиле HH, и форма его использует напрямую).
    """

    if resume_path is None:

        print()
        print("Путь к резюме не задан.")

        return False

    if not resume_path.exists():

        print()
        print(
            "ФАЙЛ РЕЗЮМЕ НЕ НАЙДЕН:",
            resume_path
        )

        return False

    # --- Сценарий 1: прямой input[type=file] ---

    file_input = await find_file_input(
        page
    )

    if file_input is not None:

        try:

            await file_input.set_input_files(
                str(resume_path)
            )

            await page.wait_for_timeout(
                1500
            )

            print(
                "Резюме прикреплено (input):",
                resume_path.name
            )

            return True

        except Exception as e:

            print(
                "Ошибка прикрепления через input:",
                e
            )

    # --- Сценарий 2: кнопка + file chooser ---

    attach_button = await find_attach_resume_button(
        page
    )

    if attach_button is not None:

        try:

            async with page.expect_file_chooser() as fc_info:

                await attach_button.click()

            file_chooser = await fc_info.value

            await file_chooser.set_files(
                str(resume_path)
            )

            await page.wait_for_timeout(
                1500
            )

            print(
                "Резюме прикреплено (file chooser):",
                resume_path.name
            )

            return True

        except Exception as e:

            print(
                "Ошибка прикрепления через file chooser:",
                e
            )

    print()
    print(
        "Не найдено поле для прикрепления резюме "
        "(возможно, форма использует резюме из профиля HH)."
    )

    return False


# ============================================================
# FINAL APPLY BUTTON
# ============================================================

async def find_final_apply_button(
    page
):

    selectors = [
        'button[data-qa*="vacancy-response"]',
        'button[data-qa*="response"]',
    ]

    for selector in selectors:

        buttons = page.locator(
            selector
        )

        count = await buttons.count()

        for i in range(count):

            candidate = buttons.nth(i)

            try:

                if not (
                    await candidate.is_visible()
                    and await candidate.is_enabled()
                ):
                    continue

                text = (
                    await candidate.inner_text()
                ).strip().lower()

                if (
                    "откликнуться" in text
                    or "отправить" in text
                ):

                    return candidate

            except Exception:
                continue

    try:

        buttons = page.get_by_role(
            "button",
            name=re.compile(
                r"(откликнуться|отправить)",
                re.IGNORECASE
            )
        )

        count = await buttons.count()

        for i in range(count):

            candidate = buttons.nth(i)

            try:

                if (
                    await candidate.is_visible()
                    and await candidate.is_enabled()
                ):

                    return candidate

            except Exception:
                continue

    except Exception:
        pass

    return None


# ============================================================
# SUCCESS
# ============================================================

async def check_success(
    page,
    timeout_ms=15000
):

    phrases = [
        "вы откликнулись",
        "отклик отправлен",
        "ваш отклик отправлен",
        "отклик отправлен успешно",
        "спасибо за отклик",
    ]

    elapsed = 0

    while elapsed < timeout_ms:

        try:

            body_text = (
                await page.locator(
                    "body"
                ).inner_text()
            ).lower()

            if any(
                phrase in body_text
                for phrase in phrases
            ):

                return True

        except Exception:
            pass

        await page.wait_for_timeout(
            500
        )

        elapsed += 500

    return False


# ============================================================
# COLLECT VACANCIES
# ============================================================

async def collect_vacancies(
    page,
    search_url,
    limit=50
):

    print()
    print("=" * 70)
    print("ПОИСК ВАКАНСИЙ")
    print("=" * 70)

    print(search_url)

    try:

        await page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(
            2000
        )

    except Exception as e:

        print(
            "Ошибка:",
            e
        )

        return []

    cards = page.locator(
        '[data-qa="vacancy-serp__vacancy"]'
    )

    count = await cards.count()

    print(
        "Найдено карточек:",
        count
    )

    vacancies = []

    for i in range(
        min(count, limit)
    ):

        card = cards.nth(i)

        try:

            link = card.locator(
                'a[data-qa="serp-item__title"]'
            ).first

            if await link.count() == 0:
                continue

            title = (
                await link.inner_text()
            ).strip()

            href = await link.get_attribute(
                "href"
            )

            if not href:
                continue

            if href.startswith("/"):

                href = (
                    "https://astana.hh.kz"
                    + href
                )

            href = href.split("?")[0]

            match = re.search(
                r"/vacancy/(\d+)",
                href
            )

            if not match:
                continue

            vacancy_id = match.group(1)

            vacancies.append({
                "id": vacancy_id,
                "title": title,
                "url": (
                    "https://astana.hh.kz/"
                    f"vacancy/{vacancy_id}"
                ),
            })

        except Exception as e:

            print(
                "Ошибка карточки:",
                e
            )

    return vacancies


# ============================================================
# PROCESS ONE VACANCY
# ============================================================

async def process_vacancy(
    page,
    vacancy,
    processed_ids,
    application_mode
):
    global SESSION_LLM_INSTRUCTION

    print()
    print()
    print("#" * 70)
    print(vacancy["title"])
    print("ID:", vacancy["id"])
    print("#" * 70)

    vacancy_id = str(
        vacancy["id"]
    )

    # --------------------------------------------------------
    # LOCAL PROTECTION
    # --------------------------------------------------------

    if vacancy_id in processed_ids:

        print(
            "→ Уже был отправлен отклик ранее."
        )

        return {
            "status": "already_processed"
        }

    # --------------------------------------------------------
    # OPEN
    # --------------------------------------------------------

    try:

        await page.goto(
            vacancy["url"],
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(
            1200
        )

    except Exception as e:

        return {
            "status": "error",
            "reason": str(e),
        }

    # --------------------------------------------------------
    # HH CHECK
    # --------------------------------------------------------

    if await check_already_applied(
        page
    ):

        print(
            "→ HH показывает, что отклик уже был отправлен."
        )

        return {
            "status": "already_applied"
        }

    # --------------------------------------------------------
    # EXTRACT
    # --------------------------------------------------------

    vacancy_data = (
        await extract_vacancy_text(
            page
        )
    )

    if not vacancy_data["description"]:

        return {
            "status": "error",
            "reason": (
                "Не удалось получить описание вакансии."
            ),
        }

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    analysis = await analyze_vacancy(
        vacancy_data,
        SESSION_LLM_INSTRUCTION
    )

    if "error" in analysis:

        return {
            "status": analysis["error"],
            "reason": analysis.get(
                "reason",
                ""
            ),
        }

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print()

    print(
        "REMOTE:",
        "YES"
        if analysis.get("is_remote")
        else "NO"
    )

    print(
        "SCORE:",
        analysis.get(
            "score",
            0
        )
    )

    print(
        "РЕШЕНИЕ:",
        analysis.get(
            "decision",
            "reject"
        ).upper()
    )

    print(
        "Уровень:",
        analysis.get(
            "job_level",
            "unknown"
        )
    )

    print()
    print(
        "Совпавшие навыки:",
        ", ".join(
            analysis.get(
                "matched_skills",
                []
            )
        )
    )

    print(
        "Transferable:",
        ", ".join(
            analysis.get(
                "transferable_skills",
                []
            )
        )
    )

    print(
        "Неподтверждённые:",
        ", ".join(
            analysis.get(
                "missing_skills",
                []
            )
        )
    )

    print(
        "Критические:",
        ", ".join(
            analysis.get(
                "critical_missing_skills",
                []
            )
        )
    )

    print(
        "HARD BLOCKER:",
        analysis.get(
            "hard_blocker",
            False
        )
    )

    print()
    print("Причина:")
    print(
        analysis.get(
            "reason",
            ""
        )
    )

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------

    if analysis["decision"] == "reject":

        print()
        print("→ ПРОПУСК")

        return {
            "status": "rejected_by_ai",
            **analysis,
        }

    # --------------------------------------------------------
    # MANUAL
    # --------------------------------------------------------

    if analysis["decision"] == "manual_review":

        print()
        print("→ РУЧНАЯ ПРОВЕРКА")

        return {
            "status": "manual_review",
            **analysis,
        }

    # --------------------------------------------------------
    # APPLY
    # --------------------------------------------------------

    while True:
        cover_letter = (
            analysis.get(
                "cover_letter",
                ""
            )
            .strip()
        )

        if not cover_letter:
            print("→ ОТКАЗ: нет сопроводительного.")
            return {
                "status": "no_cover_letter",
                **analysis,
            }

        print()
        print("СОПРОВОДИТЕЛЬНОЕ:")
        print("-" * 60)
        print(cover_letter)
        print("-" * 60)

        if application_mode != "manual":
            break

        review_action, instruction = await review_cover_letter(cover_letter)

        if review_action == "send":
            break

        if review_action == "skip":
            return {
                "status": "manual_skipped",
                **analysis,
            }

        SESSION_LLM_INSTRUCTION = instruction
        print("Перегенерирую письмо с инструкцией только для этой сессии...")
        analysis = await analyze_vacancy(
            vacancy_data,
            SESSION_LLM_INSTRUCTION
        )

        if "error" in analysis:
            return {
                "status": analysis["error"],
                "reason": analysis.get("reason", ""),
            }

        if analysis.get("decision") != "apply":
            print("Модель не разрешила отправку после обновления письма.")
            return {
                "status": "rejected_after_manual_edit",
                **analysis,
            }

    # --------------------------------------------------------
    # RESPONSE BUTTON
    # --------------------------------------------------------

    response_button = (
        await find_response_button(
            page
        )
    )

    if response_button is None:

        print(
            "Кнопка отклика не найдена."
        )

        return {
            "status": "unavailable",
            **analysis,
        }

    # --------------------------------------------------------
    # OPEN FORM
    # --------------------------------------------------------

    try:

        await response_button.click()

        await page.wait_for_timeout(
            1000
        )

    except Exception as e:

        return {
            "status": "form_error",
            "reason": str(e),
            **analysis,
        }

    # Резюме не загружаем: HH использует резюме, выбранное в профиле аккаунта.

    # --------------------------------------------------------
    # COVER LETTER
    # --------------------------------------------------------

    letter_added = (
        await add_cover_letter(
            page,
            cover_letter
        )
    )

    if not letter_added:

        print(
            "Не удалось вставить письмо."
        )

        return {
            "status": "letter_error",
            **analysis,
        }

    # --------------------------------------------------------
    # FINAL BUTTON
    # --------------------------------------------------------

    await page.wait_for_timeout(
        500
    )

    final_button = (
        await find_final_apply_button(
            page
        )
    )

    if final_button is None:

        print(
            "Финальная кнопка отправки не найдена."
        )

        return {
            "status": "send_button_error",
            **analysis,
        }

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    print()
    print("ОТПРАВЛЯЮ ОТКЛИК...")

    try:

        await final_button.click()

    except Exception as e:

        return {
            "status": "send_error",
            "reason": str(e),
            **analysis,
        }

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    success = await check_success(
        page
    )

    if success:

        print()
        print("✓ ОТКЛИК ОТПРАВЛЕН")

        return {
            "status": "applied",
            **analysis,
        }

    print()
    print(
        "? Не удалось подтвердить отправку."
    )

    return {
        "status": "unknown",
        **analysis,
    }


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("JOBHUNTER — AI АВТООТКЛИК HH")
    print("=" * 70)

    print()
    print(
        "MAX_TOTAL_VACANCIES:",
        MAX_TOTAL_VACANCIES
    )

    print(
        "NORMAL APPLY SCORE:",
        MIN_SCORE_TO_APPLY
    )

    print(
        "REMOTE APPLY SCORE:",
        REMOTE_MIN_SCORE_TO_APPLY
    )

    print(
        "ATTACH_RESUME_PDF:",
        ATTACH_RESUME_PDF
    )

    if ATTACH_RESUME_PDF:

        print(
            "Резюме RUS:",
            RESUME_PATH_RUS,
            "-",
            "найден" if RESUME_PATH_RUS.exists() else "НЕ НАЙДЕН"
        )

        print(
            "Резюме ENG:",
            RESUME_PATH_ENG,
            "-",
            "найден" if RESUME_PATH_ENG.exists() else "НЕ НАЙДЕН"
        )

    # --------------------------------------------------------
    # LM STUDIO
    # --------------------------------------------------------

    if not check_lm_studio():

        print()
        print(
            "Запусти LM Studio с Local Server."
        )

        return

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    if not SESSION_DIR.exists():

        print()
        print("ОШИБКА:")
        print(
            "Не найдена папка:",
            SESSION_DIR
        )

        return

    # --------------------------------------------------------
    # PREVIOUS APPLICATIONS
    # --------------------------------------------------------

    processed_ids = load_processed_ids()

    print()
    print(
        "Ранее отправленных откликов:",
        len(processed_ids)
    )

    # --------------------------------------------------------
    # PLAYWRIGHT
    # --------------------------------------------------------

    async with async_playwright() as p:

        print()
        print("Запускаю браузер...")

        context = (
            await p.chromium.launch_persistent_context(
                user_data_dir=str(
                    SESSION_DIR
                ),
                headless=False,
                viewport={
                    "width": 1400,
                    "height": 900,
                },
            )
        )

        page = (
            context.pages[0]
            if context.pages
            else await context.new_page()
        )

        try:

            # ------------------------------------------------
            # HH
            # ------------------------------------------------

            await page.goto(
                HH_URL,
                wait_until="domcontentloaded",
                timeout=30000
            )

            await page.wait_for_timeout(
                1500
            )

            print()
            print(
                "HH:",
                page.url
            )

            # До ручного подтверждения вакансии не собираются и не анализируются.
            wait_for_hh_login(page)
            application_mode = choose_application_mode()

            # ------------------------------------------------
            # COLLECT
            # ------------------------------------------------

            all_vacancies = []
            seen_ids = set()

            for search_index, search_url in enumerate(
                SEARCH_URLS,
                start=1
            ):

                if len(all_vacancies) >= MAX_TOTAL_VACANCIES:
                    break

                print()
                print(
                    f"ПОИСК {search_index}/{len(SEARCH_URLS)}"
                )

                remaining = (
                    MAX_TOTAL_VACANCIES
                    - len(all_vacancies)
                )

                limit = min(
                    MAX_VACANCIES_PER_SEARCH,
                    remaining
                )

                vacancies = (
                    await collect_vacancies(
                        page,
                        search_url,
                        limit
                    )
                )

                for vacancy in vacancies:

                    vacancy_id = str(
                        vacancy["id"]
                    )

                    if vacancy_id in seen_ids:
                        continue

                    seen_ids.add(
                        vacancy_id
                    )

                    all_vacancies.append(
                        vacancy
                    )

                    if len(
                        all_vacancies
                    ) >= MAX_TOTAL_VACANCIES:

                        break

            # ------------------------------------------------
            # STATS
            # ------------------------------------------------

            print()
            print("=" * 70)
            print("СБОР ЗАВЕРШЁН")
            print("=" * 70)

            print(
                "Уникальных вакансий:",
                len(all_vacancies)
            )

            if not all_vacancies:

                print(
                    "Вакансии не найдены."
                )

                return

            # ------------------------------------------------
            # PROCESS
            # ------------------------------------------------

            results = []

            for index, vacancy in enumerate(
                all_vacancies,
                start=1
            ):

                print()
                print("=" * 70)
                print(
                    f"[{index}/{len(all_vacancies)}]"
                )

                try:

                    result = (
                        await process_vacancy(
                            page,
                            vacancy,
                                processed_ids,
                                application_mode
                        )
                    )

                except Exception as e:

                    print()
                    print(
                        "КРИТИЧЕСКАЯ ОШИБКА:"
                    )
                    print(e)

                    result = {
                        "status": "error",
                        "reason": str(e),
                    }

                results.append({
                    "vacancy": vacancy,
                    "result": result,
                })

                save_result(
                    vacancy,
                    result
                )

                # Если реально отправили —
                # запоминаем ID сразу.
                if result.get("status") in {
                    "applied",
                    "already_applied",
                    "rejected_by_ai",
                }:

                    processed_ids.add(
                        str(
                            vacancy["id"]
                        )
                    )

                await page.wait_for_timeout(
                    1200
                )

            # ------------------------------------------------
            # FINAL STATS
            # ------------------------------------------------

            stats = {}

            for item in results:

                status = item[
                    "result"
                ].get(
                    "status",
                    "unknown"
                )

                stats[status] = (
                    stats.get(status, 0)
                    + 1
                )

            print()
            print()
            print("=" * 70)
            print("JOBHUNTER ЗАВЕРШИЛ РАБОТУ")
            print("=" * 70)

            print()
            print(
                "Обработано:",
                len(results)
            )

            print(
                "Отправлено:",
                stats.get(
                    "applied",
                    0
                )
            )

            print(
                "Ручная проверка:",
                stats.get(
                    "manual_review",
                    0
                )
            )

            print(
                "Отклонено AI:",
                stats.get(
                    "rejected_by_ai",
                    0
                )
            )

            print(
                "Уже откликались:",
                stats.get(
                    "already_applied",
                    0
                )
            )

            print(
                "Уже обработано локально:",
                stats.get(
                    "already_processed",
                    0
                )
            )

            print(
                "Ошибок:",
                stats.get(
                    "error",
                    0
                )
            )

            print()
            print(
                "Результаты:",
                RESULTS_FILE
            )

            input(
                "\nНажми ENTER для завершения..."
            )

        finally:

            print()
            print(
                "Закрываю браузер..."
            )

            await context.close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )

