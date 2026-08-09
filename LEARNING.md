# LEARNING.md

Historical lessons for this repo — non-obvious constraints, rejected approaches, and why behind decisions. Referenced from [CLAUDE.md](CLAUDE.md) and [HARNESS.md](HARNESS.md). Append new entries at the bottom; don't rewrite history, just note when something in an old entry stopped being true.

## Merge conflicts must be verified, not just resolved in the editor

Commit `276e830` ("Merge conflits") was pushed to `main` with unresolved `<<<<<<< HEAD` / `=======` / `>>>>>>>` markers still inside `services/llm.py`, breaking `build_prompt` with a `SyntaxError`. The working tree looked fine because the fix existed uncommitted on disk — but HEAD (and origin/main) was broken.

**Rule**: after resolving a merge, `git diff HEAD` the affected files and re-run the test suite *before* committing. A file with no visible markers in your editor can still have committed markers in a prior commit.

## Streamlit's `file_uploader(type=[...])` is enforced server-side

As of streamlit 1.58.0, uploading a file whose extension isn't in `type=[...]` raises `StreamlitAPIException` during deserialization, before any app code runs. This means `services/extract.py`'s `UnsupportedFormatError` branch for `.doc` files is unreachable through the real widget — it can only be exercised by calling `extract_resume()` directly, or by monkeypatching `extract_resume` in an `AppTest`. Don't try to trigger it via `at.file_uploader[0].set_value(("x.doc", ...))`; it will blow up before app code sees it.

**Superseded** — see "The `type=[...]` restriction was actively harmful, not just untestable" below. `app.py` no longer sets `type=[...]` at all, so this entry's workaround (monkeypatch `extract_resume` instead of uploading a real `.doc`) is no longer needed for that case specifically — real `.doc` uploads now reach app code normally. The general lesson (Streamlit can validate widget state before script code runs) still stands and can bite other widgets.

## `AppTest`'s default timeout is too short for widget interactions like `st.pills`

The default `AppTest` timeout (3s) intermittently timed out on `st.pills` interactions in this environment. Fixed by passing `default_timeout=15` to `AppTest.from_file(...)` in `tests/test_app.py`'s `_app_test()` helper. If new widget-interaction tests start timing out, raise this further rather than assuming the app itself is hanging.

## Mocking service functions works with `AppTest` because it re-execs the script

`app.py` does `from services.llm import analyze_resumes`. `AppTest.run()` re-executes `app.py`'s source from scratch every call (not a cached import), so `monkeypatch.setattr(services.llm, "analyze_resumes", fake)` *before* `.run()` correctly makes `app.py` pick up the fake — the `from x import y` statement re-resolves against the (patched) module object each run. Verified empirically; don't assume it needs `monkeypatch.setattr("app.analyze_resumes", fake)` instead (that path is fragile since `app` isn't imported as a normal module by `AppTest`).

## `.streamlit/secrets.toml` may hold a live token — never dump it

The file is gitignored and exists locally. When checking for secrets, verify via file existence/size or targeted grep on tracked files, not by `cat`-ing or otherwise printing its contents into a transcript or tool output.

## Performance: Streamlit reruns the whole script on every interaction

Any `Path(...).read_text()` or similar disk I/O at module level in `app.py` runs on *every* widget interaction (typing, clicking), not just page load. Static reads (CSS, prompt template) are wrapped in `@st.cache_data`-decorated functions for this reason — see `load_css()` / `load_prompt_template()`.

## PyMuPDF page rendering isn't safe to parallelize; Tesseract OCR calls are

In `services/extract.py::_ocr_pdf`, page rasterization (`page.get_pixmap`) is done sequentially — PyMuPDF documents aren't thread-safe across threads. Only the Tesseract OCR step (`pytesseract.image_to_string`, which shells out to a subprocess) is parallelized via `ThreadPoolExecutor`.

## No lint/format/security tooling is configured

Repeatedly re-verified (no `ruff`/`flake8`/`black`/`bandit` config, no `pyproject.toml`, no pre-commit hooks). `pytest` is the only real quality gate. Don't reference a lint/format/security step as if it exists — check `HARNESS.md` before claiming otherwise, and update both files together if that ever changes.

## The `type=[...]` restriction was actively harmful, not just untestable

Uploading a `.doc` file crashed the whole app with an uncatchable exception — not just an unfriendly message. Root cause: `st.file_uploader(..., type=["pdf", "md", "docx"])`'s extension check (`enforce_filename_restriction`) runs during `session_state`'s widget-deserialization step, which Streamlit performs as part of `on_script_will_rerun` — *before* `app.py`'s script body executes at all. A `try/except` wrapped around the `st.file_uploader(...)` call itself cannot catch it, because the raise happens outside that call's stack frame entirely (confirmed by tracing the exception through `script_runner.py` — it originates in `code_to_exec` before `exec(code, module.__dict__)` runs). The user was stuck because every rerun re-hit the same crash for the same attached file.

**Fix**: don't rely on `file_uploader`'s `type=[...]` for validation at all. `app.py` no longer passes `type=`; `services/extract.py::extract_resume` now validates the extension itself (raising `UnsupportedFormatError` for `.doc` and any other unrecognized extension, not just falling through to a blind `.decode("utf-8")`), and that exception is already caught and shown via `st.error` in `app.py`'s normal upload try/except. Same lesson as the entry above, sharper: if a Streamlit widget constraint (`type=`, `max_chars=`, validators, etc.) can be violated by data arriving outside the browser's own UI gating (drag-and-drop, `AppTest.set_value`, a stale client), don't trust framework-level rejection to be catchable — validate in application code where you control the exception flow.

## A Pylance "import could not be resolved" warning is a local-env problem, not a code problem

`services/extract.py` originally imported `pytesseract`/`PIL` lazily, inside `_ocr_pdf()`, on purpose — it avoids loading heavy OCR libraries at app startup when most uploads never need OCR. An attempt to silence a Pylance `reportMissingImports` warning by moving the import to module level (wrapped in `try/except ImportError` → `pytesseract = None`) didn't fix the warning — Pylance resolves imports from the configured interpreter's installed packages regardless of where in the file the `import` statement sits, so the only real fix was `pip install -r requirements.txt` into the interpreter the editor actually points to.

The module-level version was also a functional regression, not just a no-op: it broke `tests/test_extract.py`'s OCR mocks (`monkeypatch.setitem(sys.modules, "pytesseract", fake)` only affects imports that happen *after* the monkeypatch runs; a module-level import already bound `services.extract.pytesseract` once, at first import, before any test's monkeypatch could apply) and collapsed the precise `TesseractNotFoundError`/`TesseractError` handling into a catch-all `except Exception`. Reverted back to the lazy, function-scoped import.

**Rule**: an IDE/linter warning about an import is almost always about the local environment (wrong/incomplete interpreter), not the code's import style. Don't restructure working import patterns to chase it — fix the environment instead, and re-run the test suite before assuming a "harmless" import refactor is actually harmless.
