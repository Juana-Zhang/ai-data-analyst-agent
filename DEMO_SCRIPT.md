# Demo Script

## Opening

This is an AI Data Analyst Workbench designed for non-technical stakeholders. The goal is to let business users ask questions in natural language, while the system returns SQL-backed, reproducible evidence.

This demo uses one synthetic sample domain dataset to show the pattern. The same architecture can be adapted to another domain by replacing the schema metadata, metric definitions, and workflow library.

## Step 1: Show The Ask Data Page

Select `Guided AI Mode` in the sidebar.

Ask:

```text
I don't know how to analyze this dataset. Where should I start?
```

Point out:

- Guided AI Mode helps vague or exploratory users clarify where to start
- suggested questions are clickable, so stakeholders do not need to write SQL
- AI guidance is constrained by the available schema and workflow library

## Step 2: Run A Trusted Workflow

Ask:

```text
What is the overall cancellation rate and booking volume?
```

Point out:

- the app selects a trusted workflow
- the SQL evidence is visible
- DuckDB computes the actual result
- the app returns KPI cards, interpretation, and next steps

## Step 3: Show Rule-Based Mode

Switch to `Rule-based Mode`.

Point out:

- this mode is best for clear, repetitive business questions
- it does not require an LLM
- it routes to stable predefined SQL workflows
- it is useful when teams need reproducible, governed reporting

## Step 4: Show Dataset Profile

Open `Dataset Profile`.

Point out:

- schema inspection
- data quality checks
- missing value summary
- sample rows

## Step 5: Show Workflow Library

Open `Workflow Library`.

Point out:

- every workflow has required columns
- this makes the app coverage-aware
- future datasets can use a different workflow library

## Step 6: Show Executive Brief And Report

Run an analysis, then open `Executive Brief`.

Click `Download HTML Report`.

Point out:

- the report includes the user question
- analysis mode decision
- SQL evidence
- result table
- interpretation
- limitations
- recommended next steps

Also point out:

- the build approach starts with analyst-defined SQL and metric frameworks
- AI is used for routing, clarification, and acceleration, not unrestricted querying
- private data and API keys stay outside the public repo

## Closing

This project is not just a chatbot. It is a governed, SQL-grounded analytics workflow that productizes repetitive stakeholder data requests while using AI safely for guidance and acceleration.
