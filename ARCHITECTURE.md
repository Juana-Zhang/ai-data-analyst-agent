# Architecture

## Product Goal

The app helps non-technical stakeholders retrieve trusted business insights without writing SQL. It demonstrates a pattern where analysts define reusable metric logic and SQL frameworks first, then AI helps users route, clarify, and consume those workflows through a simple interface.

The design principle is:

```text
Analyst defines the governed analysis framework.
AI helps route and clarify stakeholder questions.
DuckDB computes the evidence.
The app exposes the SQL, data context, and limitations.
```

## Flow

```text
User question
    |
    v
Analysis mode layer
    - Rule-based Mode, always available
    - Guided AI Mode, if Gemini is configured
    - actions: run workflow, suggest analysis plan, ask clarification, propose new analysis, unsupported
    |
    v
Workflow library
    - trusted SQL frameworks
    - required column metadata
    - supported topic coverage
    |
    v
DuckDB execution
    - CSV-backed query
    - private data.csv locally, synthetic sample_data.csv in public demo
    - reproducible result table
    - only runs when action is run_workflow
    |
    v
Evidence package
    - question
    - analysis mode decision
    - selected workflow
    - SQL
    - result dataframe
    - data context
    - interpretation
    - limitations
    - recommended next steps
    - suggested questions
    |
    v
Streamlit UI and downloadable HTML report
```

## Integration Preview

The current implementation runs inside Streamlit, but the core pattern is API-ready:

```text
POST /analyze
    |
    v
Analysis mode action selection
    |
    v
Workflow execution or guidance response
    |
    v
SQL-backed evidence package
    |
    v
Guided AI interpreter, optional
    - explains only the SQL result
    - recommends follow-up questions
    - falls back to deterministic interpretation
    |
    v
JSON response and optional report link
```

Potential production integrations:

- company database connectors for PostgreSQL, Snowflake, BigQuery, or Redshift
- API endpoint for internal tools or BI portals
- Slack or Teams assistant interface
- secrets manager for credential handling
- role-based access control before query execution

The public demo does not connect to private systems and uses synthetic sample data. The integration preview shows how the design could be extended in an enterprise environment.

## Main Components

### Analysis Modes

The app supports two modes for routing stakeholder questions:

| Mode | Best For | What It Does | Control |
| --- | --- | --- | --- |
| Rule-based Mode | Clear, repetitive business questions | Routes directly to predefined SQL workflows | Fully deterministic and reproducible |
| Guided AI Mode | Vague questions, new stakeholders, or exploratory analysis needs | Uses Gemini to clarify intent, suggest analysis paths, or select workflows | Constrained by schema metadata, workflow library, and approved SQL execution |

Both modes return one of the same structured actions:

- `run_workflow`: the question maps clearly to a trusted SQL workflow
- `suggest_analysis_plan`: the user wants help deciding how to analyze the dataset
- `ask_clarification`: the user asks broad advice but has not specified a target
- `propose_new_analysis`: the question is feasible from available fields but is not yet part of the trusted workflow library
- `unsupported`: the question cannot be answered from the current dataset or workflow coverage

If Gemini fails, Guided AI Mode falls back safely to Rule-based Mode guidance and routing.

### Interpreter

When a trusted SQL workflow runs, the optional Guided AI interpreter receives:

- the original user question
- the selected workflow metadata
- the SQL that was executed
- the DuckDB result preview
- data context and fields used

It generates a plain-English interpretation and follow-up suggestions grounded only in the result. If Gemini is unavailable, the app falls back to rule-based interpretation templates.

### Analyst-Defined Workflow Library

Each workflow contains:

- title
- business description
- required columns
- SQL

The app only executes predefined SQL workflows. This keeps the prototype reproducible and easier to validate. The current public demo uses one sample business domain dataset, but a different domain can replace this library with its own schema, metrics, and SQL frameworks.

### Data Quality Layer

The Dataset Profile tab includes:

- schema inspection
- duplicate row checks
- missing value checks
- negative ADR check
- date consistency checks

### Reporting Layer

Every completed SQL analysis can produce an HTML report with:

- user question
- analysis mode decision
- selected workflow
- data context
- SQL evidence
- result table
- business interpretation
- limitations
- next steps
- suggested questions

### Security And Secrets

The prototype separates public demo assets from private runtime configuration:

- `sample_data.csv` is synthetic and can be deployed publicly.
- `data.csv` is treated as local/private data and is excluded from git.
- Gemini credentials are read from Streamlit secrets or environment variables.
- `.streamlit/secrets.toml` is excluded from git.
- `.streamlit/secrets.toml.example` is committed only as a setup template.

The AI layer is also constrained at runtime:

- It receives workflow metadata and schema context, not unrestricted database access.
- It must return a structured action rather than arbitrary executable code.
- Unknown workflow keys are rejected.
- Non-workflow actions do not execute SQL.
- Proposed new analyses are shown for review only and are not automatically executed.

## Why This Design

This design avoids the biggest risk of general-purpose data chatbots: unsupported or hallucinated answers.

Instead of allowing the LLM to freely generate arbitrary SQL, the app constrains SQL execution to a trusted workflow library. For vague user questions, Guided AI Mode can still provide useful analysis guidance without pretending to have computed evidence.

For new but feasible analysis requests, Guided AI Mode can propose a draft analysis and draft SQL using available fields. The app marks this as proposed only and does not execute the draft SQL automatically.
