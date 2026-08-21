# brandkit

Single-function AWS Lambda that takes a website URL and extracts:

- **Social links** — Facebook, Instagram, Twitter/X, LinkedIn, YouTube, TikTok, Pinterest, GitHub, WhatsApp, Telegram, Discord, and more
- **Logo** — best-effort guess based on `<img>`/`<svg>` heuristics (alt text, class/id hints, header placement)
- **Favicon** — largest declared icon, falling back to `/favicon.ico`
- **Color palette** — most-frequent colors pulled from inline styles, `<style>` blocks, and linked stylesheets, plus `<meta name="theme-color">`
- **Fonts** — `font-family` declarations ranked by frequency, plus any Google Fonts links
- **Metadata** — title, description, site name, OG image

Fetching is static (requests + BeautifulSoup) — no headless browser, so it won't see content that's rendered client-side by JS.

## Project layout

```
brandkit/
  src/
    handler.py           # Lambda entry point
    requirements.txt      # must live under src/ so `sam build` bundles it
    extractor/
      __init__.py         # orchestrates all extractors
      fetcher.py           # HTTP fetch helpers
      social.py            # social media link extraction
      logo.py               # logo + favicon extraction
      colors.py             # color palette extraction
      fonts.py               # font/typography extraction
      metadata.py             # title/description/OG metadata
      styles.py                 # shared CSS-gathering logic
  template.yaml           # AWS SAM deployment template
  local_test.py           # run extraction locally, no AWS needed
```

## Run locally

### Option A — quick script, no Docker/AWS needed

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
python local_test.py https://stripe.com
```

### Option B — simulate the real Lambda + API Gateway (via SAM CLI)

Requires [Docker](https://www.docker.com/) or Finch running, plus the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).

```bash
sam build
sam local start-api
```

Then in another terminal:

```bash
curl "http://127.0.0.1:3000/brandkit?url=https://stripe.com"
```

## Deploy to AWS Lambda (via SAM)

Requires the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) and configured AWS credentials.

```bash
sam build
sam deploy --guided
```

This provisions:
- The Lambda function (Python 3.12, 512 MB, 20s timeout)
- A public **Function URL** (no auth) for direct HTTP access
- An **HTTP API** route at `/brandkit` (GET and POST)

After deploy, SAM prints both endpoints in the Outputs section.

## API usage

**GET** (query param):
```
GET /brandkit?url=https://stripe.com
```

**POST** (JSON body):
```bash
curl -X POST https://<your-endpoint>/brandkit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://stripe.com"}'
```

**Direct Lambda invoke** (no API Gateway):
```bash
aws lambda invoke --function-name <name> \
  --payload '{"url": "https://stripe.com"}' out.json
```

### Response shape

```json
{
  "url": "https://stripe.com/",
  "metadata": {
    "title": "Stripe | Financial Infrastructure to Grow Your Revenue",
    "description": "...",
    "site_name": "Stripe",
    "og_image": "https://stripe.com/img/og.png"
  },
  "logo": "https://stripe.com/img/logo.svg",
  "favicon": "https://stripe.com/favicon.ico",
  "social_links": {
    "twitter": "https://twitter.com/stripe",
    "linkedin": "https://linkedin.com/company/stripe",
    "youtube": "https://youtube.com/stripe"
  },
  "colors": ["#635bff", "#0a2540", "#ffffff"],
  "fonts": {
    "families": ["Inter", "SF Pro Text"],
    "google_fonts": []
  }
}
```

On failure: `{"error": "..."}` with a 4xx/5xx status.

## Notes / limitations

- Static HTML only — sites that render logo/nav via client-side JS (heavy SPAs) may return partial results. Swap in a headless-browser fetch later if needed without touching the extractor modules.
- Each linked stylesheet fetch is capped (5 stylesheets, 300KB each) to keep cold-start and execution time bounded within the Lambda timeout.
- Logo/color/font extraction are heuristic best-effort, not guaranteed exact matches to a brand's official kit.
# brandkit-extractor
