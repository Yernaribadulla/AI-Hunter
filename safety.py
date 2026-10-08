import re

from candidate import CANDIDATE
from config import (
    MIN_SCORE_TO_APPLY,
    MIN_SCORE_TO_REVIEW,
    REMOTE_MIN_SCORE_TO_APPLY,
)


def _list(value):
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _salary_reason(vacancy, analysis):
    known = analysis.get("salary_known")
    salary_max = analysis.get("salary_max")
    if known is True and salary_max is not None and salary_max < CANDIDATE["minimum_salary"]:
        return f"Зарплата ниже минимума кандидата ({CANDIDATE['minimum_salary']:,} KZT)."

    # Backward-compatible fallback for older vacancy payloads without normalized salary fields.
    if known is not True:
        text = " ".join(str(vacancy.get(key, "")) for key in ("title", "description", "salary", "compensation")).lower()
        values = [int(value.replace(" ", "")) for value in re.findall(r"(?<!\d)(\d{3}(?:[ .]\d{3})?)(?:\s*(?:₸|тг|тенге))", text)]
        if values and max(values) < CANDIDATE["minimum_salary"]:
            return f"Зарплата ниже минимума кандидата ({CANDIDATE['minimum_salary']:,} KZT)."
    return ""


def evaluate(analysis, vacancy=None, is_remote=False):
    """Apply deterministic policy; the LLM recommendation is never authoritative."""
    vacancy = vacancy or {}
    if not isinstance(analysis, dict):
        return {"score": 0, "should_apply": False, "decision": "reject", "reason": "Некорректный ответ AI.", "cover_letter": ""}

    score = analysis.get("score", 0)
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        return {"score": 0, "should_apply": False, "decision": "reject", "reason": "Некорректный score в ответе AI.", "cover_letter": ""}

    direction_match = analysis.get("direction_match", False)
    hard_blocker = analysis.get("hard_blocker", False)
    if not isinstance(direction_match, bool) or not isinstance(hard_blocker, bool):
        return {"score": 0, "should_apply": False, "decision": "reject", "reason": "Некорректный boolean в ответе AI.", "cover_letter": ""}

    reason = str(analysis.get("reason", "")).strip()
    cover_letter = str(analysis.get("cover_letter", "")).strip()
    hard_reason = str(analysis.get("hard_blocker_reason", "")).strip()
    mandatory = analysis.get("commercial_experience_mandatory", False)
    required_years = analysis.get("required_commercial_years")
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

    return {
        "score": score, "should_apply": should_apply, "decision": decision,
        "is_remote": is_remote, "job_level": str(analysis.get("job_level", "unknown")).strip().lower(),
        "direction_match": direction_match, "hard_blocker": hard_blocker,
        "hard_blocker_reason": hard_reason,
        "commercial_experience_required": analysis.get("commercial_experience_required", False),
        "commercial_experience_mandatory": mandatory,
        "required_commercial_years": required_years,
        "matched_skills": _list(analysis.get("matched_skills", [])),
        "transferable_skills": _list(analysis.get("transferable_skills", [])),
        "missing_skills": _list(analysis.get("missing_skills", [])),
        "critical_missing_skills": _list(analysis.get("critical_missing_skills", [])),
        "reason": reason, "cover_letter": cover_letter,
    }
