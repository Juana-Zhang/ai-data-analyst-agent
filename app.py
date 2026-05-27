from pathlib import Path
from datetime import datetime
import html
import json
import os
import re

import duckdb
import pandas as pd
import streamlit as st


DATA_PATH = Path("data.csv")

QUERY_LIBRARY = {
    "cancellation_overview": {
        "title": "Cancellation Overview",
        "description": "Summarizes booking volume, cancellation rate, ADR, and booking date range.",
        "required_columns": ["is_cancelled", "ADR", "booking_date"],
        "sql": """
            SELECT
                COUNT(*) AS total_bookings,
                SUM(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_bookings,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct,
                ROUND(AVG(ADR), 2) AS avg_adr,
                MIN(booking_date) AS first_booking_date,
                MAX(booking_date) AS last_booking_date
            FROM read_csv_auto('data.csv')
        """,
    },
    "city_risk": {
        "title": "Cancellation Risk by City",
        "description": "Compares cancellation rates and ADR across cities.",
        "required_columns": ["city_name", "is_cancelled", "ADR"],
        "sql": """
            SELECT
                city_name,
                COUNT(*) AS bookings,
                SUM(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_bookings,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct,
                ROUND(AVG(ADR), 2) AS avg_adr
            FROM read_csv_auto('data.csv')
            GROUP BY city_name
            ORDER BY cancellation_rate_pct DESC, bookings DESC
        """,
    },
    "platform_performance": {
        "title": "Platform Performance",
        "description": "Compares booking volume, cancellation rate, and ADR by platform.",
        "required_columns": ["platform_group_name", "is_cancelled", "ADR"],
        "sql": """
            SELECT
                platform_group_name,
                COUNT(*) AS bookings,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS booking_share_pct,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct,
                ROUND(AVG(ADR), 2) AS avg_adr
            FROM read_csv_auto('data.csv')
            GROUP BY platform_group_name
            ORDER BY bookings DESC
        """,
    },
    "payment_model": {
        "title": "Payment Model Analysis",
        "description": "Checks whether cancellation behavior differs by payment model.",
        "required_columns": ["payment_model", "is_cancelled", "ADR"],
        "sql": """
            SELECT
                payment_model,
                COUNT(*) AS bookings,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct,
                ROUND(AVG(ADR), 2) AS avg_adr
            FROM read_csv_auto('data.csv')
            GROUP BY payment_model
            ORDER BY cancellation_rate_pct DESC, bookings DESC
        """,
    },
    "star_rating_adr": {
        "title": "ADR by Star Rating",
        "description": "Profiles price levels and cancellation rates by hotel star rating.",
        "required_columns": ["current_star_rating", "is_cancelled", "ADR"],
        "sql": """
            SELECT
                current_star_rating,
                COUNT(*) AS bookings,
                ROUND(AVG(ADR), 2) AS avg_adr,
                ROUND(MEDIAN(ADR), 2) AS median_adr,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct
            FROM read_csv_auto('data.csv')
            GROUP BY current_star_rating
            ORDER BY current_star_rating
        """,
    },
    "lead_time": {
        "title": "Lead Time and Cancellation",
        "description": "Groups bookings by days between booking and check-in.",
        "required_columns": ["booking_date", "checkin_date", "is_cancelled", "ADR"],
        "sql": """
            WITH base AS (
                SELECT
                    DATE_DIFF('day', booking_date::DATE, checkin_date::DATE) AS lead_time_days,
                    is_cancelled,
                    ADR
                FROM read_csv_auto('data.csv')
            ),
            bucketed AS (
                SELECT
                    CASE
                        WHEN lead_time_days < 7 THEN '0-6 days'
                        WHEN lead_time_days < 30 THEN '7-29 days'
                        WHEN lead_time_days < 90 THEN '30-89 days'
                        ELSE '90+ days'
                    END AS lead_time_bucket,
                    is_cancelled,
                    ADR
                FROM base
            )
            SELECT
                lead_time_bucket,
                COUNT(*) AS bookings,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct,
                ROUND(AVG(ADR), 2) AS avg_adr
            FROM bucketed
            GROUP BY lead_time_bucket
            ORDER BY
                CASE lead_time_bucket
                    WHEN '0-6 days' THEN 1
                    WHEN '7-29 days' THEN 2
                    WHEN '30-89 days' THEN 3
                    ELSE 4
                END
        """,
    },
    "sample_rows": {
        "title": "Sample Rows",
        "description": "Shows the first 10 rows from the dataset.",
        "required_columns": [],
        "sql": "SELECT * FROM read_csv_auto('data.csv') LIMIT 10",
    },
    "high_risk_segments": {
        "title": "High-Risk Booking Segments",
        "description": "Identifies city, platform, payment model, and route combinations with elevated cancellation rates.",
        "required_columns": [
            "city_name",
            "platform_group_name",
            "payment_model",
            "booking_route_type",
            "is_cancelled",
            "ADR",
        ],
        "sql": """
            SELECT
                city_name,
                platform_group_name,
                payment_model,
                booking_route_type,
                COUNT(*) AS bookings,
                ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct,
                ROUND(AVG(ADR), 2) AS avg_adr
            FROM read_csv_auto('data.csv')
            GROUP BY
                city_name,
                platform_group_name,
                payment_model,
                booking_route_type
            HAVING COUNT(*) >= 1000
            ORDER BY cancellation_rate_pct DESC, bookings DESC
            LIMIT 20
        """,
    },
}

QUESTION_TEMPLATES = {
    "Give me an overview of booking cancellations.": "cancellation_overview",
    "Which cities have the highest cancellation risk?": "city_risk",
    "How do platforms compare on cancellation rate and ADR?": "platform_performance",
    "Does payment model affect cancellation behavior?": "payment_model",
    "How does ADR vary by hotel star rating?": "star_rating_adr",
    "Does booking lead time relate to cancellation risk?": "lead_time",
    "Which booking segments look highest risk?": "high_risk_segments",
    "Show me a sample of the raw data.": "sample_rows",
}

SUPPORTED_TOPICS = [
    "cancellation overview",
    "city risk",
    "platform performance",
    "payment model analysis",
    "ADR by star rating",
    "lead time analysis",
    "high-risk segment detection",
    "raw data preview",
]

SUPERVISOR_MODES = [
    "Deterministic supervisor",
    "Gemini supervisor (optional)",
]


def run_sql(sql: str) -> pd.DataFrame:
    return duckdb.sql(sql).df()


def choose_query_key(question: str) -> str:
    text = question.lower()

    if any(phrase in text for phrase in ["overall cancellation", "cancellation rate", "cancel rate"]):
        return "cancellation_overview"
    if any(word in text for word in ["risk segment", "segment", "combination", "highest risk"]):
        return "high_risk_segments"
    if any(word in text for word in ["city", "region", "location"]):
        return "city_risk"
    if any(word in text for word in ["platform", "app", "website", "mobile"]):
        return "platform_performance"
    if any(word in text for word in ["payment", "pay"]):
        return "payment_model"
    if any(word in text for word in ["star", "rating", "adr", "price"]):
        return "star_rating_adr"
    if any(word in text for word in ["lead time", "advance", "check-in", "checkin"]):
        return "lead_time"
    if any(word in text for word in ["sample", "raw", "rows", "preview"]):
        return "sample_rows"
    if any(word in text for word in ["cancel", "cancellation", "overview", "summary", "booking"]):
        return "cancellation_overview"
    return "unsupported"


def workflow_metadata() -> list[dict[str, str]]:
    rows = []
    for key, workflow in QUERY_LIBRARY.items():
        rows.append(
            {
                "workflow_key": key,
                "title": workflow["title"],
                "description": workflow["description"],
                "required_columns": ", ".join(workflow["required_columns"]) or "None",
            }
        )
    rows.append(
        {
            "workflow_key": "unsupported",
            "title": "Unsupported question",
            "description": "Use when the question is outside the current workflow coverage or cannot be answered from available data.",
            "required_columns": "N/A",
        }
    )
    return rows


def deterministic_supervisor(question: str) -> dict[str, str | float]:
    query_key = choose_query_key(question)
    if query_key == "unsupported":
        return {
            "query_key": "unsupported",
            "supervisor": "Deterministic supervisor",
            "confidence": 0.35,
            "reasoning": "The question did not match the current workflow library with enough confidence.",
        }

    workflow = QUERY_LIBRARY[query_key]
    return {
        "query_key": query_key,
        "supervisor": "Deterministic supervisor",
        "confidence": 0.75,
        "reasoning": f"Matched the question to the trusted workflow: {workflow['title']}.",
    }


def get_gemini_api_key() -> str | None:
    try:
        return st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    except Exception:
        return os.getenv("GEMINI_API_KEY")


def get_gemini_model() -> str:
    try:
        return st.secrets.get("GEMINI_MODEL") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    except Exception:
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def extract_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))


def build_supervisor_prompt(question: str, metadata: str) -> str:
    return f"""
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
{metadata}

User question:
{question}

Return only valid JSON. Do not include markdown, comments, or extra text.

JSON schema:
{{
  "query_key": "one workflow_key from the library, or unsupported",
  "confidence": 0.0,
  "reasoning": "one short plain-English sentence"
}}
"""


def gemini_supervisor(question: str) -> dict[str, str | float]:
    api_key = get_gemini_api_key()
    if not api_key:
        fallback = deterministic_supervisor(question)
        fallback["supervisor"] = "Deterministic supervisor fallback"
        fallback["reasoning"] += " Gemini was selected, but no GEMINI_API_KEY was configured."
        return fallback

    try:
        from google import genai
    except ImportError:
        fallback = deterministic_supervisor(question)
        fallback["supervisor"] = "Deterministic supervisor fallback"
        fallback["reasoning"] += " Gemini was selected, but the google-genai package is not installed."
        return fallback

    metadata = json.dumps(workflow_metadata(), indent=2)
    prompt = build_supervisor_prompt(question, metadata)

    try:
        client = genai.Client(api_key=api_key)
        model_name = get_gemini_model()
        response = client.models.generate_content(model=model_name, contents=prompt)
        decision = extract_json_object(response.text)
        query_key = decision.get("query_key", "unsupported")
        if query_key not in QUERY_LIBRARY and query_key != "unsupported":
            query_key = "unsupported"
        return {
            "query_key": query_key,
            "supervisor": f"Gemini supervisor ({model_name})",
            "confidence": float(decision.get("confidence", 0.5)),
            "reasoning": str(decision.get("reasoning", "Gemini selected this workflow.")),
        }
    except Exception as exc:
        fallback = deterministic_supervisor(question)
        fallback["supervisor"] = "Deterministic supervisor fallback"
        fallback["reasoning"] += f" Gemini supervisor failed safely: {exc}"
        return fallback


def supervisor_decision(question: str, mode: str) -> dict[str, str | float]:
    if mode == "Gemini supervisor (optional)":
        return gemini_supervisor(question)
    return deterministic_supervisor(question)


def profile_dataset() -> pd.DataFrame:
    return run_sql(
        """
        DESCRIBE SELECT *
        FROM read_csv_auto('data.csv')
        """
    )


def data_quality_summary() -> pd.DataFrame:
    return run_sql(
        """
        WITH base AS (
            SELECT *
            FROM read_csv_auto('data.csv')
        ),
        duplicate_rows AS (
            SELECT COALESCE(SUM(row_count - 1), 0) AS duplicate_count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM base
                GROUP BY
                    hotel_id,
                    current_star_rating,
                    accommodation_type_name,
                    chain,
                    booking_date,
                    checkin_date,
                    checkout_date,
                    booking_route_type,
                    platform_group_name,
                    is_cancelled,
                    city_name,
                    payment_type,
                    payment_model,
                    ADR
                HAVING COUNT(*) > 1
            )
        )
        SELECT 'total_rows' AS check_name, COUNT(*)::VARCHAR AS result
        FROM base
        UNION ALL
        SELECT 'duplicate_rows', duplicate_count::VARCHAR
        FROM duplicate_rows
        UNION ALL
        SELECT 'missing_hotel_id', SUM(CASE WHEN hotel_id IS NULL THEN 1 ELSE 0 END)::VARCHAR
        FROM base
        UNION ALL
        SELECT 'missing_dates', SUM(CASE WHEN booking_date IS NULL OR checkin_date IS NULL OR checkout_date IS NULL THEN 1 ELSE 0 END)::VARCHAR
        FROM base
        UNION ALL
        SELECT 'negative_adr', SUM(CASE WHEN ADR < 0 THEN 1 ELSE 0 END)::VARCHAR
        FROM base
        UNION ALL
        SELECT 'checkin_before_booking', SUM(CASE WHEN checkin_date::DATE < booking_date::DATE THEN 1 ELSE 0 END)::VARCHAR
        FROM base
        UNION ALL
        SELECT 'checkout_before_checkin', SUM(CASE WHEN checkout_date::DATE < checkin_date::DATE THEN 1 ELSE 0 END)::VARCHAR
        FROM base
        """
    )


def missing_value_summary() -> pd.DataFrame:
    return run_sql(
        """
        SELECT
            column_name,
            count - ROUND(count * (1 - null_percentage / 100.0)) AS null_count,
            null_percentage AS null_rate_pct
        FROM (
            SUMMARIZE SELECT *
            FROM read_csv_auto('data.csv')
        )
        ORDER BY null_count DESC, column_name
        """
    )


def build_interpretation(query_key: str, result: pd.DataFrame) -> str:
    if result.empty:
        return "No rows were returned for this workflow."

    if query_key == "cancellation_overview":
        row = result.iloc[0]
        return (
            f"The dataset contains {int(row['total_bookings']):,} bookings, with an overall "
            f"cancellation rate of {row['cancellation_rate_pct']}%. Average ADR is {row['avg_adr']}. "
            "This establishes the baseline for comparing specific segments."
        )

    if query_key == "city_risk":
        top = result.iloc[0]
        return (
            f"{top['city_name']} has the highest observed cancellation rate at "
            f"{top['cancellation_rate_pct']}% across {int(top['bookings']):,} bookings. "
            "This city should be prioritized for follow-up analysis before assuming the pattern is causal."
        )

    if query_key == "platform_performance":
        top_volume = result.sort_values("bookings", ascending=False).iloc[0]
        top_risk = result.sort_values("cancellation_rate_pct", ascending=False).iloc[0]
        return (
            f"{top_volume['platform_group_name']} contributes the largest booking volume, while "
            f"{top_risk['platform_group_name']} has the highest cancellation rate at "
            f"{top_risk['cancellation_rate_pct']}%. This helps separate scale from risk."
        )

    if query_key == "payment_model":
        top = result.iloc[0]
        return (
            f"{top['payment_model']} has the highest cancellation rate at "
            f"{top['cancellation_rate_pct']}%. Payment model may be a useful dimension for risk controls "
            "or follow-up experimentation."
        )

    if query_key == "star_rating_adr":
        highest_adr = result.sort_values("avg_adr", ascending=False).iloc[0]
        return (
            f"The highest average ADR appears in the {highest_adr['current_star_rating']}-star segment "
            f"at {highest_adr['avg_adr']}. Comparing this with cancellation rate can show whether premium "
            "segments carry different demand or cancellation dynamics."
        )

    if query_key == "lead_time":
        top = result.sort_values("cancellation_rate_pct", ascending=False).iloc[0]
        return (
            f"The {top['lead_time_bucket']} bucket has the highest cancellation rate at "
            f"{top['cancellation_rate_pct']}%. This suggests booking lead time is an important risk signal."
        )

    if query_key == "high_risk_segments":
        top = result.iloc[0]
        return (
            "The highest-risk segment combines "
            f"city {top['city_name']}, platform {top['platform_group_name']}, payment model "
            f"{top['payment_model']}, and route {top['booking_route_type']}, with a "
            f"{top['cancellation_rate_pct']}% cancellation rate across {int(top['bookings']):,} bookings. "
            "This is a strong candidate for targeted operational review."
        )

    if query_key == "sample_rows":
        return "This preview confirms the raw fields available for downstream workflows."

    return "This workflow returned a reproducible SQL-backed result from the local dataset."


def build_limitations(query_key: str) -> list[str]:
    if query_key == "unsupported":
        return [
            "The question is outside the current workflow library.",
            "No SQL was executed because the system could not map the request to a trusted analysis path.",
        ]

    return [
        "This prototype uses the available columns in data.csv and does not infer causes beyond the observed data.",
        "The workflow returns descriptive evidence, not a causal model.",
        "Results should be reviewed with business context before operational decisions are made.",
    ]


def build_next_steps(query_key: str) -> list[str]:
    next_steps = {
        "cancellation_overview": [
            "Compare cancellation rates by customer, booking, or property segment.",
            "Investigate whether high cancellation periods align with campaigns, seasonality, or policy changes.",
        ],
        "city_risk": [
            "Prioritize high-cancellation cities for deeper root-cause analysis.",
            "Compare city-level patterns against platform, payment model, and lead time.",
        ],
        "platform_performance": [
            "Separate volume-driving platforms from high-risk platforms.",
            "Review whether cancellation policies or user behavior differ by platform.",
        ],
        "payment_model": [
            "Review payment models with elevated cancellation risk.",
            "Test whether stricter payment or confirmation rules reduce preventable cancellations.",
        ],
        "star_rating_adr": [
            "Compare premium and budget segments on both ADR and cancellation rate.",
            "Check whether high-ADR segments need different cancellation mitigation strategies.",
        ],
        "lead_time": [
            "Use lead time as a candidate feature for cancellation risk scoring.",
            "Consider targeted reminders or policy changes for long-lead bookings.",
        ],
        "high_risk_segments": [
            "Review the top risky combinations with business stakeholders.",
            "Validate whether these segments are stable over time before taking action.",
        ],
        "sample_rows": [
            "Use the raw preview to confirm field meanings and identify new workflow candidates.",
            "Add more domain metadata before expanding analysis coverage.",
        ],
        "unsupported": [
            "Rephrase the question using one of the supported topics.",
            "Add a new workflow if the question is important and the required fields are available.",
        ],
    }
    return next_steps.get(query_key, next_steps["unsupported"])


def build_data_context(query_key: str) -> dict:
    profile = profile_dataset()
    row_count = run_sql("SELECT COUNT(*) AS row_count FROM read_csv_auto('data.csv')").iloc[0]["row_count"]
    required_columns = QUERY_LIBRARY.get(query_key, {}).get("required_columns", [])

    return {
        "data_source": "data.csv",
        "query_engine": "DuckDB",
        "table_reference": "read_csv_auto('data.csv')",
        "dataset_domain": "Hotel booking records",
        "row_count": int(row_count),
        "column_count": len(profile),
        "available_columns": profile["column_name"].tolist(),
        "fields_used": required_columns,
    }


def create_report_package(question: str, decision: dict[str, str | float]) -> dict:
    query_key = str(decision["query_key"])
    if query_key == "unsupported":
        return {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "question": question,
            "decision": decision,
            "query_key": query_key,
            "workflow_title": "Unsupported question",
            "workflow_description": "The question could not be mapped to a supported workflow.",
            "sql": "",
            "result": pd.DataFrame(),
            "interpretation": "No analysis was run because the question is outside the current workflow coverage.",
            "data_context": build_data_context(query_key),
            "limitations": build_limitations(query_key),
            "next_steps": build_next_steps(query_key),
        }

    query = QUERY_LIBRARY[query_key]
    result = run_sql(query["sql"])
    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
        "decision": decision,
        "query_key": query_key,
        "workflow_title": query["title"],
        "workflow_description": query["description"],
        "sql": query["sql"].strip(),
        "result": result,
        "interpretation": build_interpretation(query_key, result),
        "data_context": build_data_context(query_key),
        "limitations": build_limitations(query_key),
        "next_steps": build_next_steps(query_key),
    }


def build_report_html(report: dict) -> str:
    result = report["result"]
    table_html = (
        result.to_html(index=False, border=0, classes="result-table")
        if isinstance(result, pd.DataFrame) and not result.empty
        else "<p>No result table was generated.</p>"
    )
    limitations_html = "".join(f"<li>{html.escape(item)}</li>" for item in report["limitations"])
    next_steps_html = "".join(f"<li>{html.escape(item)}</li>" for item in report["next_steps"])
    context = report["data_context"]
    fields_used = context["fields_used"] or ["No workflow fields were selected."]
    fields_used_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in fields_used)
    available_columns_html = ", ".join(html.escape(str(item)) for item in context["available_columns"])
    sql_html = html.escape(report["sql"]) if report["sql"] else "No SQL executed."
    decision = report["decision"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AI Data Analyst Workbench Report</title>
  <style>
    body {{
      color: #1f2937;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
      margin: 40px auto;
      max-width: 1100px;
      padding: 0 24px;
    }}
    h1, h2 {{ color: #111827; }}
    .meta, .box {{
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 16px;
      margin: 16px 0;
    }}
    .finding {{
      background: #eff6ff;
      border-left: 4px solid #2563eb;
      padding: 14px 16px;
      margin: 16px 0;
    }}
    pre {{
      background: #111827;
      border-radius: 8px;
      color: #f9fafb;
      overflow-x: auto;
      padding: 16px;
    }}
    table {{
      border-collapse: collapse;
      font-size: 13px;
      margin-top: 12px;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #e5e7eb;
      padding: 8px 10px;
      text-align: left;
    }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>AI Data Analyst Workbench Report</h1>
  <div class="meta">
    <p><strong>Created:</strong> {html.escape(report["created_at"])}</p>
    <p><strong>User question:</strong> {html.escape(report["question"])}</p>
    <p><strong>Supervisor:</strong> {html.escape(str(decision.get("supervisor", "")))}</p>
    <p><strong>Confidence:</strong> {html.escape(str(decision.get("confidence", "")))}</p>
    <p><strong>Supervisor reasoning:</strong> {html.escape(str(decision.get("reasoning", "")))}</p>
  </div>

  <h2>Selected Workflow</h2>
  <div class="box">
    <p><strong>{html.escape(report["workflow_title"])}</strong></p>
    <p>{html.escape(report["workflow_description"])}</p>
  </div>

  <h2>Data Context</h2>
  <div class="box">
    <p><strong>Data source:</strong> {html.escape(context["data_source"])}</p>
    <p><strong>Dataset domain:</strong> {html.escape(context["dataset_domain"])}</p>
    <p><strong>Query engine:</strong> {html.escape(context["query_engine"])}</p>
    <p><strong>Table reference:</strong> <code>{html.escape(context["table_reference"])}</code></p>
    <p><strong>Rows analyzed:</strong> {context["row_count"]:,}</p>
    <p><strong>Columns available:</strong> {context["column_count"]}</p>
    <p><strong>Available columns:</strong> {available_columns_html}</p>
    <p><strong>Fields used by this workflow:</strong></p>
    <ul>{fields_used_html}</ul>
  </div>

  <h2>Key Finding</h2>
  <div class="finding">{html.escape(report["interpretation"])}</div>

  <h2>SQL Evidence</h2>
  <pre><code>{sql_html}</code></pre>

  <h2>Result Table</h2>
  {table_html}

  <h2>Limitations</h2>
  <ul>{limitations_html}</ul>

  <h2>Recommended Next Steps</h2>
  <ul>{next_steps_html}</ul>
</body>
</html>
"""


def render_download_button(report: dict, key: str) -> None:
    file_slug = re.sub(r"[^a-z0-9]+", "-", report["workflow_title"].lower()).strip("-")
    st.download_button(
        "Download HTML Report",
        data=build_report_html(report),
        file_name=f"{file_slug or 'analysis'}-report.html",
        mime="text/html",
        key=key,
    )


def render_report(report: dict) -> None:
    query_key = report["query_key"]
    result = report["result"]

    if query_key == "unsupported":
        st.warning(
            "I could not confidently map this question to an existing analysis workflow. "
            "Please try one of the supported topics below."
        )
        st.write(", ".join(SUPPORTED_TOPICS))
        st.info(report["interpretation"])
        return

    st.caption(report["workflow_description"])

    if query_key == "cancellation_overview" and not result.empty:
        row = result.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Bookings", f"{int(row['total_bookings']):,}")
        col2.metric("Cancelled Bookings", f"{int(row['cancelled_bookings']):,}")
        col3.metric("Cancellation Rate", f"{row['cancellation_rate_pct']}%")
        col4.metric("Average ADR", f"{row['avg_adr']}")

    st.info(report["interpretation"])
    st.dataframe(result, use_container_width=True)

    chart_columns = [column for column in result.columns if column.endswith("_pct") or column == "avg_adr"]
    dimension_columns = [
        column
        for column in result.columns
        if column not in chart_columns and column not in {"bookings", "cancelled_bookings"}
    ]

    if chart_columns and dimension_columns and len(result) > 1:
        chart_data = result.set_index(dimension_columns[0])[chart_columns[0]]
        st.bar_chart(chart_data)


def render_result(query_key: str) -> None:
    query = QUERY_LIBRARY[query_key]
    result = run_sql(query["sql"])

    st.caption(query["description"])

    if query_key == "cancellation_overview" and not result.empty:
        row = result.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Bookings", f"{int(row['total_bookings']):,}")
        col2.metric("Cancelled Bookings", f"{int(row['cancelled_bookings']):,}")
        col3.metric("Cancellation Rate", f"{row['cancellation_rate_pct']}%")
        col4.metric("Average ADR", f"{row['avg_adr']}")
        st.info(build_interpretation(query_key, result))
        st.dataframe(result, use_container_width=True)
        return

    st.info(build_interpretation(query_key, result))
    st.dataframe(result, use_container_width=True)

    chart_columns = [column for column in result.columns if column.endswith("_pct") or column == "avg_adr"]
    dimension_columns = [
        column
        for column in result.columns
        if column not in chart_columns and column not in {"bookings", "cancelled_bookings"}
    ]

    if chart_columns and dimension_columns and len(result) > 1:
        chart_data = result.set_index(dimension_columns[0])[chart_columns[0]]
        st.bar_chart(chart_data)


st.set_page_config(page_title="AI Data Analyst Workbench", layout="wide")

st.title("AI Data Analyst Workbench (Prototype)")
st.caption("A local DuckDB-powered analysis workflow for non-technical stakeholders.")

if not DATA_PATH.exists():
    st.error("data.csv was not found. Please place it in the ai_analyst_agent folder and refresh the app.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "latest_report" not in st.session_state:
    st.session_state.latest_report = None

with st.sidebar:
    st.header("Workbench")
    st.write("Data source: `data.csv`")
    supervisor_mode = st.radio("Supervisor mode", SUPERVISOR_MODES)
    selected_question = st.selectbox("Business question templates", list(QUESTION_TEMPLATES.keys()))

    if st.button("Run Template", use_container_width=True):
        decision = supervisor_decision(selected_question, supervisor_mode)
        report = create_report_package(selected_question, decision)
        st.session_state.latest_report = report
        st.session_state.messages.append({"role": "user", "content": selected_question})
        st.session_state.messages.append(
            {
                "role": "assistant",
                "query_key": decision["query_key"],
                "decision": decision,
                "report": report,
            }
        )

    st.divider()
    st.subheader("Supervisor Layer")
    st.write("The supervisor chooses one trusted workflow before DuckDB runs any SQL.")
    st.write("Gemini is optional. Without a configured key, the app falls back safely to local routing.")

overview_tab, profile_tab, library_tab, report_tab = st.tabs(
    ["Ask Data", "Dataset Profile", "Workflow Library", "Executive Brief"]
)

with overview_tab:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            elif message.get("query_key") == "unsupported":
                decision = message.get("decision")
                report = message.get("report")
                if decision:
                    st.write(f"Supervisor: **{decision['supervisor']}**")
                    st.caption(f"Confidence: {decision['confidence']}")
                    st.write(decision["reasoning"])
                if report:
                    render_report(report)
            else:
                decision = message.get("decision")
                report = message.get("report")
                if decision:
                    st.write(f"Supervisor: **{decision['supervisor']}**")
                    st.caption(f"Confidence: {decision['confidence']}")
                    st.write(decision["reasoning"])
                if not report:
                    report = create_report_package(message.get("content", ""), decision)
                    message["report"] = report
                st.write(f"Selected analysis: **{report['workflow_title']}**")
                with st.expander("SQL used"):
                    st.code(report["sql"], language="sql")
                render_report(report)
                render_download_button(report, key=f"download_{id(message)}")

    prompt = st.chat_input("Ask your data...", key="week2_prompt")

    if prompt:
        decision = supervisor_decision(prompt, supervisor_mode)
        report = create_report_package(prompt, decision)
        st.session_state.latest_report = report

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append(
            {
                "role": "assistant",
                "query_key": decision["query_key"],
                "decision": decision,
                "report": report,
            }
        )
        st.rerun()

with profile_tab:
    st.subheader("Dataset Schema")
    st.dataframe(profile_dataset(), use_container_width=True)

    st.subheader("Data Quality Checks")
    st.dataframe(data_quality_summary(), use_container_width=True)

    st.subheader("Missing Value Summary")
    st.dataframe(missing_value_summary(), use_container_width=True)

    st.subheader("Preview")
    render_result("sample_rows")

with library_tab:
    st.subheader("Supported Analysis Workflows")
    st.write(
        "Each workflow is a trusted SQL framework with declared required columns. "
        "This makes the prototype coverage-aware instead of pretending it can answer every question."
    )

    st.dataframe(pd.DataFrame(workflow_metadata()), use_container_width=True)

    st.subheader("Unsupported Question Behavior")
    st.write(
        "If a stakeholder asks a question outside the current workflow library, the app explains "
        "the limitation and suggests supported topics instead of forcing an unreliable answer."
    )

with report_tab:
    st.subheader("Latest Executive Report")
    latest_report = st.session_state.latest_report
    if latest_report:
        st.write(f"**Question:** {latest_report['question']}")
        st.write(f"**Workflow:** {latest_report['workflow_title']}")
        st.write(f"**Supervisor:** {latest_report['decision'].get('supervisor')}")
        st.info(latest_report["interpretation"])

        context = latest_report["data_context"]
        st.write("**Data context**")
        col1, col2, col3 = st.columns(3)
        col1.metric("Rows analyzed", f"{context['row_count']:,}")
        col2.metric("Columns available", context["column_count"])
        col3.metric("Query engine", context["query_engine"])
        st.write(f"**Data source:** `{context['data_source']}`")
        st.write(f"**Table reference:** `{context['table_reference']}`")
        st.write("**Fields used by this workflow:**")
        st.write(", ".join(context["fields_used"]) if context["fields_used"] else "No workflow fields were selected.")

        with st.expander("Report SQL evidence"):
            st.code(latest_report["sql"] or "No SQL executed.", language="sql")

        st.write("**Limitations**")
        for item in latest_report["limitations"]:
            st.write(f"- {item}")

        st.write("**Recommended next steps**")
        for item in latest_report["next_steps"]:
            st.write(f"- {item}")

        render_download_button(latest_report, key="download_latest_report")
    else:
        st.write("Run an analysis in the Ask Data tab to generate a downloadable executive report.")

    st.divider()

    st.subheader("Project Goal")
    st.write(
        "This project explores an AI analyst workbench pattern for cross-functional teams. "
        "The goal is to let non-technical stakeholders ask business questions in natural "
        "language while the system retrieves reproducible, SQL-backed evidence from local data."
    )

    st.subheader("Weekly Roadmap")
    st.markdown(
        """
        | Week | Focus | Deliverable |
        | --- | --- | --- |
        | Week 1 | Build the basic Streamlit and DuckDB connection | A chat-style prototype where any question runs a fixed SQL query: `SELECT * FROM read_csv_auto('data.csv') LIMIT 10;` |
        | Week 2 | Upgrade the fixed-query demo into an analyst workbench | Rule-based question routing, pre-designed SQL workflows, KPI summaries, charts, schema profiling, and transparent SQL display |
        | Week 3 | Strengthen the analysis layer | Add data quality checks, missing-value summaries, high-risk segment detection, and richer business interpretations |
        | Week 4 | Add an AI supervisor layer | Add a supervisor mode that can use Gemini to choose among trusted workflows, with a deterministic fallback when no API key is configured |
        | Week 5 | Generate executive outputs | Add one-click downloadable HTML reports with findings, SQL evidence, limitations, and recommended next steps |
        | Week 6 | Polish for portfolio presentation | Add README, architecture documentation, setup instructions, demo script, and future extension plan |
        """
    )

    st.subheader("Current Capabilities")
    st.write(
        "- Local CSV analysis through DuckDB\n"
        "- Deterministic supervisor for local workflow routing\n"
        "- Optional Gemini supervisor for LLM-based workflow selection\n"
        "- Safe fallback when Gemini is not configured or unavailable\n"
        "- Transparent SQL for every result\n"
        "- KPI summaries, tables, and quick charts\n"
        "- Dataset schema inspection and quality checks\n"
        "- One-click downloadable HTML reports"
    )

    st.subheader("Gemini Setup")
    st.write(
        "To enable the optional Gemini supervisor, install `google-genai` and configure "
        "`GEMINI_API_KEY` through an environment variable or `.streamlit/secrets.toml`. "
        "The app remains usable without this key."
    )

    st.subheader("Portfolio Positioning")
    st.write(
        "This demo is designed for recruiters and hiring managers, while the product experience is "
        "designed for non-technical stakeholders who need trusted, SQL-backed business answers."
    )
