import asyncio
from services.analysis_core import (
    parse_llm_response as parse_llm_response,
    apply_safety_filter as apply_safety_filter,
)
import re
import os
import sys

from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from services.analysis_core import (
    detect_text_language,
)
from services.client import (
    analyze_vacancy,
    load_processed_ids,
    save_result,
    check_lm_studio,
)
from gui_bridge import request as gui_request
from events import PipelineEvent, emit_event
from config import (
    AREA_ASTANA,
    DEFAULT_APPLICATION_MODE,
    HH_URL,
    MAX_TOTAL_VACANCIES,
    MAX_VACANCIES_PER_SEARCH,
    MIN_SCORE_TO_APPLY,
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
# FILES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SESSION_DIR = BASE_DIR / "hh_session"
# Совместимость со старой структурой проекта, где сессия лежала в JobHunter/hh_session.
LEGACY_SESSION_DIR = BASE_DIR / "JobHunter" / "hh_session"
if not SESSION_DIR.exists() and LEGACY_SESSION_DIR.exists():
    SESSION_DIR = LEGACY_SESSION_DIR
RESULTS_FILE = os.getenv("JOBHUNTER_HISTORY_URL", "http://127.0.0.1:8012")

# ============================================================
# RESUME PDF ATTACHMENT
# ============================================================

# Резюме берётся из профиля HH. Загрузка локального PDF отключена.
ATTACH_RESUME_PDF = False

# Резюме должны лежать в той же папке, что и этот скрипт.
# Если у тебя другие имена файлов - поменяй пути тут.
RESUME_PATH_RUS = (
    BASE_DIR / "output" / "pdf" / "Resume_Yernar_Ibadulla_Russian_Final.pdf"
)
RESUME_PATH_ENG = (
    BASE_DIR
    / "output"
    / "pdf"
    / "Resume_Yernar_Ibadulla_AI_Integration_Backend_Final.pdf"
)

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
# RESUME LANGUAGE DETECTION
# ============================================================


def pick_resume_path(vacancy_data, analysis):
    """
    Выбирает PDF резюме под язык вакансии.
    Смотрит на описание вакансии + сгенерированное сопроводительное письмо,
    т.к. письмо уже определено LLM на языке вакансии.
    """

    combined_text = (
        vacancy_data.get("description", "")
        + "\n"
        + str(analysis.get("cover_letter", ""))
    )

    language = detect_text_language(combined_text)

    if language == "eng":
        return RESUME_PATH_ENG

    return RESUME_PATH_RUS


# ============================================================
# LM STUDIO
# ============================================================


async def wait_for_hh_login(page):
    """Останавливает pipeline до ручного входа в HH."""
    if os.getenv("JOBHUNTER_GUI_CONFIRMED") == "1":
        print("HH-сессия подтверждена через GUI.")
        try:
            await page.reload(wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            raise RuntimeError(
                f"Не удалось проверить сессию HH после GUI-подтверждения: {e}"
            ) from e
        return

    print()
    print("=" * 70)
    print("ТРЕБУЕТСЯ ВХОД В HH")
    print("=" * 70)
    print("1. В открывшемся браузере войдите в аккаунт HH.")
    print("2. При необходимости пройдите CAPTCHA и дождитесь загрузки профиля.")
    print("3. Вернитесь в консоль и введите точно: Подтвердить")

    while True:
        confirmation = input("\nВаш ввод: ").strip().casefold()
        if confirmation == "подтвердить":
            break
        print('Ожидается команда "Подтвердить". Браузер оставлен открытым.')

    try:
        await page.reload(wait_until="domcontentloaded", timeout=30000)
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
    if os.getenv("JOBHUNTER_GUI_BRIDGE_PORT"):
        response = await asyncio.to_thread(
            gui_request,
            {"type": "application_review", "cover_letter": cover_letter},
        )
        return response.get("action", "skip"), response.get("instruction", "")

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
# EXTRACT VACANCY
# ============================================================


async def extract_vacancy_text(page):

    title = ""

    try:
        locator = page.locator('[data-qa="vacancy-title"]').first

        if await locator.count() > 0:
            title = (await locator.inner_text()).strip()

    except Exception:
        pass

    if not title:
        try:
            title = (await page.title()).strip()

        except Exception:
            title = ""

    description = ""

    try:
        locator = page.locator('[data-qa="vacancy-description"]').first

        if await locator.count() > 0:
            description = (await locator.inner_text()).strip()

    except Exception:
        pass

    if not description:
        try:
            description = (await page.locator("body").inner_text()).strip()

        except Exception:
            description = ""

    return {
        "title": title,
        "description": description[:20000],
    }


# ============================================================
# CHECK ALREADY APPLIED
# ============================================================


async def check_already_applied(page):

    try:
        body_text = (await page.locator("body").inner_text()).lower()

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

    return any(phrase in body_text for phrase in phrases)


# ============================================================
# RESPONSE BUTTON
# ============================================================


async def find_response_button(page):

    selectors = [
        'a[data-qa="vacancy-response-link-top"]',
        'button[data-qa*="vacancy-response"]',
        'a[data-qa*="vacancy-response"]',
    ]

    for selector in selectors:
        locator = page.locator(selector)

        count = await locator.count()

        for i in range(count):
            candidate = locator.nth(i)

            try:
                if await candidate.is_visible() and await candidate.is_enabled():
                    return candidate

            except Exception:
                continue

    try:
        locator = page.get_by_role(
            "link", name=re.compile(r"откликнуться", re.IGNORECASE)
        )

        count = await locator.count()

        for i in range(count):
            candidate = locator.nth(i)

            try:
                if await candidate.is_visible() and await candidate.is_enabled():
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


async def add_cover_letter(page, cover_letter):

    if not cover_letter:
        return False

    # Existing textarea

    textareas = page.locator("textarea")

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
                re.IGNORECASE,
            ),
        )

        count = await button.count()

        for i in range(count):
            candidate = button.nth(i)

            try:
                if await candidate.is_visible():
                    await candidate.click()

                    await page.wait_for_timeout(700)

                    break

            except Exception:
                continue

    except Exception:
        pass

    await page.wait_for_timeout(500)

    # Textarea again

    textareas = page.locator("textarea")

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

    editable = page.locator('[contenteditable="true"]')

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

    file_inputs = page.locator('input[type="file"]')

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
            button = page.get_by_role("button", name=re.compile(pattern, re.IGNORECASE))

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
            link = page.get_by_role("link", name=re.compile(pattern, re.IGNORECASE))

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


async def attach_resume_pdf(page, resume_path):
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
        print("ФАЙЛ РЕЗЮМЕ НЕ НАЙДЕН:", resume_path)

        return False

    # --- Сценарий 1: прямой input[type=file] ---

    file_input = await find_file_input(page)

    if file_input is not None:
        try:
            await file_input.set_input_files(str(resume_path))

            await page.wait_for_timeout(1500)

            print("Резюме прикреплено (input):", resume_path.name)

            return True

        except Exception as e:
            print("Ошибка прикрепления через input:", e)

    # --- Сценарий 2: кнопка + file chooser ---

    attach_button = await find_attach_resume_button(page)

    if attach_button is not None:
        try:
            async with page.expect_file_chooser() as fc_info:
                await attach_button.click()

            file_chooser = await fc_info.value

            await file_chooser.set_files(str(resume_path))

            await page.wait_for_timeout(1500)

            print("Резюме прикреплено (file chooser):", resume_path.name)

            return True

        except Exception as e:
            print("Ошибка прикрепления через file chooser:", e)

    print()
    print(
        "Не найдено поле для прикрепления резюме "
        "(возможно, форма использует резюме из профиля HH)."
    )

    return False


# ============================================================
# FINAL APPLY BUTTON
# ============================================================


async def find_final_apply_button(page):

    selectors = [
        'button[data-qa*="vacancy-response"]',
        'button[data-qa*="response"]',
    ]

    for selector in selectors:
        buttons = page.locator(selector)

        count = await buttons.count()

        for i in range(count):
            candidate = buttons.nth(i)

            try:
                if not (await candidate.is_visible() and await candidate.is_enabled()):
                    continue

                text = (await candidate.inner_text()).strip().lower()

                if "откликнуться" in text or "отправить" in text:
                    return candidate

            except Exception:
                continue

    try:
        buttons = page.get_by_role(
            "button", name=re.compile(r"(откликнуться|отправить)", re.IGNORECASE)
        )

        count = await buttons.count()

        for i in range(count):
            candidate = buttons.nth(i)

            try:
                if await candidate.is_visible() and await candidate.is_enabled():
                    return candidate

            except Exception:
                continue

    except Exception:
        pass

    return None


# ============================================================
# SUCCESS
# ============================================================


async def check_success(page, timeout_ms=15000):

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
            body_text = (await page.locator("body").inner_text()).lower()

            if any(phrase in body_text for phrase in phrases):
                return True

        except Exception:
            pass

        await page.wait_for_timeout(500)

        elapsed += 500

    return False


# ============================================================
# COLLECT VACANCIES
# ============================================================


async def collect_vacancies(page, search_url, limit=50):

    print()
    print("=" * 70)
    print("ПОИСК ВАКАНСИЙ")
    print("=" * 70)

    print(search_url)

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

        await page.wait_for_timeout(2000)

    except Exception as e:
        print("Ошибка:", e)

        return []

    cards = page.locator('[data-qa="vacancy-serp__vacancy"]')

    count = await cards.count()

    print("Найдено карточек:", count)

    vacancies = []

    for i in range(min(count, limit)):
        card = cards.nth(i)

        try:
            link = card.locator('a[data-qa="serp-item__title"]').first

            if await link.count() == 0:
                continue

            title = (await link.inner_text()).strip()

            href = await link.get_attribute("href")

            if not href:
                continue

            if href.startswith("/"):
                href = "https://astana.hh.kz" + href

            href = href.split("?")[0]

            match = re.search(r"/vacancy/(\d+)", href)

            if not match:
                continue

            vacancy_id = match.group(1)

            vacancies.append(
                {
                    "id": vacancy_id,
                    "title": title,
                    "url": (f"https://astana.hh.kz/vacancy/{vacancy_id}"),
                }
            )

        except Exception as e:
            print("Ошибка карточки:", e)

    return vacancies


# ============================================================
# PROCESS ONE VACANCY
# ============================================================


async def process_vacancy(page, vacancy, processed_ids, application_mode):
    global SESSION_LLM_INSTRUCTION

    print()
    print()
    print("#" * 70)
    print(vacancy["title"])
    print("ID:", vacancy["id"])
    print("#" * 70)

    vacancy_id = str(vacancy["id"])

    # --------------------------------------------------------
    # LOCAL PROTECTION
    # --------------------------------------------------------

    if vacancy_id in processed_ids:
        print("→ Уже был отправлен отклик ранее.")

        return {"status": "already_processed"}

    # --------------------------------------------------------
    # OPEN
    # --------------------------------------------------------

    try:
        await page.goto(vacancy["url"], wait_until="domcontentloaded", timeout=30000)

        await page.wait_for_timeout(1200)

    except Exception as e:
        return {
            "status": "error",
            "reason": str(e),
        }

    # --------------------------------------------------------
    # HH CHECK
    # --------------------------------------------------------

    if await check_already_applied(page):
        print("→ HH показывает, что отклик уже был отправлен.")

        return {"status": "already_applied"}

    # --------------------------------------------------------
    # EXTRACT
    # --------------------------------------------------------

    vacancy_data = await extract_vacancy_text(page)

    if not vacancy_data["description"]:
        return {
            "status": "error",
            "reason": ("Не удалось получить описание вакансии."),
        }

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    analysis = await analyze_vacancy(vacancy_data, SESSION_LLM_INSTRUCTION)

    if "error" in analysis:
        return {
            "status": analysis["error"],
            "reason": analysis.get("reason", ""),
        }

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print()

    print("REMOTE:", "YES" if analysis.get("is_remote") else "NO")

    print("SCORE:", analysis.get("score", 0))

    print("РЕШЕНИЕ:", analysis.get("decision", "reject").upper())

    print("Уровень:", analysis.get("job_level", "unknown"))

    print()
    print("Совпавшие навыки:", ", ".join(analysis.get("matched_skills", [])))

    print("Transferable:", ", ".join(analysis.get("transferable_skills", [])))

    print("Неподтверждённые:", ", ".join(analysis.get("missing_skills", [])))

    print("Критические:", ", ".join(analysis.get("critical_missing_skills", [])))

    print("HARD BLOCKER:", analysis.get("hard_blocker", False))

    print()
    print("Причина:")
    print(analysis.get("reason", ""))

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
        cover_letter = analysis.get("cover_letter", "").strip()

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
        analysis = await analyze_vacancy(vacancy_data, SESSION_LLM_INSTRUCTION)

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

    response_button = await find_response_button(page)

    if response_button is None:
        print("Кнопка отклика не найдена.")

        return {
            "status": "unavailable",
            **analysis,
        }

    # --------------------------------------------------------
    # OPEN FORM
    # --------------------------------------------------------

    save_result(vacancy, {**analysis, "status": "submission_pending"})

    try:
        await response_button.click()

        await page.wait_for_timeout(1000)

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

    letter_added = await add_cover_letter(page, cover_letter)

    if not letter_added:
        print("Не удалось вставить письмо.")

        return {
            "status": "letter_error",
            **analysis,
        }

    # --------------------------------------------------------
    # FINAL BUTTON
    # --------------------------------------------------------

    await page.wait_for_timeout(500)

    final_button = await find_final_apply_button(page)

    if final_button is None:
        print("Финальная кнопка отправки не найдена.")

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

    success = await check_success(page)

    if success:
        print()
        print("✓ ОТКЛИК ОТПРАВЛЕН")

        return {
            "status": "applied",
            **analysis,
        }

    print()
    print("? Не удалось подтвердить отправку.")

    return {
        "status": "unknown",
        **analysis,
    }


# ============================================================
# MAIN
# ============================================================


async def main():

    emit_event(PipelineEvent("run_started", "Starting AI-Hunter core..."))

    print("=" * 70)
    print("JOBHUNTER — AI АВТООТКЛИК HH")
    print("=" * 70)

    print()
    print("MAX_TOTAL_VACANCIES:", MAX_TOTAL_VACANCIES)

    print("NORMAL APPLY SCORE:", MIN_SCORE_TO_APPLY)

    print("REMOTE APPLY SCORE:", REMOTE_MIN_SCORE_TO_APPLY)

    print("ATTACH_RESUME_PDF:", ATTACH_RESUME_PDF)

    if ATTACH_RESUME_PDF:
        print(
            "Резюме RUS:",
            RESUME_PATH_RUS,
            "-",
            "найден" if RESUME_PATH_RUS.exists() else "НЕ НАЙДЕН",
        )

        print(
            "Резюме ENG:",
            RESUME_PATH_ENG,
            "-",
            "найден" if RESUME_PATH_ENG.exists() else "НЕ НАЙДЕН",
        )

    # --------------------------------------------------------
    # LM STUDIO
    # --------------------------------------------------------

    if not check_lm_studio():
        print()
        print("Запусти LM Studio с Local Server.")

        return

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # PREVIOUS APPLICATIONS
    # --------------------------------------------------------

    processed_ids = load_processed_ids()

    print()
    print("Ранее отправленных откликов:", len(processed_ids))

    # --------------------------------------------------------
    # PLAYWRIGHT
    # --------------------------------------------------------

    async with async_playwright() as p:
        print()
        print("Запускаю браузер...")
        emit_event(
            PipelineEvent(
                "browser_starting", "Starting browser and preparing HH session"
            )
        )

        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            viewport={
                "width": 1400,
                "height": 900,
            },
        )

        page = context.pages[0] if context.pages else await context.new_page()

        try:
            # ------------------------------------------------
            # HH
            # ------------------------------------------------

            await page.goto(HH_URL, wait_until="domcontentloaded", timeout=30000)

            await page.wait_for_timeout(1500)

            print()
            print("HH:", page.url)

            # До ручного подтверждения вакансии не собираются и не анализируются.
            await wait_for_hh_login(page)
            emit_event(PipelineEvent("hh_ready", "HH session ready"))
            application_mode = choose_application_mode()
            os.environ["JOBHUNTER_APPLICATION_MODE"] = application_mode

            # ------------------------------------------------
            # COLLECT
            # ------------------------------------------------

            all_vacancies = []
            seen_ids = set()

            for search_index, search_url in enumerate(SEARCH_URLS, start=1):
                if len(all_vacancies) >= MAX_TOTAL_VACANCIES:
                    break

                print()
                print(f"ПОИСК {search_index}/{len(SEARCH_URLS)}")

                remaining = MAX_TOTAL_VACANCIES - len(all_vacancies)

                limit = min(MAX_VACANCIES_PER_SEARCH, remaining)

                vacancies = await collect_vacancies(page, search_url, limit)

                for vacancy in vacancies:
                    vacancy_id = str(vacancy["id"])

                    if vacancy_id in seen_ids:
                        continue

                    seen_ids.add(vacancy_id)

                    all_vacancies.append(vacancy)

                    if len(all_vacancies) >= MAX_TOTAL_VACANCIES:
                        break

            emit_event(
                PipelineEvent(
                    "vacancies_collected",
                    f"Collected {len(all_vacancies)} vacancies",
                    total=len(all_vacancies),
                )
            )

            # ------------------------------------------------
            # STATS
            # ------------------------------------------------

            print()
            print("=" * 70)
            print("СБОР ЗАВЕРШЁН")
            print("=" * 70)

            print("Уникальных вакансий:", len(all_vacancies))

            if not all_vacancies:
                print("Вакансии не найдены.")

                return

            # ------------------------------------------------
            # PROCESS
            # ------------------------------------------------

            results = []
            counters = {"processed": 0, "apply": 0, "review": 0, "reject": 0}

            for index, vacancy in enumerate(all_vacancies, start=1):
                title = vacancy.get("title", vacancy.get("name", ""))
                company = vacancy.get("company", vacancy.get("employer", ""))
                emit_event(
                    PipelineEvent(
                        "vacancy_started",
                        f"Analyzing vacancy {index}/{len(all_vacancies)}: {title}",
                        vacancy_id=str(vacancy.get("id", "")),
                        vacancy_index=index,
                        total=len(all_vacancies),
                        title=title,
                        company=company,
                    )
                )

                print()
                print("=" * 70)
                print(f"[{index}/{len(all_vacancies)}]")

                try:
                    result = await process_vacancy(
                        page, vacancy, processed_ids, application_mode
                    )

                except Exception as e:
                    print()
                    print("КРИТИЧЕСКАЯ ОШИБКА:")
                    print(e)

                    result = {
                        "status": "error",
                        "reason": str(e),
                    }

                results.append(
                    {
                        "vacancy": vacancy,
                        "result": result,
                    }
                )

                save_result(vacancy, result)

                decision = result.get("decision", "reject")
                counters["processed"] += 1
                if decision == "apply":
                    counters["apply"] += 1
                elif decision == "manual_review":
                    counters["review"] += 1
                else:
                    counters["reject"] += 1
                emit_event(
                    PipelineEvent(
                        "decision_made",
                        f"Decision: {decision.upper()} - {title} - score {result.get('score', 0)}",
                        vacancy_id=str(vacancy.get("id", "")),
                        vacancy_index=index,
                        total=len(all_vacancies),
                        processed=counters["processed"],
                        apply=counters["apply"],
                        review=counters["review"],
                        reject=counters["reject"],
                        score=result.get("score"),
                        decision=decision,
                        title=title,
                        company=company,
                    )
                )

                # Если реально отправили —
                # запоминаем ID сразу.
                if result.get("status") in {
                    "applied",
                    "already_applied",
                    "rejected_by_ai",
                    "submission_pending",
                    "unknown",
                    "send_error",
                }:
                    processed_ids.add(str(vacancy["id"]))

                await page.wait_for_timeout(1200)

            # ------------------------------------------------
            # FINAL STATS
            # ------------------------------------------------

            stats = {}

            for item in results:
                status = item["result"].get("status", "unknown")

                stats[status] = stats.get(status, 0) + 1

            print()
            print()
            print("=" * 70)
            print("JOBHUNTER ЗАВЕРШИЛ РАБОТУ")
            print("=" * 70)

            print()
            print("Обработано:", len(results))

            print("Отправлено:", stats.get("applied", 0))

            print("Ручная проверка:", stats.get("manual_review", 0))

            print("Отклонено AI:", stats.get("rejected_by_ai", 0))

            print("Уже откликались:", stats.get("already_applied", 0))

            print("Уже обработано локально:", stats.get("already_processed", 0))

            print("Ошибок:", stats.get("error", 0))

            emit_event(PipelineEvent("run_finished", "Run finished", **counters))

            print()
            print("Результаты:", RESULTS_FILE)

            if not os.getenv("JOBHUNTER_GUI_BRIDGE_PORT"):
                input("\nНажми ENTER для завершения...")

        finally:
            print()
            print("Закрываю браузер...")

            await context.close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
