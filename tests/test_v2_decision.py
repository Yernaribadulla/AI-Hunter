import unittest
from unittest.mock import patch

from apply import apply_safety_filter, parse_llm_response


def analysis(**overrides):
    value = {
        "score": 65,
        "direction_match": True,
        "hard_blocker": False,
        "job_level": "junior",
        "commercial_experience_mandatory": False,
        "required_commercial_years": None,
        "cover_letter": "Здравствуйте! Готов обсудить задачу.",
    }
    value.update(overrides)
    return value


class DecisionEngineTests(unittest.TestCase):
    def test_score_below_threshold_does_not_apply(self):
        result = apply_safety_filter(analysis(score=64))
        self.assertFalse(result["should_apply"])

    def test_score_65_applies(self):
        result = apply_safety_filter(analysis())
        self.assertTrue(result["should_apply"])

    def test_hard_blocker_does_not_apply(self):
        result = apply_safety_filter(analysis(score=90, hard_blocker=True))
        self.assertFalse(result["should_apply"])

    def test_commercial_years_are_independent_from_job_level(self):
        result = apply_safety_filter(
            analysis(
                job_level="junior",
                commercial_experience_mandatory=True,
                required_commercial_years=1,
            )
        )
        self.assertTrue(result["should_apply"])

    def test_insufficient_mandatory_commercial_years_reject(self):
        result = apply_safety_filter(
            analysis(
                commercial_experience_mandatory=True,
                required_commercial_years=3,
            )
        )
        self.assertFalse(result["should_apply"])
        self.assertIn("коммерческого опыта", result["reason"])

    def test_maybe_hard_blocker_is_invalid_and_safe(self):
        raw = '{"score": 90, "direction_match": true, "hard_blocker": "maybe"}'
        self.assertIsNone(parse_llm_response(raw))

    def test_salary_below_minimum_is_rejected(self):
        result = apply_safety_filter(
            analysis(),
            vacancy_data={"description": "Зарплата 180 000 ₸"},
        )
        self.assertFalse(result["should_apply"])


if __name__ == "__main__":
    unittest.main()
