# Build and Test Commands

- Run app: `streamlit run app.py`
- Full test suite: `python -m pytest -q`
- Single file: `python -m pytest tests/test_llm.py -q`
- Single test: `python -m pytest tests/test_llm.py::test_build_prompt_single_resume -q`
- Lint: not configured — none to run
- Format: not configured — none to run
- Docker build: `docker build -t avaliacao-candidatos .`

# Code Style Guidelines

- **Paradigm**: procedural/functional. Classes only for exceptions.
- **Typing**: type-hint every function signature (params + return).
- **Errors**: raise specific typed exceptions in `services/*` (e.g. `RateLimitError`, `TokenLimitError`); `app.py` catches each type and shows a distinct `st.error`. Never swallow errors silently.
- **Naming**: `snake_case` functions/vars, `PascalCase` exceptions, `_leading_underscore` for module-private helpers/constants, `UPPER_SNAKE` for constants.
- **Comments**: none by default; only for non-obvious *why* (in Portuguese, matching existing comments). No docstrings unless behavior isn't obvious from the name.
- **Layer separation**: business logic lives in `services/`, UI-agnostic and independently testable; `app.py` only orchestrates UI + calls services.
- **UI/user-facing text**: Portuguese (pt-BR). Code identifiers: English.

# State and Context Anchors

- Read [HARNESS.md](HARNESS.md) first — pipeline rules, real quality gates, repo layout.
- Read [LEARNING.md](LEARNING.md) for historical lessons — non-obvious constraints, rejected approaches, why-behind-decisions. Append new lessons there; don't rewrite history.
- Whenever you fix a critical bug or complete a complex experiment, update [LEARNING.md](LEARNING.md).
