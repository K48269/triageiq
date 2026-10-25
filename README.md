# TriageIQ

AI-powered pipeline-failure triage: failure event -> Agentia CLI fetches logs -> **local LLM (Ollama)** classifies the root cause -> plain-language summary + retry/rollback command posted to Slack / Teams. No API tokens, logs never leave your environment.

```
CI failure webhook ──> triageiq serve ──> agentia CLI (logs) ──> redact ──> Ollama
                                                                              │
                  Slack / Teams  <── summary + commands <── SQLite history <──┘
```

## Quick start
```bash
ollama pull qwen2.5:7b-instruct          # or llama3.1:8b
cp triageiq.example.json triageiq.json   # set model, webhooks, secret
python -m triageiq demo                  # runs samples/*.log through the real pipeline
python -m triageiq analyze --run-id 123 --pipeline payments-api   # uses the CLI to fetch logs
python -m triageiq serve                 # POST /events from your CI on failure
python -m triageiq history
python -m unittest discover -s tests     # offline tests (fake Ollama)
```
Python 3.9+, standard library only.

## Wiring the Agentia CLI  (check this first)
Two things are templates because I couldn't verify the exact CLI syntax:
- `log_command` in `triageiq.json` - must print the run's logs to stdout. Replace with the real Agentia command (try `agentia --help`, and `agentia <area> --json` variants).
- `commands` - retry/rollback strings shown in chat. Edit to real syntax.
Retry/rollback commands come from these templates, **not** from the LLM, so the model can't invent a dangerous command.

## Event payload (POST /events, header `X-TriageIQ-Token`)
```json
{"status":"failed","run_id":"123","pipeline":"payments-api","environment":"UAT","logs":"(optional inline logs)"}
```
Non-failure statuses are ignored. Add `logs` to skip the CLI fetch.

## Design notes
- Redaction (`redact.py`) scrubs tokens, keys, emails before the LLM, DB and chat see anything.
- Long logs are condensed to error lines + context (small local models degrade on huge inputs).
- Output is validated; bad/garbled model output becomes `other` with low confidence and a "check the raw log" note.
- Repeat failures are detected via a normalised evidence signature stored in SQLite.

## Demo script (proves it isn't hard-coded)
1. `python -m triageiq demo` -> two different logs, two different categories and fixes.
2. Break your own pipeline a third way (e.g. delete a referenced component) and show the diagnosis.
3. Re-run the same failure -> "Seen 1 time(s) before".

## Roadmap
Auto-create tickets, risk scoring from failure patterns, governance checks.
