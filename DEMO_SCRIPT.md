# Demo Script

## Opening

This is an AI Data Analyst Workbench designed for non-technical stakeholders. The goal is to let business users ask questions in natural language, while the system returns SQL-backed, reproducible evidence.

## Step 1: Show The Ask Data Page

Select `Gemini supervisor (optional)` in the sidebar.

Ask:

```text
Can you tell me the overall cancellation rate?
```

Point out:

- Gemini chooses the workflow
- the selected workflow is visible
- the SQL is transparent
- DuckDB computes the actual result
- the app returns KPI cards and an interpretation

## Step 2: Show Unsupported Question Handling

Ask:

```text
What's your advice?
```

Point out:

- the supervisor does not force an answer
- the app explains the question is outside workflow coverage
- this is intentional and prevents unsupported analysis

## Step 3: Show Dataset Profile

Open `Dataset Profile`.

Point out:

- schema inspection
- data quality checks
- missing value summary
- sample rows

## Step 4: Show Workflow Library

Open `Workflow Library`.

Point out:

- every workflow has required columns
- this makes the app coverage-aware
- future datasets can use a different workflow library

## Step 5: Show Executive Report

Run an analysis, then open `Executive Brief`.

Click `Download HTML Report`.

Point out:

- the report includes the user question
- supervisor decision
- SQL evidence
- result table
- interpretation
- limitations
- recommended next steps

## Closing

This project is not just a chatbot. It is a SQL-grounded analyst workflow that uses AI as a supervisor while keeping the actual evidence reproducible and inspectable.
