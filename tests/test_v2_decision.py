import unittest
import os
from unittest import mock
from unittest.mock import patch

from apply import apply_safety_filter, choose_application_mode, parse_llm_response
from models import VacancyAnalysis


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
    return VacancyAnalysis.model_validate(value)


class DecisionEngineTests(unittest.TestCase):
    def test_gui_mode_selection_does_not_read_stdin(self):
        with mock.patch.dict(os.environ, {"JOBHUNTER_GUI_MODE": "manual"}):
            with mock.patch("builtins.input", side_effect=AssertionError("GUI must not read stdin")):
                self.assertEqual(choose_application_mode(), "manual")

    def test_direction_mismatch_rejects(self):
        self.assertEqual(apply_safety_filter(analysis(direction_match=False)).action, "reject")

    def test_score_below_review_rejects(self):
        self.assertEqual(apply_safety_filter(analysis(score=54)).action, "reject")

    def test_score_review_range(self):
        self.assertEqual(apply_safety_filter(analysis(score=55)).action, "manual_review")

    def test_remote_threshold_boundaries(self):
        self.assertEqual(apply_safety_filter(analysis(score=59), is_remote=True).action, "manual_review")
        self.assertEqual(apply_safety_filter(analysis(score=60), is_remote=True).action, "apply")

    def test_missing_cover_letter_rejects(self):
        self.assertEqual(apply_safety_filter(analysis(cover_letter="")).action, "reject")

    def test_salary_range_uses_maximum(self):
        low_start = analysis(salary_known=True, salary_min=200_000, salary_max=500_000)
        low_range = analysis(salary_known=True, salary_min=200_000, salary_max=240_000)
        self.assertEqual(apply_safety_filter(low_start).action, "apply")
        self.assertEqual(apply_safety_filter(low_range).action, "reject")

    def test_commercial_exact_match_passes(self):
        result = apply_safety_filter(analysis(commercial_experience_mandatory=True, required_commercial_years=2))
        self.assertEqual(result.action, "apply")

    def test_score_below_threshold_does_not_apply(self):
        result = apply_safety_filter(analysis(score=64))
        self.assertFalse(result.should_apply)

    def test_score_65_applies(self):
        result = apply_safety_filter(analysis())
        self.assertTrue(result.should_apply)

    def test_hard_blocker_does_not_apply(self):
        result = apply_safety_filter(analysis(score=90, hard_blocker=True))
        self.assertFalse(result.should_apply)

    def test_commercial_years_are_independent_from_job_level(self):
        result = apply_safety_filter(
            analysis(
                job_level="junior",
                commercial_experience_mandatory=True,
                required_commercial_years=1,
            )
        )
        self.assertTrue(result.should_apply)

    def test_insufficient_mandatory_commercial_years_reject(self):
        result = apply_safety_filter(
            analysis(
                commercial_experience_mandatory=True,
                required_commercial_years=3,
            )
        )
        self.assertFalse(result.should_apply)
        self.assertIn("коммерческого опыта", result.reason)

    def test_maybe_hard_blocker_is_invalid_and_safe(self):
        raw = '{"score": 90, "direction_match": true, "hard_blocker": "maybe"}'
        self.assertIsNone(parse_llm_response(raw))

    def test_salary_below_minimum_is_rejected(self):
        result = apply_safety_filter(
            analysis(),
            vacancy_data={"description": "Зарплата 180 000 ₸"},
        )
        self.assertFalse(result.should_apply)

    def test_unknown_salary_is_not_rejected_by_salary_rule(self):
        result = apply_safety_filter(analysis(), vacancy_data={"description": "Компенсация обсуждается"})
        self.assertTrue(result.should_apply)

    def test_preferred_commercial_experience_is_not_hard_reject(self):
        result = apply_safety_filter(
            analysis(commercial_experience_mandatory=False, required_commercial_years=5)
        )
        self.assertTrue(result.should_apply)


if __name__ == "__main__":
    unittest.main()
