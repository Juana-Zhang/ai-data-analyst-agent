# AI Data Analyst Workbench

A SQL-grounded AI analyst workbench for non-technical stakeholders.

This project demonstrates how AI can support repetitive, structured analytics work for cross-functional teams. Stakeholders often need SQL-based data pulls, KPI checks, recurring summaries, and report-ready outputs, but they may not write SQL themselves. The analyst can pre-design trusted data extraction logic and analysis frameworks, then use an AI-guided interface to help stakeholders access those workflows through natural language.

The public demo uses one synthetic sample domain dataset to illustrate the pattern. The same approach can be adapted to other domains by replacing the schema metadata, metric definitions, and workflow library.

## Why This Project

Many stakeholder requests are structured or repetitive, even when they are asked in natural language. A general chatbot can be flexible, but pure LLM-to-SQL can also create unsupported logic, reference unavailable fields, or expose sensitive data boundaries.

This prototype uses a governed workflow pattern:

```text
Stakeholder question
-> analyst-defined SQL and metric framework
-> workflow library
-> AI routing and clarification
-> approved DuckDB execution
-> SQL evidence + executive report
```

The AI does not freely query data or invent metrics. It helps clarify intent, suggest analysis paths, and select trusted workflows. DuckDB performs the actual computation using approved SQL.

## Current Features

- Streamlit front end for non-technical users
- DuckDB analytics engine over CSV-backed data
- Rule-based Mode for deterministic workflow routing
- Guided AI Mode for Gemini-powered workflow selection, analysis guidance, and clarification
- Gemini interpreter for evidence-grounded result explanation after approved SQL runs
- Proposed new analysis mode for feasible questions outside the trusted workflow library
- Safe fallback when Gemini is unavailable
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
- analysis mode decision
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

## Build Approach

| Step | What Happens | Why It Matters |
| --- | --- | --- |
| 1 | Use one sample business domain dataset | Demonstrates the pattern without exposing private company data |
| 2 | Inspect schema and metric possibilities | Defines what the system can answer safely |
| 3 | Pre-design reusable analysis frameworks | Converts repetitive SQL and reporting work into reusable workflows |
| 4 | Add AI routing and clarification | Helps stakeholders ask better questions and find the right workflow |
| 5 | Execute only approved SQL | Keeps computation reproducible and reviewable |
| 6 | Return evidence and reports | Gives users SQL, interpretation, limitations, next steps, and downloadable output |

## Analysis Modes

| Mode | Best For | What It Does | Control |
| --- | --- | --- | --- |
| Rule-based Mode | Clear, repetitive business questions | Routes directly to predefined SQL workflows | Fully deterministic and reproducible |
| Guided AI Mode | Vague questions, new stakeholders, or exploratory analysis needs | Uses Gemini to clarify intent, suggest analysis paths, or select workflows | Constrained by schema metadata, workflow library, and approved SQL execution |

## Design Guardrails

| Risk | Guardrail |
| --- | --- |
| Free-form LLM-to-SQL | SQL execution is limited to approved workflows |
| Unsupported fields or hallucinated logic | AI responses are grounded in available schema metadata and workflow coverage |
| Unreviewed new analysis | New analyses can be proposed, but untrusted SQL is not automatically executed |
| Black-box answers | Completed analyses expose SQL evidence, data context, limitations, and next steps |
| Private data or key exposure | The public demo uses synthetic sample data; real data and API keys stay outside the repo |

## Sample Domain Workflows

The current demo includes a workflow library for one sample business domain:

- baseline KPI overview
- dimension-level risk comparison
- channel or platform performance
- payment model comparison
- pricing or value segmentation
- lead-time behavior
- high-risk segment detection
- raw data preview

These workflows are examples of how an analyst can encode repeatable business logic. A different company or domain would replace this library with its own metric definitions and SQL frameworks.

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
- The synthetic sample keeps the same schema shape as the local demo dataset, but does not contain real records.

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

## Portfolio Positioning

This is not a universal data chatbot. It is a configurable, SQL-grounded analyst workbench that demonstrates how structured analytics work can be productized for non-technical stakeholders. The project highlights product thinking, SQL framework design, AI workflow design with guardrails, local analytics with DuckDB, and executive reporting UX.

## Integration Preview

The current app runs as a Streamlit prototype on a local CSV file. The sidebar includes an integration preview showing how the same design could later connect to:

- company databases such as PostgreSQL, Snowflake, BigQuery, or Redshift
- an API endpoint such as `POST /analyze`
- Slack or Teams assistant workflows

These integrations are shown as product and architecture previews only. The public demo does not connect to private company systems.

## Limitations

- The current workflow library is designed around one sample domain dataset.
- The analysis is descriptive and does not prove causality.
- The app does not yet generate new SQL freely from arbitrary user questions.
- HTML reporting is implemented before PDF export for simplicity and reliability.

## Future Work

- Add more domain-specific workflows
- Add clarification questions for ambiguous requests
- Add richer statistical tests and model diagnostics
- Add PDF export
- Split the single-file prototype into modules for production maintainability
