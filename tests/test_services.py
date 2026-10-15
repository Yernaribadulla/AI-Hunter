import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from services.analysis import app
from services import analysis_core as core
from services.history import Store, create_app
from services import client
from test_v2_decision import analysis


class AnalysisTests(unittest.TestCase):
    def test_llm_cannot_override_deterministic_rejection(self):
        raw = analysis(score=99, should_apply=True, hard_blocker=True).model_dump_json()
        with patch.object(core, "ask_llm", return_value=raw):
            result = asyncio.run(
                core.analyze_vacancy({"description": "Работа разработчиком"})
            )
        self.assertFalse(result["should_apply"])
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["action"], "reject")

    def test_llm_false_does_not_override_accepted_decision(self):
        raw = analysis(should_apply=False).model_dump_json()
        with patch.object(core, "ask_llm", return_value=raw):
            result = asyncio.run(
                core.analyze_vacancy({"description": "Работа разработчиком"})
            )
        self.assertTrue(result["should_apply"])

    def test_language_rejection_is_consistent(self):
        with patch.object(
            core,
            "ask_llm",
            return_value=analysis(
                cover_letter="Hello, I would like to apply for this job."
            ).model_dump_json(),
        ):
            result = asyncio.run(
                core.analyze_vacancy({"description": "Работа разработчиком"})
            )
        self.assertEqual(
            (result["decision"], result["action"], result["should_apply"]),
            ("reject", "reject", False),
        )

    def test_dot_salary_does_not_crash(self):
        self.assertEqual(
            core.apply_safety_filter(
                analysis(), vacancy_data={"description": "180.000 ₸"}
            ).action,
            "reject",
        )

    def test_service_uses_validated_policy(self):
        with (
            TestClient(app) as api,
            patch.object(core, "ACTIVE_MODEL", "test"),
            patch.object(
                core,
                "ask_llm",
                return_value=analysis(
                    hard_blocker=True, should_apply=True
                ).model_dump_json(),
            ),
        ):
            response = api.post(
                "/v1/analyze", json={"vacancy": {"description": "Работа"}}
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["should_apply"])

    def test_unavailable_service_fails_closed(self):
        with patch.object(
            client.requests, "post", side_effect=client.requests.ConnectionError
        ):
            result = asyncio.run(client.analyze_vacancy({}))
        self.assertIn("error", result)

    def test_invalid_service_decision_fails_closed(self):
        with patch.object(client.requests, "post") as post:
            post.return_value.json.return_value = {"decision": "maybe"}
            result = asyncio.run(client.analyze_vacancy({}))
        self.assertIn("error", result)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "history.db"

    def tearDown(self):
        self.temp.cleanup()

    def record(self, status="applied", vacancy_id="42"):
        return {
            "timestamp": "2026-10-15",
            "vacancy": {"id": vacancy_id},
            "result": {"status": status},
        }

    def test_blocked_state_survives_restart_and_later_error(self):
        store = Store(self.path)
        store.append(self.record("submission_pending"))
        store.append(self.record("form_error"))
        self.assertEqual(Store(self.path).processed(), ["42"])

    def test_history_pagination_and_validation(self):
        with TestClient(create_app(self.path)) as api:
            for i in range(3):
                self.assertEqual(
                    api.post(
                        "/v1/records", json=self.record(vacancy_id=str(i))
                    ).status_code,
                    201,
                )
            page = api.get("/v1/records?limit=2").json()
            self.assertEqual([r["vacancy"]["id"] for r in page], ["2", "1"])
            older = api.get(
                "/v1/records", params={"before": page[-1]["record_id"]}
            ).json()
            self.assertEqual(len(older), 1)
            self.assertEqual(api.get("/v1/records?limit=0").status_code, 422)
            self.assertEqual(api.post("/v1/records", json={}).status_code, 422)

    def test_pending_write_failure_prevents_browser_click(self):
        import apply

        page = AsyncMock()
        vacancy = {"id": "42", "title": "Python", "url": "https://example.test"}
        result = {"decision": "apply", "should_apply": True, "cover_letter": "Письмо"}
        with (
            patch.object(apply, "check_already_applied", return_value=False),
            patch.object(
                apply, "extract_vacancy_text", return_value={"description": "Работа"}
            ),
            patch.object(apply, "analyze_vacancy", return_value=result),
            patch.object(apply, "find_response_button", return_value=page),
            patch.object(apply, "save_result", side_effect=OSError("disk full")),
        ):
            with self.assertRaises(OSError):
                asyncio.run(apply.process_vacancy(page, vacancy, set(), "auto"))
        page.click.assert_not_awaited()
