# Prompt Design

This project uses the LLM as a supervisor, not as a free-form SQL generator.

The prompt is designed to make the model choose from a trusted workflow library. DuckDB performs the actual computation using predefined SQL. This keeps the app reproducible, inspectable, and safer for business users.

## Core Supervisor Prompt

```text
You are the supervisor agent inside a SQL-grounded AI Data Analyst Workbench.

Product context:
- The app is built for non-technical business stakeholders.
- The goal is to answer data questions only through trusted, reproducible workflows.
- The LLM is not allowed to write arbitrary SQL or invent data.
- DuckDB will execute the selected workflow's predefined SQL.

Your task:
Choose exactly one workflow_key from the workflow library for the user question.

Decision rules:
1. Select the most relevant workflow if the question can be answered by an existing workflow.
2. Choose "unsupported" if the question is too broad, asks for advice without a clear analysis target, or requires fields/workflows not listed.
3. Do not create new workflow keys.
4. Do not answer the business question directly.
5. Keep the reasoning short and explain why the workflow was selected or why the request is unsupported.

Workflow library:
{workflow_metadata}

User question:
{question}

Return only valid JSON. Do not include markdown, comments, or extra text.

JSON schema:
{
  "query_key": "one workflow_key from the library, or unsupported",
  "confidence": 0.0,
  "reasoning": "one short plain-English sentence"
}
```

## Why This Prompt Works

The prompt has three main constraints:

1. **Workflow-only selection**

   The model can only choose from known workflow keys. It cannot invent a new analysis path.

2. **No arbitrary SQL generation**

   The model does not write SQL. This reduces hallucination risk and keeps evidence reproducible.

3. **Explicit unsupported behavior**

   The model is allowed to say a question is outside coverage. This is important for a trusted analyst workbench because not every question can be answered from the current dataset.

## Example Input

```text
User question:
Can you tell me the overall cancellation rate?
```

Expected supervisor output:

```json
{
  "query_key": "cancellation_overview",
  "confidence": 0.9,
  "reasoning": "The question asks for the overall cancellation rate, which is covered by the cancellation overview workflow."
}
```

## Unsupported Example

```text
User question:
What's your advice?
```

Expected supervisor output:

```json
{
  "query_key": "unsupported",
  "confidence": 0.8,
  "reasoning": "The question is too broad and does not specify a supported data analysis target."
}
```

## Runtime Safety

The app validates the model output after generation:

- If the model returns an unknown workflow key, the app converts it to `unsupported`.
- If Gemini fails or is unavailable, the app falls back to deterministic routing.
- If no API key is configured, the app still runs locally.

## Design Philosophy

This prompt supports the core project positioning:

> LLM selects the workflow. DuckDB computes the evidence. The app exposes the SQL and limitations.

The result is not a general chatbot. It is a governed, SQL-grounded analyst workbench for non-technical stakeholders.
