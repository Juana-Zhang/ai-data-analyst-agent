# Prompt Design

This project uses the LLM as a Guided AI routing layer and result interpreter, not as a free-form SQL generator.

The prompt is designed to make the model decide the next best analytical action. If a question is specific, the model chooses from a trusted workflow library. If a user does not know where to start, the model suggests useful analysis directions. DuckDB performs the actual computation using predefined SQL. This keeps the app helpful, reproducible, inspectable, and safer for business users.

## Core Guided AI Routing Prompt

```text
You are the routing agent inside a SQL-grounded AI Data Analyst Workbench.

Product context:
- The app is built for non-technical business stakeholders.
- The goal is to answer data questions only through trusted, reproducible workflows.
- The LLM is not allowed to write arbitrary SQL or invent data.
- DuckDB will execute the selected workflow's predefined SQL.
- The LLM should help users frame better analytical questions when their request is vague.

Your task:
Decide the next best action for the user question.

Decision rules:
1. Use action "run_workflow" when the question maps clearly to one existing workflow.
2. Use action "suggest_analysis_plan" when the user asks how to analyze the data, where to start, what analysts usually check, or asks for analysis ideas.
3. Use action "ask_clarification" when the user asks for broad business advice but does not specify a measurable analysis target.
4. Use action "propose_new_analysis" when the user asks for a reasonable analysis that is not in the workflow library but appears feasible from the available columns.
5. Use action "unsupported" only when the question cannot be answered from the current dataset or asks for fields/workflows not available.
6. Do not create new workflow keys.
7. Do not execute or claim results for proposed analyses.
8. For propose_new_analysis, provide a draft SQL query using only the configured data source and available columns. This SQL is for review only and will not be executed automatically.
9. Do not invent data or findings.
10. If action is not "run_workflow", set query_key to "unsupported" and provide helpful suggested questions or a proposed analysis.

Workflow library:
{workflow_metadata}

Available dataset columns:
{columns}

User question:
{question}

Return only valid JSON. Do not include markdown, comments, or extra text.

JSON schema:
{
  "action": "run_workflow | suggest_analysis_plan | ask_clarification | propose_new_analysis | unsupported",
  "query_key": "one workflow_key from the library if action is run_workflow, otherwise unsupported",
  "confidence": 0.0,
  "reasoning": "one short plain-English sentence",
  "user_message": "a helpful message to show the user",
  "suggested_questions": ["3 to 5 concrete questions the user could ask next"],
  "proposed_analysis": {
    "title": "short title for the proposed analysis",
    "required_columns": ["columns needed for the proposed analysis"],
    "draft_sql": "read-only draft SQL using the configured data source",
    "status": "Proposed only. Not executed automatically."
  }
}
```

## Why This Prompt Works

The prompt has three main constraints:

1. **Workflow-constrained computation**

   The model can only run known workflow keys. It cannot invent a new SQL analysis path.

2. **No arbitrary SQL generation**

   The model does not write SQL. This reduces hallucination risk and keeps evidence reproducible.

3. **Interactive guidance**

   If the user does not know how to analyze the dataset, the model suggests concrete next questions instead of stopping at `unsupported`.

4. **Explicit unsupported behavior**

   The model only uses `unsupported` when the question cannot be answered from the current data or workflow coverage.

5. **Controlled exploration**

   The model can propose a new analysis when the fields exist, but the app does not execute draft SQL automatically.

## Sample Domain Examples

The examples below use the public demo's sample domain. In another business domain, the workflow keys, metric names, and suggested questions would be replaced with that domain's schema and metric framework.

## Run Workflow Example

```text
User question:
Can you tell me the overall cancellation rate?
```

Expected routing output:

```json
{
  "action": "run_workflow",
  "query_key": "cancellation_overview",
  "confidence": 0.9,
  "reasoning": "The question asks for the overall cancellation rate, which is covered by the cancellation overview workflow.",
  "user_message": "I selected the cancellation overview workflow because it provides the overall booking and cancellation baseline.",
  "suggested_questions": []
}
```

## Guidance Example

```text
User question:
I don't know how to analyze this dataset. Where should I start?
```

Expected routing output:

```json
{
  "action": "suggest_analysis_plan",
  "query_key": "unsupported",
  "confidence": 0.9,
  "reasoning": "The user is asking for analysis guidance rather than a specific metric.",
  "user_message": "A good starting point is to understand the cancellation baseline, then compare cancellation risk by city, platform, lead time, and high-risk booking segments.",
  "suggested_questions": [
    "What is the overall cancellation rate?",
    "Which cities have the highest cancellation risk?",
    "How do platforms compare on cancellation rate and ADR?",
    "Does booking lead time relate to cancellation risk?",
    "Which booking segments look highest risk?"
  ]
}
```

## Unsupported Example

```text
User question:
Are younger customers more likely to cancel?
```

Expected routing output:

```json
{
  "action": "unsupported",
  "query_key": "unsupported",
  "confidence": 0.85,
  "reasoning": "The current dataset does not include customer age.",
  "user_message": "I cannot answer this from the current dataset because there is no customer age field.",
  "suggested_questions": [
    "What is the overall cancellation rate?",
    "Which booking segments look highest risk?"
  ]
}
```

## Proposed New Analysis Example

```text
User question:
How does cancellation vary by accommodation type?
```

Expected routing output:

```json
{
  "action": "propose_new_analysis",
  "query_key": "unsupported",
  "confidence": 0.82,
  "reasoning": "The question is feasible using available fields but is not covered by the current trusted workflow library.",
  "user_message": "This analysis is not in the current workflow library, but I can propose a draft analysis using accommodation type, cancellation status, and ADR.",
  "suggested_questions": [],
  "proposed_analysis": {
    "title": "Cancellation by Accommodation Type",
    "required_columns": ["accommodation_type_name", "is_cancelled", "ADR"],
    "draft_sql": "SELECT accommodation_type_name, COUNT(*) AS bookings, ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct, ROUND(AVG(ADR), 2) AS avg_adr FROM configured_data_source GROUP BY accommodation_type_name ORDER BY cancellation_rate_pct DESC, bookings DESC",
    "status": "Proposed only. Not executed automatically."
  }
}
```

## Runtime Safety

The app validates the model output after generation:

- If the model returns an unknown workflow key, the app converts it to `unsupported`.
- If the model returns a non-workflow action, the app does not execute SQL and instead displays guidance or clarification.
- If Guided AI Mode fails or is unavailable, the app falls back to Rule-based Mode routing.
- If no API key is configured, the app still runs locally.

## Result Interpreter Prompt

After a trusted SQL workflow runs, the app can call Gemini a second time as an evidence-grounded interpreter. This is where the AI adds more value than Rule-based Mode routing.

The interpreter receives:

- user question
- selected workflow
- SQL executed
- result preview
- data context

It must only explain what is supported by the SQL output.

Core constraints:

```text
You must explain only what is supported by the SQL result.
Do not invent numbers, columns, causes, or recommendations not grounded in the result.
Do not claim causality.
Use cautious language such as "suggests", "is associated with", or "should be investigated".
```

Expected interpreter output:

```json
{
  "interpretation": "2 to 4 plain-English sentences explaining the key insight from the result",
  "next_steps": ["2 to 4 recommended follow-up analyses or business actions"],
  "suggested_questions": ["2 to 4 concrete follow-up questions the user could ask next"]
}
```

## Design Philosophy

This prompt supports the core project positioning:

> Analysts define the trusted workflow library; AI routes questions and interprets verified results. DuckDB computes the evidence. The app exposes the SQL, data context, and limitations.

The result is not a general chatbot. It is a governed, SQL-grounded analyst workbench for non-technical stakeholders.
