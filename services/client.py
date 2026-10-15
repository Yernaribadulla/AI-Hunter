"""HTTP boundary used by the operator. Failures never imply permission to send."""

import asyncio
from datetime import datetime, timezone
import os
import requests
from config import LM_MODEL, PROMPT_VERSION

ANALYSIS_URL = os.getenv("JOBHUNTER_ANALYSIS_URL", "http://127.0.0.1:8011").rstrip("/")
HISTORY_URL = os.getenv("JOBHUNTER_HISTORY_URL", "http://127.0.0.1:8012").rstrip("/")


def check_lm_studio():
    try:
        response = requests.get(ANALYSIS_URL + "/ready", timeout=(3, 10))
        response.raise_for_status()
        response = requests.get(HISTORY_URL + "/health", timeout=(3, 10))
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        print("Services unavailable. Run python run_services.py:", exc)
        return False


async def analyze_vacancy(vacancy_data, session_instruction=""):
    def request():
        response = requests.post(
            ANALYSIS_URL + "/v1/analyze",
            json={"vacancy": vacancy_data, "instruction": session_instruction},
            timeout=(3, 310),
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or (
            "error" not in result
            and result.get("decision") not in {"apply", "manual_review", "reject"}
        ):
            raise ValueError("Invalid analysis service response")
        return result

    try:
        return await asyncio.to_thread(request)
    except (requests.RequestException, ValueError) as exc:
        return {"error": "analysis_service_error", "reason": str(exc)}


def load_processed_ids():
    response = requests.get(HISTORY_URL + "/v1/processed", timeout=(3, 10))
    response.raise_for_status()
    return set(response.json()["ids"])


def save_result(vacancy, result):
    result = dict(result)
    result.setdefault("model", LM_MODEL)
    result.setdefault("prompt_version", PROMPT_VERSION)
    result.setdefault(
        "application_mode", os.getenv("JOBHUNTER_APPLICATION_MODE", "manual")
    )
    result.setdefault("decision_reason", result.get("reason", ""))
    response = requests.post(
        HISTORY_URL + "/v1/records",
        json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vacancy": vacancy,
            "result": result,
        },
        timeout=(3, 10),
    )
    response.raise_for_status()


def load_history(limit=500):
    response = requests.get(
        HISTORY_URL + "/v1/records", params={"limit": limit}, timeout=(2, 3)
    )
    response.raise_for_status()
    return response.json()
