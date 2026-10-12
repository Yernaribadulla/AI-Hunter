# AI-Hunter

Local-first job discovery, vacancy analysis, and supervised application assistant for HeadHunter.

AI-Hunter combines deterministic vacancy filtering, a local LLM, Pydantic validation, Playwright browser automation, persistent JSONL state, and a confirmation-first application mode. It is designed as a portfolio project and personal job-search tool—not as unattended mass application software.

## Pipeline

```text
Discovery queries → HH collection → normalization/deduplication → local LLM analysis
→ Pydantic validation → deterministic safety decision → letter validation
→ automatic or confirmation-first application → persistent JSONL log
```

The LLM proposes structured analysis; Python owns the final decision. Hard blockers, missing cover letters, language mismatches, salary constraints, duplicate applications, and invalid model output are handled by deterministic checks.

## Main capabilities

- Related-title discovery for Python, backend, AI integration, LLM, API, CRM, automation, and full-stack roles.
- Local analysis through an OpenAI-compatible LM Studio endpoint.
- Structured `VacancyAnalysis` validation with Pydantic.
- Transferable-skill and commercial-experience matching.
- Russian/English cover-letter generation and language validation.
- Duplicate protection through persistent local status records.
- Automatic mode or confirmation-first mode before each final application click.
- Persistent Playwright browser session with user-controlled login and CAPTCHA handling.

## Safety model

The project does not bypass CAPTCHA or anti-bot controls. Browser sessions, cookies, resumes, vacancy history, generated letters, and local model data remain local. Never commit credentials, tokens, cookies, `hh_session`, `results.jsonl`, resumes, or exported vacancy datasets.

The confirmation-first mode shows the generated letter before submission. A successful browser click is not treated as proof that HH recorded the application; uncertain and send-error states require manual verification.

## Local LLM

- Model: `qwen/qwen3-4b-2507`
- Endpoint: `http://localhost:1234/v1/chat/completions`
- Request timeout: 300 seconds

## Requirements

- Windows, Python 3.11+, Requests, Playwright, Pydantic
- PySide6 for the desktop operator interface
- Chromium installed for Playwright
- LM Studio with an OpenAI-compatible local endpoint

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install requests playwright openai pydantic
pip install PySide6
playwright install chromium
```

## Run

Start LM Studio, load the configured model, enable the local server, then run `python apply.py`. For the desktop operator interface, run `python desktop.py`.

The workflow opens a persistent browser, waits for the user to log in and complete interactive checks, asks for the application mode, then processes vacancies under the selected safety policy.

## Testing

```powershell
python -m compileall -q apply.py
python -m unittest discover -s tests -v
```

The browser workflow should be tested with sending disabled or under manual supervision.

## Project status

AI-Hunter V2 is an active portfolio project suitable for local experimentation and supervised applications. It is not a production recruitment platform, does not guarantee correct decisions, and should not be used for unattended mass outreach.
