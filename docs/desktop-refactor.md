# AI-Hunter desktop refactor

Scope: the native Python mini-application in AI-Hunter. No outreach-agent code or external portfolio website is changed. Baseline: main at `1bd6fcc`. LM Studio was switched off throughout verification.

## Counc

**Verdict:** keep PySide6 and the existing deterministic decision policy; separate desktop infrastructure from widgets and pipeline responsibilities, and make readiness and confirmation visible.

**Socrates:** the actual problem is operating a local job-search workflow, including when dependencies are unavailable. The old startup confirmation opens an unrelated browser before the pipeline's persistent Chromium session exists. Counterargument: a short setup wizard can guide new users; the replacement moves that guidance to the actual session checkpoint.

**Skeptic:** attractive cards cannot fix event framing, stale process state, unsaved results or a table whose rows move while being populated. The implementation needs regression tests for those contracts. Counterargument: a large rewrite can regress browser selectors; page operations and prompt content are moved without changing their meaning, and live selector verification is explicitly left to supervised testing.

**Practitioner / interface:** a graphite-and-mint native workspace offers clear navigation, readable counters, a visible offline notice, and a plain-text log. Keep the current storage format and launch commands. Counterargument: PySide6 has less layout flexibility than a browser UI; scrollable pages, a minimum usable window size and standard Qt keyboard navigation keep the native application practical.

**Arbiter:** retain native deployment, preserve user data and the CLI entry point, and default the desktop to per-application review. The meaningful trade-off is stricter model selection: the app now requires the configured model instead of silently taking the first model returned by LM Studio. Configure a different model explicitly in `config.py` if desired. Settings remain read-only rather than adding an untested configuration persistence layer.

## Changes

- `hunter/ui/`: Russian workspace, offline banner, launch controls, real counters, bounded plain-text log, model-backed vacancy table, review dialogs and a separate QSS theme.
- `hunter/process.py`: inherited system environment, UTF-8/unbuffered child output, failed-start handling, independent stdout/stderr decoders, final-line flushing, stop watchdog and cleanup.
- `hunter/bridge.py`: bounded loopback frames, queued requests, pending-request cancellation and server shutdown. The GUI confirms the actual worker browser session.
- `hunter/history.py`: shared append-only storage, validated record shapes, partial-line tolerance and the existing terminal-status deduplication policy. Write failures now propagate so processing cannot silently claim durable success.
- `hunter/browser.py`, `analysis.py`, `llm.py`, `prompts.py`: explicit browser and model responsibilities. Unreachable duplicate safety logic is removed; `safety.evaluate` remains authoritative. Persisted application mode now reflects the actual selected mode.

## Verification

The original 18 decision/schema tests pass. New tests cover malformed history, terminal-status deduplication, numeric sorting and filter persistence, UTF-8 events split at every byte, missing final newlines, malformed events, offline and wrong-model states, model request contracts, bridge shutdown and response delivery, actual session confirmation and cancellation, subprocess environment inheritance, nonzero exit, failed start and stop.

Rendered the real Qt widgets at desktop and compact dimensions, including overview, history, settings and both review dialogs. Screenshots contain no live applications or generated model responses. The offline screen in the README is a real widget render, not an HTML mockup.

Cheap next validation: enable LM Studio, load the configured Qwen model, press **Проверить связь**, start in manual mode, confirm login in the Chromium window, and inspect one prepared letter. Verify the result in HH before allowing another run. Actual model inference, browser selectors and network delivery were not exercised while LM Studio was off.

## Limits

The application keeps JSONL rather than introducing a database migration. History refreshes only on decisions, completion or explicit navigation; very large histories may eventually benefit from indexing. Process interruption can occur during a browser action and cannot roll back an application already recorded by HH. No automatic resubmission is added. The loopback bridge is intended for a single-user local desktop, not remote access.
