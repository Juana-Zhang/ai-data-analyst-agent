# AI Data Analyst Workbench

A SQL-grounded AI analyst workbench for non-technical stakeholders.

This project lets users ask business questions in natural language, routes those questions to trusted analysis workflows, runs reproducible DuckDB queries on a local hotel booking dataset, and returns KPI summaries, charts, business interpretations, and downloadable HTML reports.

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
- DuckDB local analytics engine
- Gemini supervisor mode for workflow selection
- Deterministic supervisor fallback when Gemini is unavailable
- Trusted SQL workflow library
- Transparent SQL for every result
- KPI cards, tables, and quick charts
- Dataset schema and data quality checks
- Unsupported question handling
- One-click downloadable HTML executive report
- Data context and field lineage in each report

## Report Contents

Each downloaded report includes:

- user question
- supervisor decision
- selected workflow
- data source and DuckDB table reference
- rows analyzed and columns available
- fields used by the selected workflow
- SQL evidence
- result table
- business interpretation
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

Place the dataset in the project root:

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
