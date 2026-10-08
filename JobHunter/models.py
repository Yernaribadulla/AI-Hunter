from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class VacancyAnalysis(BaseModel):
    """Validated, non-authoritative output from the local LLM."""

    model_config = ConfigDict(extra="ignore")

    score: int = Field(ge=0, le=100)
    should_apply: StrictBool = False
    direction_match: StrictBool
    hard_blocker: StrictBool
    hard_blocker_reason: str = ""
    job_level: str = "unknown"
    commercial_experience_required: StrictBool = False
    commercial_experience_mandatory: StrictBool = False
    required_commercial_years: Optional[float] = Field(default=None, ge=0)
    salary_known: StrictBool = False
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    matched_skills: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    critical_missing_skills: list[str] = Field(default_factory=list)
    language: str = "unknown"
    is_remote: StrictBool = False
    reason: str = ""
    cover_letter: str = ""


class Decision(BaseModel):
    action: Literal["apply", "manual_review", "reject"]
    score: int = Field(ge=0, le=100)
    reason: str = ""
    should_apply: StrictBool
    cover_letter: str = ""
    threshold: int
    is_remote: StrictBool
    hard_blocker: StrictBool
    direction_match: StrictBool
    required_commercial_years: Optional[float] = None
