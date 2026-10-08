import re

from candidate import CANDIDATE
from models import Decision, VacancyAnalysis
from config import (
    MIN_SCORE_TO_APPLY,
    MIN_SCORE_TO_REVIEW,
    REMOTE_MIN_SCORE_TO_APPLY,
)


def _list(value):
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _salary_reason(vacancy: dict, analysis: VacancyAnalysis):
    if analysis.salary_known and analysis.salary_max is not None and analysis.salary_max < CANDIDATE["minimum_salary"]:
        return f"Зарплата ниже минимума кандидата ({CANDIDATE['minimum_salary']:,} KZT)."

    # Backward-compatible fallback for older vacancy payloads without normalized salary fields.
    if not analysis.salary_known:
        text = " ".join(str(vacancy.get(key, "")) for key in ("title", "description", "salary", "compensation")).lower()
        values = [int(value.replace(" ", "")) for value in re.findall(r"(?<!\d)(\d{3}(?:[ .]\d{3})?)(?:\s*(?:₸|тг|тенге))", text)]
        if values and max(values) < CANDIDATE["minimum_salary"]:
            return f"Зарплата ниже минимума кандидата ({CANDIDATE['minimum_salary']:,} KZT)."
    return ""


def evaluate(analysis: VacancyAnalysis, vacancy: dict, is_remote: bool) -> Decision:
    """Apply deterministic policy; the LLM recommendation is never authoritative."""
    vacancy = vacancy or {}
    score = analysis.score
    direction_match = analysis.direction_match
    hard_blocker = analysis.hard_blocker
    reason = analysis.reason.strip()
    cover_letter = analysis.cover_letter.strip()
    hard_reason = analysis.hard_blocker_reason.strip()
    mandatory = analysis.commercial_experience_mandatory
    required_years = analysis.required_commercial_years
    candidate_years = CANDIDATE.get("commercial_experience_years", 0)
    minimum = REMOTE_MIN_SCORE_TO_APPLY if is_remote else MIN_SCORE_TO_APPLY

    if hard_blocker:
        decision, should_apply = "reject", False
        reason = reason or hard_reason or "Есть настоящий hard blocker."
    elif not direction_match:
        decision, should_apply = "reject", False
        reason = reason or "Основное направление вакансии не соответствует профилю кандидата."
    elif mandatory and required_years is not None and required_years > candidate_years:
        decision, should_apply = "reject", False
        reason = reason or f"Требуется {required_years:g} лет коммерческого опыта, подтверждено {candidate_years:g}."
    elif _salary_reason(vacancy, analysis):
        decision, should_apply = "reject", False
        reason = reason or _salary_reason(vacancy, analysis)
    elif score >= minimum:
        decision, should_apply = "apply", True
    elif score >= MIN_SCORE_TO_REVIEW:
        decision, should_apply = "manual_review", False
    else:
        decision, should_apply = "reject", False

    if should_apply and not cover_letter:
        decision, should_apply = "reject", False
        reason = (reason + " Отклик отменён: AI не сгенерировал сопроводительное письмо.").strip()

    return Decision(
        action=decision,
        score=score,
        reason=reason,
        should_apply=should_apply,
        cover_letter=cover_letter,
        threshold=minimum,
        is_remote=is_remote,
        hard_blocker=hard_blocker,
        direction_match=direction_match,
        required_commercial_years=required_years,
    )
