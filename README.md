# AI-Hunter

AI-Hunter is a local-first job discovery, vacancy analysis and controlled application assistant for HeadHunter. It combines deterministic filtering, a local LLM and Playwright browser automation. The project is designed for a personal job search and portfolio demonstration, not for mass or unattended applications.

## What It Solves

Manual job hunting usually repeats the same work:

- searching across many related job titles;
- opening and reading long vacancy descriptions;
- comparing requirements with a candidate profile;
- writing a tailored cover letter;
- tracking which vacancies were already reviewed or submitted;
- repeating the process after a temporary error.

AI-Hunter turns this into a staged pipeline while keeping the final browser action observable and guarded.

## Architecture

```text
Discovery queries
       |
       v
HH vacancy collection through Playwright
       |
       v
Normalization and vacancy deduplication
       |
       v
Local LLM analysis through LM Studio
       |
       v
Pydantic schema validation
       |
       v
Deterministic safety and decision engine (`safety.py`)
       |
       +--> reject / manual review
       |
       v
Cover-letter language validation
       |
       v
Application mode: automatic or confirmation-first
       |
       v
Persistent JSONL result log
```

The project intentionally separates semantic analysis from deterministic safety decisions. The model proposes an analysis; the application validates the structure, thresholds, hard blockers, cover letter and processing status before continuing.

## Discovery

The collector searches Astana (`area=160`) using related discovery queries rather than one exact job title. Current groups include:

- Python, Backend Python and Python Automation;
- Backend Developer;
- Full-stack, Fullstack and Web Developer;
- React + Node.js and React + TypeScript;
- JavaScript and TypeScript;
- AI Integration Developer, AI Automation, AI Engineer, AI Assistant and LLM;
- API Integration, Integration Developer and Integration Specialist;
- Automation Developer, RPA, n8n, Make.com, No-Code and Zapier;
- CRM Developer, amoCRM and Bitrix24;
- Junior Developer and Python internship searches.

Discovery intentionally has a wider scope than the final decision. A vacancy found by `AI Engineer`, for example, is not automatically treated as a match for ML research. The scoring stage evaluates the actual responsibilities and requirements.

## Analysis And Safety

`candidate.py` is the single runtime source of truth for the structured candidate profile and its text representation. `config.py` is the single source of truth for thresholds, HH settings, LM Studio settings and application defaults. The old `profile.json` is not loaded by the production pipeline.

The local model returns structured JSON with fields such as:

- `score`;
- `direction_match`;
- `hard_blocker`;
- matched, transferable and missing skills;
- job level and commercial-experience requirements;
- required commercial years, language and remote status;
- cover letter. The model's `should_apply` field is informational only.

The extracted JSON is validated with the strict `VacancyAnalysis` Pydantic model. Values such as `hard_blocker: "maybe"` are invalid and cause a safe failure, so an invalid model response can never authorize an application.

The rule-based safety layer then:

- rejects hard blockers and unrelated directions;
- applies separate thresholds for regular and remote vacancies;
- rejects missing cover letters;
- compares mandatory commercial years with the candidate's confirmed experience independently of seniority;
- applies explicit salary minimums when the vacancy publishes a salary below the candidate profile; unknown salary remains reviewable;
- validates that the cover letter uses one language and matches the dominant language of the vacancy;
- verifies that the inserted browser text exactly matches the generated letter before sending.

If any validation fails, the final application button is not clicked. Python owns the final APPLY, REVIEW or REJECT decision; the LLM never has authority to submit.

The main runtime modules are deliberately small in responsibility: `candidate.py` (profile), `config.py` (settings), `models.py` (validated LLM schema), `safety.py` (deterministic policy), `apply.py` (existing orchestration and browser workflow), and `tests/` (decision checks). The legacy `filter.py` is not a second production decision engine.

## Login And Application Flow

The application uses a persistent Playwright browser profile in `hh_session`.

1. Start the program.
2. Log in to the HH account in the opened browser.
3. Complete CAPTCHA or other interactive checks manually.
4. Enter `Подтвердить` in the console.
5. Choose one application mode:
   - automatic application submission;
   - confirmation-first submission, also called the safety mode.
6. The program collects and analyzes vacancies.
7. Only accepted vacancies proceed to the application form.

In automatic mode, a validated accepted application is submitted without another console prompt.

In confirmation-first mode, the generated cover letter is shown before the final application action. Press ENTER to submit it, type `пропустить` to skip the vacancy, or type an instruction for the model to regenerate the letter. That instruction is kept only for the current process session and is not written into the candidate profile.

The program does not upload a local PDF resume anymore. HH uses the resume selected in the user's account profile. This avoids brittle file-upload fields and prevents an application from depending on a changing form control.

## V2 Safety Mode

The original version started sending accepted applications immediately after login and analysis. It did not provide a per-application confirmation option.

V2 preserves the original automatic workflow but adds a choice between:

- automatic submission for a hands-off run;
- confirmation-first submission as a safety layer before each final click.

The confirmation-first mode does not change deterministic scoring or silently approve a rejected vacancy. It only controls the final application action after the vacancy has passed analysis, safety checks and cover-letter validation.

## Duplicate Protection And State

Results are appended locally to `results.jsonl` (the file is ignored by Git because it may contain personal vacancy history). Final statuses are used to avoid repeating work after a restart:

- `applied`;
- `already_applied`;
- `rejected_by_ai`.

Temporary or technical failures remain retryable:

- `llm_error`;
- `letter_error`;
- `send_error`;
- `unknown`;
- other form and navigation errors.

The same local-only policy applies to generated vacancy datasets (`vacancies.json`, `filtered.json`, `suitable_vacancies.json`) and the legacy `profile.json`. The production runtime profile is `candidate.py`.

This distinction prevents rejected vacancies from being analyzed again while still allowing recovery from a timeout or a broken browser state.

## Local LLM

The current configuration uses:

```text
Model: qwen/qwen3-4b-2507
Endpoint: http://localhost:1234/v1/chat/completions
Request timeout: 300 seconds
```

LM Studio must have the model loaded and its OpenAI-compatible local server enabled. The model runs locally, so vacancy descriptions, profile data and generated letters are not sent to a hosted LLM provider by this application.

## Installation

Requirements:

- Windows;
- Python 3.11+;
- Playwright;
- Requests;
- OpenAI-compatible local server through LM Studio;
- Chromium installed for Playwright.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install requests playwright openai pydantic
playwright install chromium
```

## Run

Start LM Studio, load `qwen/qwen3-4b-2507`, enable the local server, then run:

```powershell
python apply.py
```

The program prints the selected model, resume paths, search progress, analysis result, cover letter and final status for each vacancy.

## Other Utilities

`main.py` is a small HH API search example. The HH API can reject unauthenticated or restricted requests with HTTP 403, so it is not the main discovery path for the application workflow.

`filter.py` is a deterministic offline vacancy filter for `vacancies.json`. It is useful for experiments and does not submit applications.

`test_hh.py` is an earlier browser collection prototype. The production flow is implemented in `apply.py`.

## Benefits

- reduces repetitive vacancy research;
- keeps LLM analysis local;
- combines semantic reasoning with deterministic safety rules;
- preserves processing history;
- avoids rechecking final rejected vacancies;
- supports Russian and English vacancy communication;
- generates tailored cover letters from the actual vacancy;
- keeps login, CAPTCHA and the application session under user control;
- allows automatic submission or confirmation-first submission per run;
- allows session-only cover-letter instructions before a manual approval;
- does not upload a resume file through a fragile form field;
- supports portfolio-quality demonstration of Python, LLM integration and browser automation.

## Limitations And Risks

This is not a production recruitment platform and it cannot guarantee a correct application decision.

- Vacancy descriptions can be incomplete, misleading or dynamically rendered.
- A local LLM can hallucinate or misunderstand a requirement.
- Language detection is heuristic and intentionally blocks uncertain mixed-language letters.
- Website selectors can change when HH changes its UI.
- HH can rate-limit, challenge or block automated traffic.
- API search may return HTTP 403 without the required authorization or access policy.
- A successful browser click is not an absolute guarantee that HH recorded the response.
- `unknown` and `send_error` outcomes require manual verification before retrying.
- The persistent browser session contains sensitive account state and must not be shared.
- `results.jsonl`, vacancy data and resumes can contain personal or sensitive information.
- Automated applications must be used carefully and in accordance with HH terms and applicable law.

The application deliberately does not bypass CAPTCHA or anti-bot controls.

## Known Problems And Their Fixes

### Slow local model responses

LM Studio requests previously timed out after 180 seconds. The request timeout is now 300 seconds and the configured model is `qwen/qwen3-4b-2507`.

### Mixed Russian and English letters

The prompt now requires one language. A post-generation validator compares the letter with the dominant language of the vacancy and blocks mixed or mismatched output.

### Applications without a cover letter

The application verifies the exact text after inserting it into the HH form. If the field is missing or the text does not match, the final send action is skipped.

### Resume upload failures

Local PDF upload was disabled. The resume is selected in the HH profile, so the workflow does not depend on a file input that may be absent from the form.

### Repeating rejected vacancies

`rejected_by_ai` is now persisted as a final local decision and skipped on future launches. Technical failures remain retryable.

### Login timing

The browser opens before collection and waits for the explicit console command `Подтвердить`, giving the user time to authenticate and complete interactive checks.

### Automatic submission and safety mode

The original V1 flow submitted every accepted vacancy automatically after the initial login gate. V2 adds a per-run choice: automatic submission or confirmation-first submission. In the latter mode, every generated letter can be approved, skipped or regenerated with a temporary user instruction before the final click.

## Privacy And Security

Do not commit:

- `hh_session`;
- `results.jsonl`;
- personal resumes;
- exported vacancy datasets;
- tokens, cookies or credentials.

The repository already ignores the local browser session, result log, generated resume output and local resume-builder scripts.

## Testing

Run a syntax check before starting:

```powershell
python -m compileall -q apply.py
```

The main browser workflow requires a real HH session and a running LM Studio server, so a full end-to-end test should be performed with sending disabled or under manual supervision.

## Project Status

AI-Hunter V2 is an active personal portfolio project. It supports both automatic application submission and a confirmation-first safety mode. The current implementation is suitable for local experimentation and supervised applications. It should not be treated as unattended mass outreach or a guaranteed production automation system.
