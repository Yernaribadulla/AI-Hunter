"""Regression tests without a real model, HH session or application submission."""

import asyncio
import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import requests

from hunter.history import HistoryStore, vacancy_values
from hunter.protocol import OutputDecoder, EVENT_PREFIX
from hunter.bridge import BridgeServer, PendingRequest
from hunter.health import probe_model
from hunter.llm import LocalModelClient
import config


class HistoryTests(unittest.TestCase):
    def test_corrupt_and_partial_lines_do_not_hide_valid_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            store = HistoryStore(path)
            self.assertEqual(store.records(), [])
            record = {"vacancy": {"id": 12}, "result": {"status": "applied"}}
            store.append(record)
            with path.open("a", encoding="utf-8") as file:
                file.write('null\n[]\n{"vacancy":null,"result":{}}\n{broken\n')
            self.assertEqual(store.records(), [record])
            self.assertEqual(store.processed_ids(), {"12"})

    def test_only_final_statuses_prevent_reprocessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(Path(tmp) / "results.jsonl")
            for index, status in enumerate(
                (
                    "applied",
                    "already_applied",
                    "rejected_by_ai",
                    "error",
                    "manual_review",
                    "send_error",
                )
            ):
                store.append({"vacancy": {"id": index}, "result": {"status": status}})
            self.assertEqual(store.processed_ids(), {"0", "1", "2"})

    def test_nested_employer_and_zero_score_are_preserved(self):
        values = vacancy_values(
            {
                "vacancy": {"name": "Python", "employer": {"name": "Acme"}},
                "result": {"score": 0},
            }
        )
        self.assertEqual(values[:3], ["Python", "Acme", 0])

    def test_write_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                HistoryStore(Path(tmp)).append({"vacancy": {}, "result": {}})


class DecoderTests(unittest.TestCase):
    def test_every_byte_boundary_including_cyrillic(self):
        payload = {"type": "decision_made", "title": "Разработчик", "processed": 1}
        raw = (EVENT_PREFIX + json.dumps(payload, ensure_ascii=False) + "\r\n").encode()
        decoder = OutputDecoder()
        result = []
        for byte in raw:
            result.extend(decoder.feed(bytes([byte])))
        self.assertEqual(result, [("event", payload)])

    def test_final_line_without_newline_is_not_lost(self):
        decoder = OutputDecoder()
        self.assertEqual(decoder.feed(b"partial"), [])
        self.assertEqual(decoder.feed(b"", final=True), [("text", "partial")])

    def test_bad_event_does_not_break_following_events(self):
        decoder = OutputDecoder()
        rows = decoder.feed(
            (EVENT_PREFIX + "null\n" + EVENT_PREFIX + '{"type":"ok"}\n').encode()
        )
        self.assertEqual(rows[0][0], "text")
        self.assertEqual(rows[1], ("event", {"type": "ok"}))


class ModelTests(unittest.TestCase):
    @patch("hunter.health.requests.get", side_effect=requests.ConnectionError)
    def test_offline_is_a_normal_state(self, get):
        result = probe_model()
        self.assertFalse(result.ready)
        self.assertIn("LM Studio", result.message)
        get.assert_called_once_with(config.LM_MODELS_URL, timeout=(1, 2))

    @patch("hunter.health.requests.get")
    def test_missing_configured_model_is_not_ready(self, get):
        get.return_value.json.return_value = {"data": [{"id": "other-model"}]}
        self.assertFalse(probe_model().ready)
        get.return_value.json.return_value = {"data": [{"id": config.LM_MODEL}]}
        self.assertTrue(probe_model().ready)

    @patch("hunter.llm.requests.get")
    def test_transport_never_silently_selects_another_model(self, get):
        get.return_value.json.return_value = {"data": [{"id": "other-model"}]}
        with self.assertRaisesRegex(RuntimeError, "Загрузите модель"):
            LocalModelClient().select_model()

    @patch("hunter.llm.requests.post")
    def test_text_parts_and_request_contract(self, post):
        post.return_value.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Hello"},
                            {"type": "text", "text": " world"},
                        ]
                    }
                }
            ]
        }
        self.assertEqual(
            LocalModelClient().complete("test", "system", "prompt"), "Hello world"
        )
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 300))


class BridgeTests(unittest.TestCase):
    def test_late_send_cannot_override_cancellation(self):
        request = PendingRequest({"type": "application_review"})
        request.resolve({"action": "skip"})
        request.resolve({"action": "send"})
        self.assertEqual(request.response, {"action": "skip"})

    def test_shutdown_releases_waiting_client(self):
        bridge = BridgeServer()
        result = []

        def client():
            with socket.create_connection(
                bridge.server_address, timeout=3
            ) as connection:
                connection.sendall(b'{"type":"application_review"}\n')
                result.append(json.loads(connection.makefile("rb").readline()))

        thread = threading.Thread(target=client)
        thread.start()
        pending = bridge.requests.get(timeout=3)
        self.assertFalse(pending.event.is_set())
        bridge.close()
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [{"action": "skip"}])

    def test_review_response_reaches_client(self):
        bridge = BridgeServer()
        result = []

        def client():
            with socket.create_connection(
                bridge.server_address, timeout=3
            ) as connection:
                connection.sendall(b'{"type":"session_confirmation"}\n')
                result.append(json.loads(connection.makefile("rb").readline()))

        thread = threading.Thread(target=client)
        thread.start()
        pending = bridge.requests.get(timeout=3)
        pending.resolve({"action": "confirm"})
        thread.join(timeout=3)
        bridge.close()
        self.assertEqual(result, [{"action": "confirm"}])


class SessionTests(unittest.TestCase):
    def test_gui_waits_for_real_worker_session_confirmation(self):
        import apply

        page = Mock()
        page.reload = AsyncMock()
        with (
            patch.dict(os.environ, {"JOBHUNTER_GUI_BRIDGE_PORT": "12345"}),
            patch("apply.gui_request", return_value={"action": "confirm"}) as request,
        ):
            asyncio.run(apply.wait_for_hh_login(page))
        request.assert_called_once_with({"type": "session_confirmation"})
        page.reload.assert_awaited_once()

    def test_cancelled_login_never_collects_vacancies(self):
        import apply

        page = Mock()
        page.reload = AsyncMock()
        with (
            patch.dict(os.environ, {"JOBHUNTER_GUI_BRIDGE_PORT": "12345"}),
            patch("apply.gui_request", return_value={"action": "skip"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "отменён"):
                asyncio.run(apply.wait_for_hh_login(page))
        page.reload.assert_not_awaited()

    def test_unavailable_model_exits_with_failure_before_browser_launch(self):
        import apply

        with (
            patch("apply.check_lm_studio", return_value=False),
            patch("apply.async_playwright") as browser,
        ):
            with self.assertRaisesRegex(RuntimeError, "LM Studio"):
                asyncio.run(apply.main())
        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
