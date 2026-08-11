# Agent Harness Overview

This repository is a **Python/Streamlit application** (Avaliação de Candidatos — an HR résumé-screening tool that calls the Groq API). It is developed with the help of **Claude Code** acting as an interactive coding assistant in this working directory.

There is no autonomous multi-agent pipeline configured in this repo. There are no Dev/QE/Ops subagent roles, no local MCP servers, and no telemetry collection. If you are an AI agent picking up work here, treat this as a normal single-agent coding session: read code, make changes, run the real tests below, report honestly.

Do not assume the presence of harness infrastructure beyond what is listed in this file — search before relying on anything not documented here.

# System Core Components

```
app.py                     Streamlit UI and top-level control flow (single entry point)
services/
  config.py                Reads secrets/env vars (GROQ_API_KEY, GROQ_MODEL, TESSERACT_CMD, OCR_LANG)
  extract.py                .pdf / .docx / .md / .txt resume parsing, incl. OCR fallback for scanned PDFs
  llm.py                    Groq client call (openai/gpt-oss-120b default), prompt assembly, error mapping
prompts/analysis.md         The LLM prompt template used at runtime (not an agent instruction file)
tests/                      pytest suite — test_app.py, test_llm.py, test_config.py, test_extract.py
assets/                     Static CSS/logo used by the Streamlit UI
.streamlit/                 Streamlit config + local secrets (secrets.toml is gitignored)
Dockerfile, .dockerignore   Container build for deployment
packages.txt                System (apt) deps for Streamlit Community Cloud — Dockerfile is NOT used there
.claude/
  settings.local.json       Bash command permission allowlist for this Claude Code session
  launch.json               Editor/debug launch config
```

There is **no `.mcp.json`**, no subagent definitions under `.claude/agents/`, and no `telemetry/` directory in this repo. Don't look for them.

# State & Memory Management

There is **no `LEARNING.md`** or other in-repo file tracking lessons across sessions. Cross-session context, for this assistant specifically, is handled by Claude Code's external auto-memory system, which lives outside this repository (not version-controlled, not visible to other tools or contributors).

Practical consequence: **this repo's own history is the only durable, shareable memory.** When you learn something a future session (human or agent) will need — a non-obvious constraint, a rejected approach, a why-behind-a-decision — put it in:
- a **commit message**, for decisions tied to a specific change, or
- a **code comment**, only when the *why* isn't obvious from reading the code.

If you want a persistent, human-readable lessons log for this project, create `LEARNING.md` explicitly and reference it here — it does not currently exist.

# Guardrails & Quality Gates

The only automated quality gate currently configured in this repo is the **test suite**. There is no linter, formatter, or security scanner wired in (no ruff/flake8/black config, no bandit/pre-commit hooks).

**Before reporting any change as done:**

1. **Test Suite** — run `python -m pytest -q` from the repo root (config: [pytest.ini](pytest.ini), tests live in `tests/`). All tests must pass. Do not delete, skip, or weaken a failing test to force a pass — fix the underlying issue or explain to the user why the test's expectation changed.

That is the entire gate today. If you add lint, formatting, or security tooling to this repo, update this section to reflect the real order of execution — don't describe steps that aren't actually enforced.

# Agent Instructions

If you are an AI agent operating in this repository:

1. **Read this file first**, at the start of the session, before making changes.
2. **Run `python -m pytest -q` before declaring a task complete.** A task is not done if tests fail.
3. **Do not claim a quality gate passed without having actually run it in this session.** Don't infer or assume prior results still hold.
4. **Do not bypass the test suite** (e.g. `--no-verify`-style skips, commenting out assertions, deleting tests) to make a task appear finished.
5. **If this file's description of the repo stops matching reality** (new tooling added, structure changed), update `HARNESS.md` in the same change — don't leave it stale.
