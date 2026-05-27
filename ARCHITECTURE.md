# Architecture

## Product Goal

The app helps non-technical stakeholders retrieve trusted business insights without writing SQL.

The design principle is:

```text
LLM selects the workflow.
DuckDB computes the evidence.
The app exposes the SQL and limitations.
```

## Flow

```text
User question
    |
    v
Supervisor layer
    - Gemini supervisor, if configured
    - deterministic fallback, always available
    |
    v
Workflow library
    - trusted SQL frameworks
    - required column metadata
    - supported topic coverage
    |
    v
DuckDB execution
    - local CSV query
    - reproducible result table
    |
    v
Evidence package
    - question
    - supervisor decision
    - selected workflow
    - SQL
    - result dataframe
    - interpretation
    - limitations
    - recommended next steps
    |
    v
Streamlit UI and downloadable HTML report
```

## Main Components

### Supervisor

The supervisor maps the user question to one workflow key.

Modes:

- `Deterministic supervisor`: local keyword-based routing
- `Gemini supervisor`: LLM-based routing over the same trusted workflow library

If Gemini fails, the app falls back safely to deterministic routing.

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

Every successful analysis can produce an HTML report with:

- user question
- supervisor decision
- selected workflow
- SQL evidence
- result table
- business interpretation
- limitations
- next steps

## Why This Design

This design avoids the biggest risk of general-purpose data chatbots: unsupported or hallucinated answers.

Instead of allowing the LLM to freely generate arbitrary SQL, the app constrains it to a trusted workflow library and clearly explains when a question is unsupported.
