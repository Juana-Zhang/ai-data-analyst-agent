# AI Data Analyst Workbench

A SQL-grounded AI analyst workbench for non-technical stakeholders.

This project lets users ask business questions in natural language, routes clear questions to trusted analysis workflows, runs reproducible DuckDB queries on a hotel booking dataset, and returns KPI summaries, charts, business interpretations, and downloadable HTML reports for completed analyses.

## Why This Project

Many business users need data answers but do not write SQL. A general chatbot can be flexible, but it can also produce unsupported answers. This prototype uses a governed workflow pattern:

```text
User question
-> Supervisor chooses a trusted workflow
-> DuckDB runs SQL against local data
-> App returns evidence, interpretation, and report
```

The LLM does not directly invent data. It only helps select from supported workflows. DuckDB performs the actual computation.

## Current Features

- Streamlit front end for non-technical users
- DuckDB analytics engine over CSV-backed data
- Gemini supervisor mode for workflow selection, analysis guidance, and clarification
- Gemini interpreter mode for evidence-grounded result explanation
- Proposed new analysis mode for feasible questions outside the trusted workflow library
- Deterministic supervisor fallback when Gemini is unavailable
- Trusted SQL workflow library
- Transparent SQL for every result
- KPI cards, tables, and quick charts
- Dataset schema and data quality checks
- Unsupported question handling
- Guidance for users who do not know where to start
- Draft analysis proposals for new questions, without automatic SQL execution
- One-click downloadable HTML executive report
- Data context and field lineage in each report
- Enterprise integration preview for database, API, and Slack/Teams patterns

## Report Contents

Each downloaded report is generated only after a SQL workflow runs. It includes:

- user question
- supervisor decision
- selected workflow
- data source and DuckDB table reference
- rows analyzed and columns available
- fields used by the selected workflow
- SQL evidence
- result table
- business interpretation
- interpretation source
- limitations
- recommended next steps

## Supported Workflows

- Cancellation overview
- Cancellation risk by city
- Platform performance
- Payment model analysis
- ADR by star rating
- Lead time and cancellation
- High-risk booking segment detection
- Raw data preview

## Tech Stack

- Python
- Streamlit
- DuckDB
- Pandas
- Gemini API via `google-genai`

## Project Docs

- [Architecture](ARCHITECTURE.md)
- [Prompt Design](PROMPT_DESIGN.md)
- [Demo Script](DEMO_SCRIPT.md)

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Data source behavior:

- Local development uses your private `data.csv` when it exists.
- Public demo deployment falls back to the included synthetic `sample_data.csv`.
- The synthetic sample keeps the same schema as the private hotel booking dataset, but does not contain real records.

For local full-data analysis, place the private dataset in the project root:

```text
data.csv
```

Optional Gemini setup:

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then edit `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_api_key_here"
GEMINI_MODEL = "gemini-2.5-flash"
```

Run the app:

```bash
python -m streamlit run app.py
```

## Public Demo Deployment

You can share this project with others by deploying it to Streamlit Community Cloud:

1. Push this repository to GitHub.
2. Make sure `sample_data.csv` is included and `data.csv` is not included.
3. Create a new Streamlit app from the GitHub repository.
4. Set the main file path to `app.py`.
5. Optional: add `GEMINI_API_KEY` and `GEMINI_MODEL` in Streamlit Cloud secrets.

The deployed app will use `sample_data.csv` by default, so recruiters and reviewers can open a public URL without needing your local machine, private dataset, or local API key file.

## Weekly Progress

| Week | Focus | Deliverable |
| --- | --- | --- |
| Week 1 | Streamlit and DuckDB foundation | Chat-style prototype with one fixed SQL query |
| Week 2 | Analyst workbench pattern | Rule-based workflow routing, SQL transparency, KPI tables, charts |
| Week 3 | Analysis quality | Data quality checks, missing-value summaries, high-risk segments, business interpretation |
| Week 4 | AI supervisor layer | Gemini workflow selection with deterministic fallback |
| Week 5 | Executive outputs | Downloadable HTML reports with findings, SQL evidence, limitations, and next steps |
| Week 6 | Portfolio polish | README, architecture docs, setup instructions, and demo script |

## Portfolio Positioning

This is not a universal data chatbot. It is a configurable, SQL-grounded analyst workbench. The current demo uses a hotel booking dataset, but the architecture can support other business domains by replacing the workflow library and metadata layer.

## Integration Preview

The current app runs as a Streamlit prototype on a local CSV file. The sidebar includes an integration preview showing how the same design could later connect to:

- company databases such as PostgreSQL, Snowflake, BigQuery, or Redshift
- an API endpoint such as `POST /analyze`
- Slack or Teams assistant workflows

These integrations are shown as product and architecture previews only. The public demo does not connect to private company systems.

## Limitations

- The current workflow library is designed around the hotel booking dataset.
- The analysis is descriptive and does not prove causality.
- The app does not yet generate new SQL freely from arbitrary user questions.
- HTML reporting is implemented before PDF export for simplicity and reliability.

## Future Work

- Add more domain-specific workflows
- Add clarification questions for ambiguous requests
- Add richer statistical tests and model diagnostics
- Add PDF export
- Split the single-file prototype into modules for production maintainability
