from hh_api import HHApi


SEARCH_QUERIES = [
    "Python",
    "AI",
    "Automation",
    "Backend",
    "BI",
    "ETL",
    "Support Engineer",
    "QA",
]


def main() -> None:
    api = HHApi()

    for query in SEARCH_QUERIES:
        print(f"\n=== {query} ===")

        result = api.search_vacancies(
            text=query,
            area="159",
            per_page=10,
        )

        print(f"Найдено: {result['found']}")

        for vacancy in result["items"]:
            print(
                f"{vacancy['name']} | "
                f"{vacancy['employer']['name']} | "
                f"{vacancy['alternate_url']}"
            )


if __name__ == "__main__":
    main()