# TodoApp

A small task tracker built with Flask and SQLite, with a GitHub-inspired interface for creating, reviewing, closing, and deleting tasks.

## Features

- Create tasks with a title, deadline, and priority
- View tasks sorted by priority and status
- Highlight overdue pending tasks
- Mark tasks as done or delete them
- Run automated tests locally or in GitHub Actions

## Project Structure

- `app.py` - Flask web application
- `main.py` - CLI entry point
- `services.py` - task validation and sorting logic
- `repository.py` - SQLite persistence layer
- `models.py` - task model
- `templates/index.html` - web UI
- `test_services.py` - unit and integration tests

## Requirements

- Python 3.11 recommended
- `pip` for installing dependencies

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The App

```bash
python3 app.py
```

Then open `http://127.0.0.1:5000`.

## Run Tests

```bash
python3 -m unittest -v
```

## CI

GitHub Actions workflow:

- `.github/workflows/ci.yml`

It runs the test suite on every push and pull request.
