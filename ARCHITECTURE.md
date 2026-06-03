# Architecture

## Product Goal

The app helps non-technical stakeholders retrieve trusted business insights without writing SQL.

The design principle is:

```text
LLM supervises the analysis path.
DuckDB computes the evidence.
The app exposes the SQL, data context, and limitations.
```

## Flow

```text
User question
    |
    v
Supervisor layer
    - Gemini supervisor, if configured
    - deterministic fallback, always available
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
    - supervisor decision
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
Supervisor action selection
    |
    v
Workflow execution or guidance response
    |
    v
SQL-backed evidence package
    |
    v
Gemini interpreter, optional
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

### Supervisor

The supervisor decides the next best action:

- `run_workflow`: the question maps clearly to a trusted SQL workflow
- `suggest_analysis_plan`: the user wants help deciding how to analyze the dataset
- `ask_clarification`: the user asks broad advice but has not specified a target
- `propose_new_analysis`: the question is feasible from available fields but is not yet part of the trusted workflow library
- `unsupported`: the question cannot be answered from the current dataset or workflow coverage

Modes:

- `Deterministic supervisor`: local keyword-based routing
- `Gemini supervisor`: LLM-based action selection over the same trusted workflow library

If Gemini fails, the app falls back safely to deterministic guidance and routing.

### Interpreter

When a trusted SQL workflow runs, the optional Gemini interpreter receives:

- the original user question
- the selected workflow metadata
- the SQL that was executed
- the DuckDB result preview
- data context and fields used

It generates a plain-English interpretation and follow-up suggestions grounded only in the result. If Gemini is unavailable, the app falls back to deterministic interpretation templates.

### Workflow Library

Each workflow contains:

- title
- business description
- required columns
- SQL

The app only executes predefined SQL workflows. This keeps the prototype reproducible and easier to validate.

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
- supervisor decision
- selected workflow
- data context
- SQL evidence
- result table
- business interpretation
- limitations
- next steps
- suggested questions

## Why This Design

This design avoids the biggest risk of general-purpose data chatbots: unsupported or hallucinated answers.

Instead of allowing the LLM to freely generate arbitrary SQL, the app constrains SQL execution to a trusted workflow library. For vague user questions, the LLM can still provide useful analysis guidance without pretending to have computed evidence.

For new but feasible analysis requests, Gemini can propose a draft analysis and draft SQL using available fields. The app marks this as proposed only and does not execute the draft SQL automatically.
