import requests

from config import HH_API_URL, HH_HOST, HH_USER_AGENT


class HHApi:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "HH-User-Agent": HH_USER_AGENT,
            "User-Agent": HH_USER_AGENT,
        })

    def get_areas(self) -> list[dict]:
        response = self.session.get(
            f"{HH_API_URL}/areas",
            params={"host": HH_HOST},
            timeout=20,
        )

        response.raise_for_status()

        return response.json()

    def search_vacancies(
        self,
        text: str,
        area: str,
        page: int = 0,
        per_page: int = 20,
    ) -> dict:
        response = self.session.get(
            f"{HH_API_URL}/vacancies",
            params={
                "text": text,
                "area": area,
                "page": page,
                "per_page": per_page,
            },
            timeout=20,
        )

        print("STATUS:", response.status_code)
        print("URL:", response.url)
        print("RESPONSE:", response.text[:1000])

        response.raise_for_status()

        return response.json()

    def get_vacancy(self, vacancy_id: str) -> dict:
        response = self.session.get(
            f"{HH_API_URL}/vacancies/{vacancy_id}",
            params={
                "host": HH_HOST,
            },
            timeout=20,
        )

        response.raise_for_status()

        return response.json()