# ph_ai_tracker

A small Python library that finds trending AI products on Product Hunt.

- Primary: Product Hunt GraphQL API v2
- Secondary: Web scraping fallback (BeautifulSoup) for when the API is unavailable / rate-limited

## Install (dev)

```bash
poetry install
```

## Install (PyPI)

```bash
pip install ph-ai-tracker
```

## Quickstart

```python
from ph_ai_tracker import AIProductTracker

tracker = AIProductTracker(
    api_token="YOUR_PRODUCTHUNT_TOKEN",  # optional
    strategy="auto",                    # api | scraper | auto
)

result = tracker.get_products(search_term="AI", limit=20)
print(result.to_pretty_json())
```

Or from the terminal (prints pretty JSON):

```bash
poetry run python -m ph_ai_tracker --strategy scraper --search AI --limit 10
```

After installing from PyPI, you can also run:

```bash
ph-ai-tracker --strategy scraper --search AI --limit 10
```

## Trending behavior

- `--strategy api` defaults to Product Hunt's `RANKING` order.
- The API client first attempts the `artificial-intelligence` topic; if the schema/topic query fails, it falls back to global posts and applies a client-side filter.

## Product Hunt API token

Do **not** hardcode tokens in code or commit them to git.

Set your token as an environment variable:

```bash
export PRODUCTHUNT_TOKEN="<your_token>"
poetry run python -m ph_ai_tracker --strategy api --search AI --limit 10
```

## Notes

- This project is intended to run well on PyPy 3.
- All tests are offline and use mocks/fixtures (no real network).
