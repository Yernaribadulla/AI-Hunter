import json
import re


# =========================
# ТВОЙ ПРОФИЛЬ
# =========================

PROFILE = {
    "experience_level": "junior+",
    "salary_min": 300_000,

    "skills": [
        "python",
        "javascript",
        "react",
        "node.js",
        "node",
        "sql",
        "rest api",
        "api",
        "html",
        "css",
        "git",
        "github",
        "linux",
        "java",
        "go",
        "llm",
        "openai",
        "prompt engineering",
        "function calling",
        "n8n",
        "make",
        "nextbot",
        "amocrm",
        "google calendar api",
        "google sheets api",
        "kaspi api",
        "webhooks",
        "power bi",
        "excel",
    ],

    "preferred_directions": [
        "fullstack",
        "full stack",
        "software engineer",
        "ai",
        "искусственный интеллект",
        "ии",
        "automation",
        "автоматизация",
        "python backend",
        "backend",
        "python",
        "data analyst",
        "аналитик данных",
        "qa",
        "тестировщик",
        "it support",
        "technical support",
        "поддержка",
    ],

    "strong_directions": [
        "fullstack",
        "full stack",
        "ai",
        "automation",
        "автоматизация",
        "software engineer",
        "ai engineer",
        "ai-инженер",
        "ии разработчик",
        "ai developer",
    ],

    "weak_directions": [
        "risk manager",
        "risk",
        "hr",
        "sales",
        "бухгалтер",
        "юрист",
        "водитель",
        "менеджер по продажам",
        "экономист",
    ],
}


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def normalize(text):
    if not text:
        return ""

    text = text.lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


def get_text(vacancy):
    return normalize(
        vacancy.get("title", "")
        + " "
        + vacancy.get("description", "")
    )


def extract_salary(text):
    """
    Ищет зарплату в тенге.
    Возвращает минимальную найденную сумму.
    """

    amounts = []

    patterns = [
        r"(\d[\d\s]{2,})\s*(?:₸|тг|тенге)",
        r"от\s*(\d[\d\s]{2,})\s*(?:₸|тг|тенге)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)

        for value in matches:
            value = value.replace(" ", "")

            try:
                amounts.append(int(value))
            except ValueError:
                pass

    if not amounts:
        return None

    return min(amounts)


def detect_experience(text):
    """
    Возвращает приблизительное требование по опыту.
    """

    if re.search(r"более 6\s*лет|6\+ лет|от 6 лет", text):
        return 6

    if re.search(r"3[-–]6 лет|от 3 лет|3\+ лет", text):
        return 3

    if re.search(r"1[-–]3 года|1[-–]2 года|от 1 года|1\+ год", text):
        return 1

    if re.search(r"без опыта|нет опыта|no experience", text):
        return 0

    return None


def is_senior(text):
    senior_words = [
        "senior",
        "lead",
        "tech lead",
        "team lead",
        "principal",
        "архитектор",
        "руководитель",
    ]

    return any(word in text for word in senior_words)


def is_remote(text):
    remote_words = [
        "удаленно",
        "удаленная работа",
        "можно удаленно",
        "remote",
        "remotely",
        "из любой точки",
    ]

    return any(word in text for word in remote_words)


def is_astana(text):
    return "астана" in text or "нур-султан" in text


# =========================
# ОЦЕНКА ВАКАНСИИ
# =========================

def evaluate(vacancy):

    title = normalize(vacancy.get("title", ""))
    description = normalize(vacancy.get("description", ""))
    text = title + " " + description

    score = 0

    reasons = []
    warnings = []

    # ---------------------------------
    # 1. НАПРАВЛЕНИЕ
    # ---------------------------------

    strong_found = []

    for direction in PROFILE["strong_directions"]:
        if direction in title:
            strong_found.append(direction)

    if strong_found:
        score += 30
        reasons.append(
            "Сильное совпадение по направлению: "
            + ", ".join(strong_found[:3])
        )

    else:
        preferred_found = []

        for direction in PROFILE["preferred_directions"]:
            if direction in title or direction in text:
                preferred_found.append(direction)

        if preferred_found:
            score += 20
            reasons.append(
                "Подходящее направление: "
                + ", ".join(preferred_found[:3])
            )

    # ---------------------------------
    # 2. НАВЫКИ
    # ---------------------------------

    matched_skills = []

    for skill in PROFILE["skills"]:
        if skill in text:
            matched_skills.append(skill)

    skill_points = min(len(matched_skills) * 2, 20)

    score += skill_points

    if matched_skills:
        reasons.append(
            f"Совпадает навыков: {len(matched_skills)} "
            f"({', '.join(matched_skills[:6])})"
        )

    # ---------------------------------
    # 3. ОПЫТ
    # ---------------------------------

    required_experience = detect_experience(text)

    if required_experience is not None:

        if required_experience == 0:
            score += 5
            reasons.append("Опыт не требуется")

        elif required_experience == 1:
            score += 5
            reasons.append(
                "Требуемый опыт (1–3 года) считаем подходящим"
            )

        elif required_experience >= 3:
            score -= 20
            warnings.append(
                f"Требуется около {required_experience}+ лет опыта"
            )

    # Senior / Lead отдельно
    if is_senior(title):

        score -= 25

        warnings.append(
            "Вакансия уровня Senior/Lead"
        )

    # ---------------------------------
    # 4. ЗАРПЛАТА
    # ---------------------------------

    salary = extract_salary(text)

    if salary:

        if salary >= 500_000:
            score += 10
            reasons.append(
                f"Зарплата выше минимальной: {salary:,} ₸".replace(",", " ")
            )

        elif salary >= PROFILE["salary_min"]:
            score += 5
            reasons.append(
                f"Зарплата соответствует ожиданиям: {salary:,} ₸"
                .replace(",", " ")
            )

        else:
            score -= 20

            warnings.append(
                f"Зарплата ниже желаемых {PROFILE['salary_min']:,} ₸"
                .replace(",", " ")
            )

    # ---------------------------------
    # 5. ЛОКАЦИЯ
    # ---------------------------------

    if is_astana(text):

        score += 5
        reasons.append("Астана")

    elif is_remote(text):

        score += 5
        reasons.append("Удалённая работа")

    else:

        # Другой город без удалёнки
        score -= 30

        warnings.append(
            "Офлайн работа не в Астане"
        )

    # ---------------------------------
    # 6. АНГЛИЙСКИЙ
    # ---------------------------------

    english_c1 = [
        "английский c1",
        "english c1",
        "английский — c1",
        "английский - c1",
        "upper-advanced",
        "advanced english",
    ]

    english_b2 = [
        "английский b2",
        "english b2",
        "upper-intermediate",
        "upper intermediate",
    ]

    if any(x in text for x in english_c1):

        score -= 5

        warnings.append(
            "Требуется высокий уровень английского"
        )

    elif any(x in text for x in english_b2):

        score += 2

        reasons.append(
            "Английский примерно соответствует профилю"
        )

    # ---------------------------------
    # 7. ОБЯЗАТЕЛЬНОЕ ОБРАЗОВАНИЕ
    # ---------------------------------

    education_required = [
        "обязательно высшее образование",
        "требуется высшее образование",
        "высшее техническое образование обязательно",
    ]

    if any(x in text for x in education_required):

        score -= 8

        warnings.append(
            "Есть требование обязательного высшего образования"
        )

    # ---------------------------------
    # 8. НЕПОДХОДЯЩИЕ НАПРАВЛЕНИЯ
    # ---------------------------------

    bad_found = []

    for direction in PROFILE["weak_directions"]:
        if direction in title:
            bad_found.append(direction)

    if bad_found:

        score -= 40

        warnings.append(
            "Неподходящее направление: "
            + ", ".join(bad_found[:3])
        )

    # ---------------------------------
    # 9. ОГРАНИЧЕНИЕ
    # ---------------------------------

    score = max(0, min(score, 100))

    # ---------------------------------
    # 10. РЕШЕНИЕ
    # ---------------------------------

    if score >= 70:
        decision = "apply"

    elif score >= 50:
        decision = "review"

    else:
        decision = "skip"

    return {
        "id": vacancy.get("id"),
        "title": vacancy.get("title"),
        "url": vacancy.get("url"),
        "score": score,
        "decision": decision,
        "reasons": reasons,
        "warnings": warnings,
    }


# =========================
# MAIN
# =========================

def main():

    with open(
        "vacancies.json",
        "r",
        encoding="utf-8"
    ) as file:

        vacancies = json.load(file)

    results = []

    for vacancy in vacancies:

        result = evaluate(vacancy)

        results.append(result)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # Сохраняем полный результат
    with open(
        "filtered.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2
        )

    # =========================
    # ВЫВОД
    # =========================

    print()
    print("=" * 80)
    print("ТОП-10 ВАКАНСИЙ")
    print("=" * 80)

    for i, vacancy in enumerate(results[:10], 1):

        print(
            f"\n{i}. [{vacancy['score']}/100] "
            f"{vacancy['title']}"
        )

        for reason in vacancy["reasons"][:3]:

            print(
                f"   + {reason}"
            )

        for warning in vacancy["warnings"][:2]:

            print(
                f"   - {warning}"
            )

        print(
            f"   → {vacancy['decision'].upper()}"
        )

    print()
    print("=" * 80)
    print("Результат сохранён в filtered.json")
    print("=" * 80)


if __name__ == "__main__":
    main()