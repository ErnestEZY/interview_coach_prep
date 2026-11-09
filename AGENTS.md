# AGENTS.md

Read this before your first change. It records what the code does not say for
itself: how the test gate is run, the one rule that decides whether fixtures
work, and the decisions that were argued out and should not be re-opened
without new evidence.

## What this is

ICP (Interview Coach Prep): a FastAPI backend that serves a Vue frontend from
the same process, with MongoDB behind it. The AI feedback path sits behind a
provider router. The Android and Windows builds under `apps/` and `src-tauri/`
are artefacts of this codebase, not a second implementation.

- `backend/main.py` mounts the app and serves `frontend/` statically.
- `backend/controllers/*_routes.py` are the routers; `backend/services/` holds
  behaviour; `backend/core/` holds config, the database handle and security.
- `frontend/static/pages/*.html` are the pages (hashed names, Vue via CDN, no
  bundler). `frontend/static/js/resume-text.js` rebuilds headings, lists and
  paragraphs from extracted resume text.
- `dev_tools/` holds operator scripts, not application code.

Python 3.11 in CI. `backend/requirements.txt` is the single dependency list.

## Run it

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

The E2E suite defaults to `http://127.0.0.1:8001` (`E2E_BASE_URL`).
`start.ps1` and `start.sh` serve port **8000** — that is a different origin from
the one the tests use, so either start uvicorn on 8001 or set `E2E_BASE_URL`.

`.env` is untracked; `.env.example` lists the keys. Configuration is read in
`backend/core/config.py`; the database name is `ICP_DB_NAME`, else `DB_NAME`,
else `interview_coach`.

## The test gate

Everything below must be green before a push. CI enforces the first three plus
the lint check; the required check is the single **Test Gate** job in
`.github/workflows/build_apps.yml`.

```powershell
# Hermetic: unit, integration, functional, security, ui, smoke. No browser, no network.
.\venv\Scripts\python.exe -m pytest

# Browser: needs the backend on 127.0.0.1:8001 and Playwright chromium. ~10 min.
.\venv\Scripts\python.exe -m pytest tests/e2e/ -m "not vrt" --browser chromium

# Live stack: starts its own uvicorn on a free port against ICP_DB_NAME=icp_system_test.
.\venv\Scripts\python.exe -m pytest tests/system/

# Visual regression: local only, never in CI (see Decisions).
.\venv\Scripts\python.exe -m pytest tests/e2e/test_visual_regression.py

# Blocking lint: crash-class rules only. Full ruff is advisory.
.\venv\Scripts\python.exe -m ruff check backend/ tests/ --select E9,F63,F7,F82
```

`pytest.ini` ignores `tests/e2e` by default, so the plain `pytest` run stays
hermetic. Anything that needs a browser belongs in `tests/e2e/`; anything that
needs a live server belongs in `tests/system/`. A test that needs neither goes
in `tests/` so it runs on every push.

## The one rule that decides whether fixtures work

Fixtures that seed rows connect with pymongo using `MONGO_URI` and `DB_NAME`
from `backend/core/config.py` — the same values the **running app** uses. If the
pytest process and the app disagree about the database, seeding writes to a
database nobody reads and the suites skip or time out with no useful message.
CI sets both at job level for exactly this reason; do not move them to step
scope.

Seeded rows carry a `test_seed` marker. The fixtures delete what they insert,
and a session-start sweep in `tests/e2e/conftest.py` removes anything a killed
run left behind — `insert_many` writes until it raises, so a crash partway
through leaves rows whose ids were never returned. Keep the marker on any new
seeded row.

## Traps that have already cost time

- `resumes.resume_id` and `interviews.session_id` are uniquely indexed, and a
  unique index permits only one `null`. Seeded rows therefore need unique
  values, not a shared default.
- The admin list sorts server-side (`?sort=newest`). Do not sort it again in the
  client, and do not assert on document order that the API did not promise.
- Do not remove or re-create nodes Vue is managing. Put the page into a state
  through the component instance (the `drive_vue` fixture) or through the app's
  own handlers.
- Multi-root Vue templates make `$el` useless for querying. Use
  `document.querySelector` on stable ids.
- Admin pages gate on `localStorage.token` read at parse time, so authentication
  must be injected with a context init script before any page script runs.
- A line ending in a full stop is a paragraph boundary in `resume-text.js`.
  Fixtures written to exercise paragraph merging have to wrap mid-sentence.

## Decisions

**Visual regression stays local.** The app links no text webfont, so a page is
rasterised with the host's system font stack and the same screenshot differs
between Windows and the Ubuntu runner. CI therefore runs `-m "not vrt"`. The
baselines are still committed, because a reviewable image diff is worth having.

**Cross-browser runs monthly and on demand, one database per engine.** The
matrix legs run in parallel against rows the tests assert on, so each leg sets
its own `DB_NAME` (`icp_e2e_test_<engine>`). A shared name lets one engine's
sweep delete another's seeds.

**Blocking CI is deliberately narrow:** crash-class lint plus the suites above.
Style stays advisory so the report exists without gating a push.

## Conventions

- Commit subject: `type: imperative summary` (fix, feat, test, ci, docs). The
  body explains why — what failed, what it cost — rather than restating the
  diff.
- Comments should record the reason a reader would otherwise have to rediscover,
  particularly where a workaround exists and looks arbitrary otherwise.
- Tests state the invariant in the assertion message, so a failure says what
  broke without opening the file.
