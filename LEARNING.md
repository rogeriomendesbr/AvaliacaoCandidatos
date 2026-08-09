# LEARNING.md

Historical lessons for this repo — non-obvious constraints, rejected approaches, and why behind decisions. Referenced from [CLAUDE.md](CLAUDE.md) and [HARNESS.md](HARNESS.md). Append new entries at the bottom; don't rewrite history, just note when something in an old entry stopped being true.

## Merge conflicts must be verified, not just resolved in the editor

Commit `276e830` ("Merge conflits") was pushed to `main` with unresolved `<<<<<<< HEAD` / `=======` / `>>>>>>>` markers still inside `services/llm.py`, breaking `build_prompt` with a `SyntaxError`. The working tree looked fine because the fix existed uncommitted on disk — but HEAD (and origin/main) was broken.

**Rule**: after resolving a merge, `git diff HEAD` the affected files and re-run the test suite *before* committing. A file with no visible markers in your editor can still have committed markers in a prior commit.

## Streamlit's `file_uploader(type=[...])` is enforced server-side

As of streamlit 1.58.0, uploading a file whose extension isn't in `type=[...]` raises `StreamlitAPIException` during deserialization, before any app code runs. This means `services/extract.py`'s `UnsupportedFormatError` branch for `.doc` files is unreachable through the real widget — it can only be exercised by calling `extract_resume()` directly, or by monkeypatching `extract_resume` in an `AppTest`. Don't try to trigger it via `at.file_uploader[0].set_value(("x.doc", ...))`; it will blow up before app code sees it.

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
