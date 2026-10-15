"""Playwright page operations, isolated from orchestration and model analysis."""

import re


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
