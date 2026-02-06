# Terminal Checklist — Zero → Published GitHub Repo

## 0) Prereqs

- Install Poetry (macOS):
  - Homebrew: `brew install poetry`
  - pipx: `brew install pipx && pipx install poetry`
  - Docs: https://python-poetry.org/docs/
- Install PyPy 3 (macOS options):
  - `brew install pypy3` (Homebrew)
  - or download from https://www.pypy.org/

## 1) Create project (already scaffolded in this folder)

If starting from scratch elsewhere:

```bash
mkdir ph_ai_tracker && cd ph_ai_tracker
poetry init
mkdir -p src/ph_ai_tracker tests/unit tests/integration tests/e2e tests/fixtures
```

## 2) Point Poetry to PyPy 3

Find your PyPy path:

```bash
which pypy3
pypy3 --version
```

Then tell Poetry to use it (THIS is the command you asked for):

```bash
poetry env use /absolute/path/to/pypy3
```

Tip (optional): keep the venv in-project:

```bash
poetry config virtualenvs.in-project true
```

## 3) Install dependencies

```bash
poetry install
```

## 4) Run tests

```bash
poetry run pytest
```

## 5) Example: print results as easy-to-read JSON

```bash
poetry run python -m ph_ai_tracker --strategy scraper --search AI --limit 10
```

## 5b) Example: API strategy (requires token)

```bash
export PRODUCTHUNT_TOKEN="<your_token>"
poetry run python -m ph_ai_tracker --strategy api --search AI --limit 10
```

Alternative: store it in a local `.env` file (ignored by git) and load it into your shell:

```bash
cp .env.example .env
# edit .env and set PRODUCTHUNT_TOKEN=...
set -a
source .env
set +a
poetry run python -m ph_ai_tracker --strategy api --search AI --limit 10
```

## 6) Build distributables

```bash
poetry build
ls -lah dist/
```

## 7) Initialize git + push to GitHub

```bash
git init
git add -A
git commit -m "Initial commit: ph_ai_tracker"

# Create a new GitHub repo in the UI, then:
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```
