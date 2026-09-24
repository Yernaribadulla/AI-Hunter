# AI-Hunter

AI-powered job search and application automation for HeadHunter (hh.kz).

AI-Hunter combines deterministic vacancy filtering, local LLM analysis and browser automation to help find relevant vacancies and automate parts of the application process.

## What it does

The project follows a pipeline:


hh.kz
  ↓
Vacancy collection
  ↓
Deterministic filtering
  ↓
Candidate/profile matching
  ↓
Local LLM analysis
  ↓
Application decision
  ↓
Cover letter generation
  ↓
Browser automation
  ↓
Application result


The system is designed around a simple principle: use deterministic rules for large-scale filtering and use an LLM only where semantic analysis is useful.

## Features

* Search vacancies on hh.kz
* Collect vacancy information using the HH API and Playwright
* Filter vacancies by:

  * skills
  * role/direction
  * experience
  * salary
  * location
  * remote work
  * seniority
* Score vacancies from 0 to 100
* Classify vacancies as:

  * `apply`
  * `review`
  * `skip`
* Analyze vacancies with a local LLM
* Generate application cover letters
* Automate the application process through Playwright
* Attach a resume automatically
* Store processed applications and results
* Avoid processing the same vacancy repeatedly

## Tech Stack

* Python
* Requests
* Playwright
* OpenAI-compatible API
* LM Studio
* Qwen
* JSON / JSONL
* hh.ru / hh.kz

The LLM can run locally through LM Studio, so vacancy analysis does not require sending the candidate's data to a remote LLM provider.

## Project Structure


AI-Hunter/
├── apply.py
├── candidate.py
├── config.py
├── filter.py
├── hh_api.py
├── llm_test.py
├── main.py
├── profile.json
├── test_hh.py
│
├── filtered.json
├── vacancies.json
├── suitable_vacancies.json
└── results.jsonl


### Core modules

`apply.py`

Main automation pipeline. Collects vacancies, analyzes them, generates cover letters and performs browser-based applications.

`filter.py`

Deterministic vacancy scoring and filtering. It evaluates vacancies before they reach the LLM stage.

`hh_api.py`

Small client for the HeadHunter API.

`test_hh.py`

Playwright-based vacancy collection from hh.kz when browser collection is required.

`candidate.py`

Candidate profile used by the filtering logic.

`profile.json`

Extended candidate profile and job-search preferences.

`llm_test.py`

Minimal test client for the local LM Studio OpenAI-compatible API.

`main.py`

Basic HH API search example.

## Vacancy Scoring

The deterministic filter calculates a score from several signals.

Examples include:

* relevant job direction
* matching technical skills
* required experience
* salary
* location
* remote work
* seniority
* language requirements
* education requirements

The resulting score is used to decide whether a vacancy should be applied to, reviewed manually, or skipped.

This stage intentionally runs before LLM analysis so that the local model does not have to process every vacancy returned by the job board.

## Local LLM

AI-Hunter is designed to work with a local OpenAI-compatible LLM server.

The current development configuration uses LM Studio:


http://localhost:1234/v1


and a Qwen model.

Example:


from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
)


Start LM Studio, load the desired model and make sure its local API server is running before using the LLM functionality.

## Installation

Clone the repository:


git clone https://github.com/Yernaribadulla/AI-Hunter.git
cd AI-Hunter


Create a virtual environment:


python -m venv .venv


Activate it on Windows:


.\.venv\Scripts\Activate.ps1


Install dependencies:


pip install requests playwright openai


Install the Playwright browser:


playwright install chromium

## Configuration

Configure the candidate profile in:

candidate.py
profile.json


Configure HH API settings in:


config.py


For local LLM functionality, make sure LM Studio is running and exposes an OpenAI-compatible endpoint.

The browser automation also requires an authenticated hh.kz browser session.

## Running

### Test the local LLM


python llm_test.py


### Test HH API search


python main.py


### Run deterministic filtering


python filter.py


### Run application automation


python apply.py


`apply.py` uses a persistent Playwright browser session and can interact with hh.kz on the user's behalf. Review the configuration and search criteria before running it.

## Architecture

AI-Hunter intentionally separates deterministic logic from AI logic.


                 ┌──────────────────┐
                 │     hh.kz        │
                 └────────┬─────────┘
                          │
                 ┌────────▼─────────┐
                 │ Vacancy Collector│
                 │ API / Playwright │
                 └────────┬─────────┘
                          │
                 ┌────────▼─────────┐
                 │ Deterministic    │
                 │ Filter & Scoring │
                 └────────┬─────────┘
                          │
                    Relevant jobs
                          │
                 ┌────────▼─────────┐
                 │ Local LLM         │
                 │ Qwen / LM Studio  │
                 └────────┬─────────┘
                          │
                 ┌────────▼─────────┐
                 │ Application       │
                 │ Automation        │
                 └──────────────────┘


This architecture reduces unnecessary LLM calls and keeps basic matching logic predictable.

## Data

The repository contains generated vacancy and result files used during development.

Examples:


vacancies.json
filtered.json
suitable_vacancies.json
results.jsonl


These files are not required for the core architecture and can be regenerated by the corresponding scripts.

## Important Notes

This project automates interaction with a third-party job platform. Automated applications should be used carefully and in accordance with the platform's terms and applicable rules.

AI-generated application text should be reviewed to ensure that it does not claim experience or skills that the candidate does not actually have.

The project is primarily a personal automation/portfolio project rather than a production-ready job platform.

## Author

**Yernar Ibadulla**

AI Integration / Automation / Python Developer

GitHub: https://github.com/Yernaribadulla
