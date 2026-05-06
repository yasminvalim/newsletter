# CoreOS Newsletter (POC)

Pull updates from **GitHub**, **GitLab**, and **Jira**, then optionally use **Google Gemini** to write a weekly **Markdown newsletter**.

---

## Quick start

### 1. Install

```bash
cd coreos-newsletter
python3 -m venv .venv
source .venv/bin/activate         
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit **`.env`**: add tokens and IDs for the tools you use (see comments in `.env.example`). You can leave unused sections blank; those sources are skipped.

**Gemini auth (pick one):**

- **API key:** set **`GOOGLE_API_KEY`** from [Google AI Studio](https://aistudio.google.com/app/apikey).
- **Vertex AI + ADC (no API key):** set **`GOOGLE_CLOUD_PROJECT`** (and optionally **`GOOGLE_CLOUD_LOCATION`**, default `us-central1`). Install [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), run **`gcloud auth application-default login`**, and enable the **Vertex AI API** on that project. The app uses **`GOOGLE_CLOUD_PROJECT`** first when set.

### 3. Run

Always activate the venv first (`source .venv/bin/activate`).

**Option A — everything in one go** (fetch data → Gemini summary → Markdown newsletter):

```bash
PYTHONPATH=src python -m coreos_newsletter all --days 7 --out output
```

**Option B — step by step:**

| Step | Command | Output |
|------|---------|--------|
| Download activity | `PYTHONPATH=src python -m coreos_newsletter fetch --days 7 --out output` | `output/bundle.json` |
| Gemini summary (needs API key **or** Vertex + ADC) | `PYTHONPATH=src python -m coreos_newsletter summarize --out output --bundle output/bundle.json` | `output/gemini_summary.json` |
| Newsletter text | `PYTHONPATH=src python -m coreos_newsletter draft --out output --summary output/gemini_summary.json` | `output/newsletter.md` |

### 4. Read the results

- **`output/bundle.json`** — raw combined data from your APIs  
- **`output/gemini_summary.json`** — structured summary from Gemini  
- **`output/newsletter.md`** — newsletter you can paste into Slack or email  

---
