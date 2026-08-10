# LEARNING.md

Historical lessons for this repo — non-obvious constraints, rejected approaches, and why behind decisions. Referenced from [CLAUDE.md](CLAUDE.md) and [HARNESS.md](HARNESS.md). Append new entries at the bottom; don't rewrite history, just note when something in an old entry stopped being true.

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

## `st.error()` immediately followed by `st.rerun()` in the same run is invisible to the user

When adding the disable/hourglass upload state machine, the upload error branch called `st.error(...)` and then, in a `finally` block right after, unconditionally called `st.rerun()` (needed to reset `pending_upload`/`uploader_key` back to idle). Streamlit replaces the entire page's element tree on every run; a run that calls `st.rerun()` right after `st.error(...)` never gives the browser a chance to actually display that error before the next run wipes it — the message is emitted but the page is already gone before the user can see it. Result: `.doc` uploads (and any other upload error) silently failed with the widget just resetting, no visible feedback at all.

This bug was **not caught by the existing `AppTest`-based tests** (`test_upload_doc_file_shows_friendly_error_without_crashing` et al.) even though they assert on `at.error` after the fact — worth treating `AppTest` assertions on transient per-run state with suspicion when a code path deliberately chains multiple internal `st.rerun()` calls; verify what the *actually settled* run contains (e.g. check that a reset/idle indicator like `uploader_key` or `disabled=False` is present in the same tree as the message) rather than trusting that "the assertion passed" proves the message would be visible in a real browser.

**Fix**: never call `st.error()`/`st.success()` etc. immediately before an unconditional `st.rerun()` in the same code path. If a message must survive a mandatory reset-rerun, stash it in `st.session_state` (e.g. `st.session_state.upload_error`) and render+clear it on the *next* run instead — see the `upload_error` pattern in `app.py`'s upload handler.

## The disable/hourglass/deferred-message pattern is now used twice — treat it as the standard for any "click → slow work → result" control

Both the file uploader and the "Analisar candidatos" button follow the same three-phase shape now: (1) on trigger, stash whatever's needed into `st.session_state` and `st.rerun()` immediately, *before* doing any slow work — this is the only way to get the widget to render `disabled=True` on the next pass, since Streamlit can't retroactively disable a widget already rendered in the run that triggered it; (2) on the next run, render the widget disabled, inject a page-wide `cursor: wait` style, do the slow work, and store the outcome (never call `st.error`/`st.success` directly here — see the entry above) in session_state, then `st.rerun()` again; (3) the following (settled) run renders the widget enabled and displays+clears the stored outcome.

Verified both instances directly (not just via passing `AppTest` assertions) by inspecting the settled run's `session_state` and widget `.disabled` property together with the message — see how `app.py`'s upload and analyze-button handlers do it if adding a third instance of this pattern (e.g. another slow action button). Don't shortcut to a single-phase `try/except` + immediate message for anything that both (a) takes long enough that a double-click matters and (b) needs to show a `disabled=`/cursor cue — it silently doesn't work.

## A conditionally-rendered `st.markdown`/`st.error`/any element shifts everything below it — even if it's visually empty

Adding the busy-cursor CSS as `if busy: st.markdown("<style>...</style>", unsafe_allow_html=True)` caused the *entire page* to shift up/down whenever `busy` toggled — logo, title, all three columns, the button, everything below it. Cause: every `st.*` call gets wrapped in its own element-container with vertical margin in Streamlit's layout flow, regardless of whether the element renders any visible content. A `<style>` tag has zero visible size but its *container* still occupies space, so inserting/removing it conditionally inserts/removes that space, and everything after it in the page shifts to compensate. This is easy to miss because the element itself is invisible — the bug reads as "unrelated things move around" rather than "this specific element appeared."

Same root cause as the `col2` height issue fixed just before this (dynamic content changing an element's footprint) but worse in scope: that one only affected one column's height, this one affected the *entire page* because the conditional element was the first thing rendered, before the logo/title row.

**Fix**: never gate an element's *presence* on state — gate its *content*. The cursor-override CSS is now folded into the single, always-rendered `st.markdown(f"<style>{load_css()}\n{cursor_rule}</style>", ...)` call at the top of `app.py`, where `cursor_rule` is `""` when not busy. One element, always present, only its inner text changes. General rule: if a UI element needs to conditionally show/hide, prefer varying its content/value over wrapping the whole `st.*` call in `if condition:` — the latter is a layout-shift risk anywhere on the page, not just near dynamic content.
