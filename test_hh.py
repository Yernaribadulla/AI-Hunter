import json
import re
from playwright.sync_api import sync_playwright


SEARCH_URL = (
    "https://aktau.hh.kz/search/vacancy"
    "?text=Python"
    "&area=159"
)


def extract_vacancy_id(url: str) -> str | None:
    match = re.search(r"/vacancy/(\d+)", url)
    return match.group(1) if match else None


def main():
    vacancies = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Открываю HH...")
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)

        page.wait_for_timeout(5000)

        # Собираем ссылки на вакансии
        links = page.locator('a[href*="/vacancy/"]')

        count = links.count()
        print(f"Найдено ссылок: {count}")

        vacancy_links = {}

        for i in range(count):
            link = links.nth(i)

            try:
                title = link.inner_text().strip()
                href = link.get_attribute("href")

                if not href or not title:
                    continue

                if href.startswith("/"):
                    href = "https://aktau.hh.kz" + href

                vacancy_id = extract_vacancy_id(href)

                if not vacancy_id:
                    continue

                # Не добавляем одну вакансию несколько раз
                if vacancy_id not in vacancy_links:
                    vacancy_links[vacancy_id] = {
                        "id": vacancy_id,
                        "title": title,
                        "url": href,
                    }

            except Exception:
                continue

        print(f"Уникальных вакансий: {len(vacancy_links)}")

        # Открываем каждую вакансию и получаем описание
        for index, vacancy in enumerate(vacancy_links.values(), start=1):
            print(
                f"[{index}/{len(vacancy_links)}] "
                f"{vacancy['title']} "
                f"(ID: {vacancy['id']})"
            )

            try:
                vacancy_page = browser.new_page()

                vacancy_page.goto(
                    vacancy["url"],
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                vacancy_page.wait_for_timeout(2000)

                # Получаем весь текст страницы
                body_text = vacancy_page.locator("body").inner_text()

                vacancy["description"] = body_text.strip()

                vacancy_page.close()

            except Exception as e:
                print(f"  Ошибка: {e}")
                vacancy["description"] = ""

        browser.close()

    # Сохраняем JSON
    with open(
        "vacancies.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            list(vacancy_links.values()),
            file,
            ensure_ascii=False,
            indent=4,
        )

    print()
    print("=" * 60)
    print(f"Готово! Сохранено вакансий: {len(vacancy_links)}")
    print("Файл: vacancies.json")
    print("=" * 60)


if __name__ == "__main__":
    main()