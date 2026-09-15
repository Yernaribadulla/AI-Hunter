import asyncio
import json
import re
import requests

from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright


# ============================================================
# CONFIG
# ============================================================

SEARCH_URLS = [

    # Fullstack / Web
    "https://astana.hh.kz/search/vacancy?text=Full-stack+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Fullstack+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Full+Stack+разработчик&area=160",
    "https://astana.hh.kz/search/vacancy?text=Фуллстак+разработчик&area=160",
    "https://astana.hh.kz/search/vacancy?text=Веб-разработчик&area=160",
    "https://astana.hh.kz/search/vacancy?text=Web+Developer&area=160",

    # JavaScript / TypeScript Fullstack вариации
    "https://astana.hh.kz/search/vacancy?text=React+Node.js&area=160",
    "https://astana.hh.kz/search/vacancy?text=JavaScript+Fullstack&area=160",
    "https://astana.hh.kz/search/vacancy?text=TypeScript+Developer&area=160",

    # No-Code / Low-Code / Make / n8n (часто ищут автоматизаторов без чистого кода)
    "https://astana.hh.kz/search/vacancy?text=n8n&area=160",
    "https://astana.hh.kz/search/vacancy?text=Make.com&area=160",
    "https://astana.hh.kz/search/vacancy?text=No-Code&area=160",
    "https://astana.hh.kz/search/vacancy?text=Zapier&area=160",

    # CRM & Business Systems Integrations
    "https://astana.hh.kz/search/vacancy?text=CRM+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=amoCRM&area=160",
    "https://astana.hh.kz/search/vacancy?text=Bitrix24&area=160",
    "https://astana.hh.kz/search/vacancy?text=Integration+Specialist&area=160",

    # Web & Frontend расширения
    "https://astana.hh.kz/search/vacancy?text=Frontend&area=160",
    "https://astana.hh.kz/search/vacancy?text=Web+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=TypeScript&area=160",

    # Общие Python/Junior вариации
    "https://astana.hh.kz/search/vacancy?text=Junior+Developer&area=160",
    "https://astana.hh.kz/search/vacancy?text=Стажер+Python&area=160",
    "https://astana.hh.kz/search/vacancy?text=Python+разработчик&area=160",
]


# Максимум вакансий за запуск
MAX_TOTAL_VACANCIES = 2500

# Максимум вакансий из одного поискового запроса
MAX_VACANCIES_PER_SEARCH = 50

# Обычная вакансия
MIN_SCORE_TO_APPLY = 65

# Remote-вакансия
REMOTE_MIN_SCORE_TO_APPLY = 60

# Ручная проверка
MIN_SCORE_TO_REVIEW = 55


# ============================================================
# LM STUDIO
# ============================================================

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_MODELS_URL = "http://localhost:1234/v1/models"

LM_MODEL = "qwen/qwen3-vl-8b"


# ============================================================
# FILES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SESSION_DIR = BASE_DIR / "hh_session"
RESULTS_FILE = BASE_DIR / "results.jsonl"

HH_URL = "https://astana.hh.kz/"


# ============================================================
# RESUME PDF ATTACHMENT
# ============================================================

# Включить/выключить прикрепление PDF резюме к отклику
ATTACH_RESUME_PDF = True

# Резюме должны лежать в той же папке, что и этот скрипт.
# Если у тебя другие имена файлов - поменяй пути тут.
RESUME_PATH_RUS = BASE_DIR / "resume_RUS.pdf"
RESUME_PATH_ENG = BASE_DIR / "resume_ENG.pdf"


# ============================================================
# CANDIDATE
# ============================================================

CANDIDATE_PROFILE = """
NAME:
Ернар

LOCATION:
Astana, Kazakhstan

LEVEL:
Junior+.

TARGET ROLES:
- AI Integration Developer
- AI Automation Developer
- AI Developer
- Python Developer
- Junior Python Developer
- Backend Developer
- Automation Developer
- Backend / Automation Developer
- LLM Integration Developer
- Full-Stack Developer

IMPORTANT:
"AI Engineer" is NOT a preferred target role by itself.

However, an "AI Engineer" vacancy may still be suitable if
the actual work is mainly:
- LLM integrations
- AI assistants
- Function Calling
- API integrations
- workflow automation
- business automation

COMMERCIAL EXPERIENCE:

S-Dental — AI Automation Developer

Confirmed commercial experience:
- AI assistant development
- AI-powered customer communication
- Knowledge Base Design
- Function Calling
- Google Calendar integration
- amoCRM integration
- Kaspi API integration
- business workflow automation
- NextBot
- Make
- n8n


PROJECT EXPERIENCE:

Coffee Shop Analytics Platform:
- Python
- JavaScript
- React
- HTML5
- CSS3
- REST APIs
- Google Sheets API / GViz
- QR tracking
- conversion analytics
- dashboards
- employee-level tracking
- external platform click tracking
- GitHub Pages


CONFIRMED TECHNICAL SKILLS:

PROGRAMMING:
- Python
- JavaScript
- Node.js
- SQL
- Java
- Go

WEB:
- React
- HTML5
- CSS3
- REST APIs

AI / LLM:
- LLMs
- OpenAI API
- Prompt Engineering
- Function Calling
- Knowledge Base Design
- AI Assistants
- LLM Integrations

AUTOMATION:
- Workflow Automation
- AI Automation
- n8n
- Make
- NextBot

INTEGRATIONS:
- REST API integrations
- CRM integrations
- amoCRM API
- Google Calendar API
- Google Sheets API
- Kaspi API
- Robokassa API
- Webhooks

DATA / ANALYTICS:
- SQL
- Power BI
- Excel
- Google Sheets
- Data Visualization
- QR Tracking
- Conversion Analytics

TOOLS:
- Git
- GitHub
- Linux
- GitHub Pages

EDUCATION:
Turan-Astana University
Faculty of Information Technologies and Cybersecurity
Government Educational Grant

LANGUAGES:
- Russian — Fluent
- Kazakh — Fluent
- English — B2/B2+


NOT CONFIRMED:

The following technologies are NOT confirmed:

- FastAPI
- Django
- Flask
- Docker
- Kubernetes
- PostgreSQL
- MySQL
- Redis
- MongoDB
- AWS
- Azure
- GCP
- Terraform
- Kafka
- LangChain
- LangGraph
- RAG
- vector databases
- PyTorch
- TensorFlow
- CI/CD
- pytest
- unittest
- Postman
- Requests
- HTTPX

NEVER present these as existing experience.

They may be considered transferable skills when appropriate.


ABSOLUTE RULES:

Do NOT invent:
- years of experience
- companies
- positions
- technologies
- certifications
- responsibilities
- commercial experience

Own projects are practical/project experience,
NOT commercial experience.
"""


# ============================================================
# GLOBAL
# ============================================================

ACTIVE_MODEL = None


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
                    "applied",
                    "already_applied",
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


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = r"""
Ты — AI-рекрутер.

Твоя задача — определить, стоит ли кандидату откликаться
на конкретную вакансию.

ГЛАВНЫЙ ПРИНЦИП:

НЕ ОТКАЗЫВАЙ КАНДИДАТУ ПРОСТО ПОТОМУ,
ЧТО У НЕГО НЕТ КОНКРЕТНОГО ИНСТРУМЕНТА.

Сначала оцени ОСНОВНУЮ РАБОТУ.

Например:

Python + REST API + backend
+
FastAPI + Docker + PostgreSQL

может быть хорошим Junior match.

Python + LLM + Function Calling
+
LangChain

может быть хорошим AI Integration match.

Отсутствие конкретного инструмента НЕ является hard blocker,
если фундаментальные навыки кандидата позволяют быстро освоить
этот инструмент.

============================================================
HARD BLOCKER — ОЧЕНЬ ВАЖНО
============================================================

hard_blocker = true можно ставить ТОЛЬКО если одновременно:

1. отсутствующий навык является центральным для работы;
2. без него кандидат фактически не сможет выполнять основную работу;
3. существующие навыки кандидата НЕ дают разумной transferable основы.

Примеры hard blocker:

Junior iOS Developer
+
Swift/iOS development является основной работой.

Embedded C++ Engineer
+
C++ embedded development является основной работой.

ML Research Engineer
+
PyTorch/TensorFlow + mathematical ML являются основной работой.

CAD Automation Engineer
+
CAD/CadQuery является центральной специализацией.

НЕ ЯВЛЯЮТСЯ hard blocker автоматически:

- pytest
- unittest
- Postman
- Requests
- HTTPX
- Docker
- PostgreSQL
- Redis
- AWS
- GCP
- Azure
- CI/CD
- LangChain
- LangGraph
- RAG

Если вакансия Python/backend/AI automation,
эти технологии обычно являются transferable/learnable,
а не hard blockers.

============================================================
КРИТИЧЕСКИЕ НАВЫКИ
============================================================

critical_missing_skills НЕ означает автоматически reject.

Можно указать missing/critical_missing_skills,
если они важны.

НО:

Если hard_blocker = false,
то critical_missing_skills НЕ должны автоматически
делать should_apply = false.

Особенно для Junior / Junior+.

Пример:

Python Test Automation Engineer

Требования:
Python
pytest
unittest
Docker
CI/CD
Postman

Кандидат:
Python
REST API
Git
Linux

pytest + unittest + Docker + CI/CD могут быть пробелами,
но если работа предполагает Python automation/testing,
это НЕ автоматически hard blocker.

============================================================
SENIORITY
============================================================

Junior / Intern / Trainee:
Будь гибким.

Junior+:
Будь гибким, если основной стек совпадает.

Middle:
Будь умеренно строгим.

Senior / Lead / Principal:
Будь строгим.

Если требуется обязательный многолетний
commercial production experience, которого нет,
это серьёзный негативный фактор.

============================================================
REMOTE
============================================================

Remote — приоритет.

Если вакансия remote и основная работа соответствует:

- Python
- backend
- AI
- LLM
- automation
- API
- integrations
- full-stack

будь более гибким к вторичным технологиям.

Remote НЕ отменяет настоящий hard blocker.

============================================================
AI ENGINEER
============================================================

AI Engineer НЕ является отдельной целевой ролью.

Но НЕ отклоняй вакансию только из-за названия.

Если AI Engineer фактически делает:

- LLM integrations
- AI assistants
- Function Calling
- API integrations
- automation
- business workflows

оценивай как AI Integration / AI Automation.

Если это:

- ML Research
- Deep Learning
- Computer Vision Research
- PyTorch/TensorFlow engineering
- mathematical ML

то это плохой match.

============================================================
ROLE FIT
============================================================

Сильные направления кандидата:

- AI Integration
- AI Automation
- AI Developer
- Python
- Backend
- Automation
- API / Integrations
- LLM Integration
- Full-Stack

Нерелевантные направления:

- Sales
- HR
- Accounting
- pure marketing
- legal
- construction
- medicine
- unrelated engineering

============================================================
SCORING
============================================================

Оценивай:

role_fit: 0-25
core_skill_fit: 0-30
task_fit: 0-20
experience_fit: 0-15
additional_fit: 0-10

Сумма = 100.

90-100 = exceptional
80-89 = strong
75-79 = good
70-74 = potentially good
60-69 = borderline
40-59 = weak
0-39 = very poor

============================================================
DECISION
============================================================

Обычная вакансия:

score >= 75
+
direction_match = true
+
hard_blocker = false
+
нет обязательного Senior/Middle production experience

=> should_apply = true

Remote:

score >= 60
+
direction_match = true
+
hard_blocker = false
+
нет обязательного Senior/Middle production experience

=> should_apply = true

ВАЖНО:

Не делай:

score = 78
hard_blocker = false
critical_missing_skills = ["Docker", "pytest", "CI/CD"]
should_apply = false

если причина отказа только в этих missing skills.

В таком случае should_apply должен быть true
для подходящей Junior/Junior+ вакансии.

============================================================
TRANSFERABLE SKILLS
============================================================

Python -> FastAPI / Django / Flask

SQL -> PostgreSQL / MySQL

REST API -> API frameworks

LLM -> LangChain / LangGraph

LLM + Knowledge Base Design -> RAG

Git/GitHub/Linux -> basic DevOps concepts

AI automation -> workflow automation platforms

Python + API -> Requests / HTTPX

Python -> pytest / unittest fundamentals

Но transferable НЕ является confirmed experience.

============================================================
COMMERCIAL EXPERIENCE
============================================================

S-Dental является подтверждённым commercial experience.

Подтверждённые навыки:

- AI assistants
- AI-powered customer communication
- Knowledge Base Design
- Function Calling
- Google Calendar
- amoCRM
- Kaspi API
- workflow automation
- NextBot
- Make
- n8n

Собственные проекты — practical/project experience,
но НЕ commercial experience.

============================================================
COVER LETTER LANGUAGE
============================================================

ОБЯЗАТЕЛЬНО определяй язык письма по DESCRIPTION вакансии.

Если описание преимущественно Russian:
письмо на русском.

Если преимущественно Kazakh:
письмо на казахском.

Если преимущественно English:
письмо на английском.

Название должности НЕ определяет язык.

Слово "Remote" НЕ определяет язык.

Названия технологий НЕ определяют язык.

Пример:

Title:
Python Backend Trainee

Description:
русский текст

=> письмо НА РУССКОМ.

============================================================
COVER LETTER
============================================================

Если should_apply = true:

Напиши 400-700 символов.

Письмо:

- естественное;
- короткое;
- профессиональное;
- конкретное;
- на языке вакансии.

Используй только подтверждённые навыки.

Не придумывай Docker/FastAPI/pytest и т.д.

Не называй собственные проекты коммерческими.

Не пиши:
"I am the perfect candidate."

============================================================
OUTPUT
============================================================

Верни ТОЛЬКО JSON.

ВАЖНО:

Если hard_blocker = false,
не используй critical_missing_skills
как автоматическую причину reject.

Формат:

{
    "score": 0,
    "should_apply": false,

    "job_level": "unknown",

    "direction_match": false,

    "hard_blocker": false,
    "hard_blocker_reason": "",

    "commercial_experience_required": false,
    "commercial_experience_mandatory": false,

    "matched_skills": [],
    "transferable_skills": [],
    "missing_skills": [],
    "critical_missing_skills": [],

    "reason": "",

    "cover_letter": ""
}
"""


# ============================================================
# VACANCY PROMPT
# ============================================================

def build_vacancy_prompt(
    vacancy_data,
    is_remote
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
apply threshold = 75.

Remote vacancy:
apply threshold = 60.

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
    "matched_skills": [],
    "transferable_skills": [],
    "missing_skills": [],
    "critical_missing_skills": [],
    "reason": "",
    "cover_letter": ""
}
""" % (
        CANDIDATE_PROFILE,
        vacancy_data.get("title", ""),
        vacancy_data.get("description", "")[:20000],
        remote_status,
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

        timeout=180,
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

def parse_llm_response(text):

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

    if not isinstance(
        result,
        dict
    ):
        return None

    return result


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


# ============================================================
# SAFETY FILTER
# ============================================================

def apply_safety_filter(
    analysis,
    is_remote=False
):

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

    hard_blocker = to_bool(
        analysis.get(
            "hard_blocker",
            False
        )
    )

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

    # --------------------------------------------------------
    # THRESHOLD
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

    elif (
        commercial_mandatory
        and (
            "senior" in job_level
            or "lead" in job_level
            or "principal" in job_level
            or "middle/senior" in job_level
        )
    ):

        decision = "reject"
        should_apply = False

        if not reason:

            reason = (
                "Вакансия требует обязательный "
                "коммерческий production experience "
                "для уровня выше Junior."
            )

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
    vacancy_data
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
        is_remote
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

    return apply_safety_filter(
        analysis,
        is_remote=is_remote
    )


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

                await candidate.fill(
                    cover_letter
                )

                return True

        except Exception:
            continue

    # Add cover letter button

    try:

        button = page.get_by_role(
            "button",
            name=re.compile(
                r"добавить сопроводительное",
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

                await candidate.fill(
                    cover_letter
                )

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

                await candidate.fill(
                    cover_letter
                )

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
    processed_ids
):

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
        vacancy_data
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

    cover_letter = (
        analysis.get(
            "cover_letter",
            ""
        )
        .strip()
    )

    if not cover_letter:

        print(
            "→ ОТКАЗ: нет сопроводительного."
        )

        return {
            "status": "no_cover_letter",
            **analysis,
        }

    print()
    print("СОПРОВОДИТЕЛЬНОЕ:")
    print("-" * 60)
    print(cover_letter)
    print("-" * 60)

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

    # --------------------------------------------------------
    # RESUME PDF
    # --------------------------------------------------------

    if ATTACH_RESUME_PDF:

        resume_path = pick_resume_path(
            vacancy_data,
            analysis
        )

        print()
        print(
            "Пробую прикрепить резюме:",
            resume_path.name
        )

        await attach_resume_pdf(
            page,
            resume_path
        )

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
                            processed_ids
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