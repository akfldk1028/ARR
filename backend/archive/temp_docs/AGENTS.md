# Repository Guidelines

## Project Structure & Module Organization
`backend/` holds project settings (`settings.py`, `urls.py`, ASGI/WSGI). Domain apps sit beside it (`agents/`, `authz/`, `conversations/`, `billing/`, `tasks/`, `registry/`, `rules/`, `adminui/`, `events/`), each keeping the standard Django layout with `migrations/`, `models.py`, `views.py`, and inline `tests.py`. Shared UI assets live in `templates/`; agent configuration helpers live in `config/`. Use `cookbook/` and `gemini/` as experimental references only, and reset the checked-in `db.sqlite3` before committing.

## Build, Test & Development Commands
Create or refresh the virtual environment with `python -m venv .venv` and `.\.venv\Scripts\activate`. Install runtime deps via `pip install django==5.2.6 channels websockets python-dotenv`, adding cookbook extras only when you run those samples. Apply schema updates with `python manage.py makemigrations` and `python manage.py migrate`. Start the stack using `python manage.py runserver 0.0.0.0:8000`, then smoke-test websockets through `python test_websocket.py` and voice streaming with `python run_voice_server.py`.

## Coding Style & Naming Conventions
Follow PEP 8, 4-space indentation, and grouped imports. Use `snake_case` for modules, functions, and JSON keys; keep `PascalCase` for Django models and serializers, and `SCREAMING_SNAKE_CASE` for configuration constants. Docstrings should match the concise tone in `core/models.py`. No formatter is enforced, but aligning with `black` defaults keeps diffs minimal. Route new environment lookups through helpers in `config/` rather than scattering `os.getenv`.

## Testing Guidelines
Run `python manage.py test <app_label>` for unit coverage and place new tests alongside each app's `tests.py`. Exercise async integrations manually: `python test_websocket.py` hits `/ws/gemini/`, `python test_tts.py` validates audio playback, and `python test_tts_simple.py` offers a quick regression. Name cases `test_<feature>_<expectation>` and document bespoke fixtures in the test module to keep scenarios reproducible.

## Commit & Pull Request Guidelines
Commits here are terse, hyphenated summaries (see `git log`); keep the subject under ~60 characters and add detail below when needed, mixing English and Korean as the history shows. In pull requests, describe scope, list verification steps, attach screenshots for admin UI touches, and flag edits to `.env` or `config/*.py`. Update `ARCHITECTURE.md` or linked docs whenever websocket contracts or cross-agent flows shift.
