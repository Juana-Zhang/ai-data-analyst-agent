from pathlib import Path
from datetime import datetime
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import duckdb
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


LOCAL_DATA_PATH = Path("data.csv")
SAMPLE_DATA_PATH = Path("sample_data.csv")


def resolve_data_path() -> Path:
    configured_path = os.getenv("APP_DATA_PATH")
    if configured_path:
        return Path(configured_path)
    if LOCAL_DATA_PATH.exists():
        return LOCAL_DATA_PATH
    return SAMPLE_DATA_PATH


DATA_PATH = resolve_data_path()
DATA_SOURCE_NAME = DATA_PATH.name
DATA_PATH_FOR_SQL = str(DATA_PATH).replace("'", "''")
DATA_SQL_REFERENCE = f"read_csv_auto('{DATA_PATH_FOR_SQL}')"

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
            HAVING COUNT(*) >= 20
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

DEFAULT_SUGGESTED_QUESTIONS = [
    "What is the overall cancellation rate?",
    "Which cities have the highest cancellation risk?",
    "How do platforms compare on cancellation rate and ADR?",
    "Does booking lead time relate to cancellation risk?",
    "Which booking segments look highest risk?",
]

RULE_BASED_MODE = "Rule-based Mode"
GUIDED_AI_MODE = "Guided AI Mode"

SUPERVISOR_MODES = [
    RULE_BASED_MODE,
    GUIDED_AI_MODE,
]


def run_sql(sql: str) -> pd.DataFrame:
    resolved_sql = sql.replace("read_csv_auto('data.csv')", DATA_SQL_REFERENCE)
    return duckdb.sql(resolved_sql).df()


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


def dataset_column_metadata() -> list[dict[str, str]]:
    try:
        profile = profile_dataset()
        return profile[["column_name", "column_type"]].to_dict(orient="records")
    except Exception:
        return []


def deterministic_supervisor(question: str) -> dict[str, str | float]:
    text = question.lower()

    if any(word in text for word in ["age", "income", "gender", "salary", "customer demographic"]):
        return {
            "action": "unsupported",
            "query_key": "unsupported",
            "supervisor": RULE_BASED_MODE,
            "confidence": 0.8,
            "reasoning": "The question requires fields that are not available in the current dataset.",
            "user_message": "I cannot answer this from the current dataset because the required demographic fields are not available.",
            "suggested_questions": DEFAULT_SUGGESTED_QUESTIONS,
        }

    if "accommodation" in text or "hotel type" in text or "property type" in text:
        return {
            "action": "propose_new_analysis",
            "query_key": "unsupported",
            "supervisor": RULE_BASED_MODE,
            "confidence": 0.72,
            "reasoning": "The question is feasible from available fields but is not yet part of the trusted workflow library.",
            "user_message": "This is not in the current trusted workflow library, but it can be proposed as a new analysis using available dataset fields. The draft SQL is not executed automatically.",
            "suggested_questions": [],
            "proposed_analysis": {
                "title": "Cancellation by Accommodation Type",
                "required_columns": ["accommodation_type_name", "is_cancelled", "ADR"],
                "draft_sql": (
                    "SELECT accommodation_type_name, COUNT(*) AS bookings, "
                    "ROUND(100.0 * AVG(CASE WHEN is_cancelled = 'cancelled' THEN 1 ELSE 0 END), 2) AS cancellation_rate_pct, "
                    "ROUND(AVG(ADR), 2) AS avg_adr "
                    f"FROM {DATA_SQL_REFERENCE} "
                    "GROUP BY accommodation_type_name "
                    "ORDER BY cancellation_rate_pct DESC, bookings DESC"
                ),
                "status": "Proposed only. Not executed automatically.",
            },
        }

    query_key = choose_query_key(question)
    if query_key != "unsupported":
        workflow = QUERY_LIBRARY[query_key]
        return {
            "action": "run_workflow",
            "query_key": query_key,
            "supervisor": RULE_BASED_MODE,
            "confidence": 0.75,
            "reasoning": f"Matched the question to the trusted workflow: {workflow['title']}.",
            "user_message": f"I selected the {workflow['title']} workflow because it can answer this question with SQL-backed evidence.",
            "suggested_questions": [],
        }

    if any(phrase in text for phrase in ["don't know", "do not know", "how to analyze", "where should i start", "start", "what should i look", "usually analyze", "normally analyze", "analysis ideas"]):
        return {
            "action": "suggest_analysis_plan",
            "query_key": "unsupported",
            "supervisor": RULE_BASED_MODE,
            "confidence": 0.85,
            "reasoning": "The user is asking for guidance on how to begin analyzing the dataset.",
            "user_message": (
                "A practical 1-2 step path is: Step 1, establish the overall cancellation baseline. "
                "Step 2, compare likely risk drivers such as city, platform, lead time, and high-risk booking segments."
            ),
            "suggested_questions": DEFAULT_SUGGESTED_QUESTIONS,
        }

    return {
        "action": "ask_clarification",
        "query_key": "unsupported",
        "supervisor": RULE_BASED_MODE,
        "confidence": 0.65,
        "reasoning": "The question is broad, so the app should guide the user toward a concrete analysis direction.",
        "user_message": "I can help, but I need a clearer business direction. For this dataset, you can explore cancellations, city risk, platform performance, payment model, ADR, lead time, or high-risk segments.",
        "suggested_questions": DEFAULT_SUGGESTED_QUESTIONS,
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


def get_ga4_measurement_id() -> str | None:
    try:
        return st.secrets.get("GA4_MEASUREMENT_ID") or os.getenv("GA4_MEASUREMENT_ID")
    except Exception:
        return os.getenv("GA4_MEASUREMENT_ID")


def get_ga4_api_secret() -> str | None:
    try:
        return st.secrets.get("GA4_API_SECRET") or os.getenv("GA4_API_SECRET")
    except Exception:
        return os.getenv("GA4_API_SECRET")


def render_ga4_tracking() -> None:
    measurement_id = get_ga4_measurement_id()
    if not measurement_id:
        return

    safe_measurement_id = html.escape(measurement_id, quote=True)
    components.html(
        f"""
        <!-- Google tag (gtag.js) -->
        <div style="width:1px;height:1px;overflow:hidden;opacity:0;" aria-hidden="true"></div>
        <script async src="https://www.googletagmanager.com/gtag/js?id={safe_measurement_id}"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}

          const pageLocation = document.referrer || window.location.href;
          gtag('js', new Date());
          gtag('config', '{safe_measurement_id}', {{
            page_title: 'AI Data Analyst Workbench',
            page_location: pageLocation,
            page_path: '/',
            transport_type: 'beacon',
            send_page_view: true
          }});
          gtag('event', 'streamlit_app_opened', {{
            event_category: 'engagement',
            event_label: 'AI Data Analyst Workbench',
            transport_type: 'beacon'
          }});
        </script>
        """,
        height=1,
        width=1,
    )


def send_ga4_event(event_name: str, params: dict | None = None, once_key: str | None = None) -> bool:
    measurement_id = get_ga4_measurement_id()
    api_secret = get_ga4_api_secret()
    if not measurement_id or not api_secret:
        return False

    if st.query_params.get("keepalive"):
        return False

    if once_key and st.session_state.get(once_key):
        return True

    if "ga4_client_id" not in st.session_state:
        st.session_state["ga4_client_id"] = str(uuid.uuid4())
    if "ga4_session_id" not in st.session_state:
        st.session_state["ga4_session_id"] = str(int(time.time()))

    event_params = {
        "session_id": st.session_state["ga4_session_id"],
        "engagement_time_msec": 100,
    }
    if params:
        event_params.update(params)

    payload = {
        "client_id": st.session_state["ga4_client_id"],
        "events": [
            {
                "name": event_name,
                "params": event_params,
            },
        ],
    }
    query = urllib.parse.urlencode({"measurement_id": measurement_id, "api_secret": api_secret})
    url = f"https://www.google-analytics.com/mp/collect?{query}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=3):
            if once_key:
                st.session_state[once_key] = True
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        if once_key:
            st.session_state[once_key] = False
        return False


def send_ga4_server_page_view() -> None:
    send_ga4_event(
        "page_view",
        {
            "page_title": "AI Data Analyst Workbench",
            "page_location": "https://ai-data-analyst-agent-hc3rs5gwg8nxvyru2qjz3q.streamlit.app/",
            "page_path": "/",
        },
        once_key="ga4_server_page_view_sent",
    )
    send_ga4_event("streamlit_app_opened", once_key="ga4_server_app_opened_sent")


def extract_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))


def build_supervisor_prompt(question: str, metadata: str, columns: str) -> str:
    return f"""
You are the supervisor agent inside a SQL-grounded AI Data Analyst Workbench.

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
8. For propose_new_analysis, provide a draft SQL query using only {DATA_SQL_REFERENCE} and available columns. This SQL is for review only and will not be executed automatically.
9. Do not invent data or findings.
10. If action is not "run_workflow", set query_key to "unsupported" and provide helpful suggested questions or a proposed analysis.

Workflow library:
{metadata}

Available dataset columns:
{columns}

User question:
{question}

Return only valid JSON. Do not include markdown, comments, or extra text.

JSON schema:
{{
  "action": "run_workflow | suggest_analysis_plan | ask_clarification | propose_new_analysis | unsupported",
  "query_key": "one workflow_key from the library if action is run_workflow, otherwise unsupported",
  "confidence": 0.0,
  "reasoning": "one short plain-English sentence",
  "user_message": "a helpful message to show the user",
  "suggested_questions": ["3 to 5 concrete questions the user could ask next"],
  "proposed_analysis": {{
    "title": "short title for the proposed analysis",
    "required_columns": ["columns needed for the proposed analysis"],
    "draft_sql": "read-only draft SQL using the configured CSV source",
    "status": "Proposed only. Not executed automatically."
  }}
}}
"""


def gemini_supervisor(question: str) -> dict[str, str | float]:
    api_key = get_gemini_api_key()
    if not api_key:
        fallback = deterministic_supervisor(question)
        fallback["supervisor"] = "Rule-based Mode fallback"
        fallback["reasoning"] += " Guided AI Mode was selected, but no GEMINI_API_KEY was configured."
        return fallback

    try:
        from google import genai
    except ImportError:
        fallback = deterministic_supervisor(question)
        fallback["supervisor"] = "Rule-based Mode fallback"
        fallback["reasoning"] += " Guided AI Mode was selected, but the google-genai package is not installed."
        return fallback

    metadata = json.dumps(workflow_metadata(), indent=2)
    columns = json.dumps(dataset_column_metadata(), indent=2)
    prompt = build_supervisor_prompt(question, metadata, columns)

    try:
        client = genai.Client(api_key=api_key)
        model_name = get_gemini_model()
        response = client.models.generate_content(model=model_name, contents=prompt)
        decision = extract_json_object(response.text)
        action = decision.get("action", "ask_clarification")
        if action not in {"run_workflow", "suggest_analysis_plan", "ask_clarification", "propose_new_analysis", "unsupported"}:
            action = "ask_clarification"

        query_key = decision.get("query_key", "unsupported")
        if action != "run_workflow":
            query_key = "unsupported"
        elif query_key not in QUERY_LIBRARY:
            query_key = "unsupported"
            action = "ask_clarification"

        suggested_questions = decision.get("suggested_questions", DEFAULT_SUGGESTED_QUESTIONS)
        if not isinstance(suggested_questions, list) or not suggested_questions:
            suggested_questions = DEFAULT_SUGGESTED_QUESTIONS

        return {
            "action": action,
            "query_key": query_key,
            "supervisor": f"Guided AI Mode ({model_name})",
            "confidence": float(decision.get("confidence", 0.5)),
            "reasoning": str(decision.get("reasoning", "Gemini selected this workflow.")),
            "user_message": str(decision.get("user_message", "")),
            "suggested_questions": [str(item) for item in suggested_questions[:5]],
            "proposed_analysis": decision.get("proposed_analysis", {}),
        }
    except Exception as exc:
        fallback = deterministic_supervisor(question)
        fallback["supervisor"] = "Rule-based Mode fallback"
        fallback["reasoning"] += f" Guided AI Mode failed safely: {exc}"
        return fallback


def supervisor_decision(question: str, mode: str) -> dict[str, str | float]:
    if mode == GUIDED_AI_MODE:
        return gemini_supervisor(question)
    return deterministic_supervisor(question)


def build_interpreter_prompt(question: str, workflow: dict, sql: str, result: pd.DataFrame, context: dict) -> str:
    result_preview = result.head(20).to_dict(orient="records")
    return f"""
You are the interpreter agent inside a SQL-grounded AI Data Analyst Workbench.

Product context:
- The app is built for non-technical business stakeholders.
- DuckDB has already executed a trusted SQL workflow.
- You must explain only what is supported by the SQL result.
- Do not invent numbers, columns, causes, or recommendations not grounded in the result.
- Do not claim causality. Use cautious language such as "suggests", "is associated with", or "should be investigated".

User question:
{question}

Selected workflow:
{workflow["title"]} - {workflow["description"]}

Data context:
{json.dumps(context, indent=2)}

SQL executed:
{sql}

Result preview:
{json.dumps(result_preview, indent=2, default=str)}

Return only valid JSON. Do not include markdown, comments, or extra text.

JSON schema:
{{
  "interpretation": "2 to 4 plain-English sentences explaining the key insight from the result",
  "next_steps": ["2 to 4 recommended follow-up analyses or business actions"],
  "suggested_questions": ["2 to 4 concrete follow-up questions the user could ask next"]
}}
"""


def gemini_interpret_result(question: str, query_key: str, sql: str, result: pd.DataFrame, context: dict) -> dict:
    api_key = get_gemini_api_key()
    if not api_key:
        return {
            "interpretation": build_interpretation(query_key, result),
            "next_steps": build_next_steps(query_key),
            "suggested_questions": [],
            "source": "Deterministic interpretation fallback",
        }

    try:
        from google import genai
    except ImportError:
        return {
            "interpretation": build_interpretation(query_key, result),
            "next_steps": build_next_steps(query_key),
            "suggested_questions": [],
            "source": "Deterministic interpretation fallback",
        }

    try:
        workflow = QUERY_LIBRARY[query_key]
        prompt = build_interpreter_prompt(question, workflow, sql, result, context)
        client = genai.Client(api_key=api_key)
        model_name = get_gemini_model()
        response = client.models.generate_content(model=model_name, contents=prompt)
        parsed = extract_json_object(response.text)
        next_steps = parsed.get("next_steps", build_next_steps(query_key))
        suggested_questions = parsed.get("suggested_questions", [])
        if not isinstance(next_steps, list) or not next_steps:
            next_steps = build_next_steps(query_key)
        if not isinstance(suggested_questions, list):
            suggested_questions = []
        return {
            "interpretation": str(parsed.get("interpretation") or build_interpretation(query_key, result)),
            "next_steps": [str(item) for item in next_steps[:4]],
            "suggested_questions": [str(item) for item in suggested_questions[:4]],
            "source": f"Gemini interpreter ({model_name})",
        }
    except Exception as exc:
        return {
            "interpretation": build_interpretation(query_key, result),
            "next_steps": build_next_steps(query_key),
            "suggested_questions": [],
            "source": f"Deterministic interpretation fallback: {exc}",
        }


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
        f"This prototype uses the available columns in {DATA_SOURCE_NAME} and does not infer causes beyond the observed data.",
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
        "data_source": DATA_SOURCE_NAME,
        "query_engine": "DuckDB",
        "table_reference": DATA_SQL_REFERENCE,
        "dataset_domain": "Hotel booking records",
        "row_count": int(row_count),
        "column_count": len(profile),
        "available_columns": profile["column_name"].tolist(),
        "fields_used": required_columns,
    }


def create_report_package(question: str, decision: dict[str, str | float]) -> dict:
    action = str(decision.get("action", "run_workflow"))
    query_key = str(decision["query_key"])
    if action != "run_workflow" or query_key == "unsupported":
        titles = {
            "suggest_analysis_plan": "Suggested Analysis Plan",
            "ask_clarification": "Clarification Needed",
            "propose_new_analysis": "Proposed New Analysis",
            "unsupported": "Unsupported Question",
        }
        descriptions = {
            "suggest_analysis_plan": "The user asked for analysis guidance, so the supervisor suggested useful starting questions.",
            "ask_clarification": "The user request is broad, so the supervisor suggested clearer analytical directions.",
            "propose_new_analysis": "The supervisor proposed a new analysis using available fields. The draft SQL is not executed automatically.",
            "unsupported": "The question cannot be answered from the current dataset or workflow coverage.",
        }
        return {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "question": question,
            "decision": decision,
            "query_key": query_key,
            "workflow_title": titles.get(action, "Clarification Needed"),
            "workflow_description": descriptions.get(action, "The supervisor did not run a SQL workflow."),
            "sql": "",
            "result": pd.DataFrame(),
            "interpretation": str(decision.get("user_message") or "No SQL workflow was run for this request."),
            "interpretation_source": "Supervisor guidance",
            "data_context": build_data_context(query_key),
            "limitations": build_limitations(query_key),
            "next_steps": build_next_steps(query_key),
            "suggested_questions": decision.get("suggested_questions", DEFAULT_SUGGESTED_QUESTIONS),
            "proposed_analysis": decision.get("proposed_analysis", {}),
        }

    query = QUERY_LIBRARY[query_key]
    result = run_sql(query["sql"])
    sql = query["sql"].strip()
    context = build_data_context(query_key)
    if str(decision.get("supervisor", "")).startswith(GUIDED_AI_MODE):
        insight = gemini_interpret_result(question, query_key, sql, result, context)
    else:
        insight = {
            "interpretation": build_interpretation(query_key, result),
            "next_steps": build_next_steps(query_key),
            "suggested_questions": decision.get("suggested_questions", []),
            "source": "Deterministic interpretation",
        }

    return {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
        "decision": decision,
        "query_key": query_key,
        "workflow_title": query["title"],
        "workflow_description": query["description"],
        "sql": sql,
        "result": result,
        "interpretation": insight["interpretation"],
        "interpretation_source": insight["source"],
        "data_context": context,
        "limitations": build_limitations(query_key),
        "next_steps": insight["next_steps"],
        "suggested_questions": insight["suggested_questions"],
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
    suggested_questions_html = "".join(
        f"<li>{html.escape(str(item))}</li>" for item in report.get("suggested_questions", [])
    )
    suggested_questions_section = (
        f"<h2>Suggested Questions</h2>\n  <ul>{suggested_questions_html}</ul>"
        if suggested_questions_html
        else ""
    )
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
    <p><strong>Analysis mode:</strong> {html.escape(str(decision.get("supervisor", "")))}</p>
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
  <p><strong>Interpretation source:</strong> {html.escape(str(report.get("interpretation_source", "Unknown")))}</p>
  <div class="finding">{html.escape(report["interpretation"])}</div>

  <h2>SQL Evidence</h2>
  <pre><code>{sql_html}</code></pre>

  <h2>Result Table</h2>
  {table_html}

  <h2>Limitations</h2>
  <ul>{limitations_html}</ul>

  <h2>Recommended Next Steps</h2>
  <ul>{next_steps_html}</ul>

  {suggested_questions_section}
</body>
</html>
"""


def render_download_button(report: dict, key: str) -> None:
    file_slug = re.sub(r"[^a-z0-9]+", "-", report["workflow_title"].lower()).strip("-")
    downloaded = st.download_button(
        "Download HTML Report",
        data=build_report_html(report),
        file_name=f"{file_slug or 'analysis'}-report.html",
        mime="text/html",
        key=key,
    )
    if downloaded:
        send_ga4_event(
            "html_report_downloaded",
            {
                "workflow_key": str(report.get("query_key", "unknown")),
                "workflow_title": str(report.get("workflow_title", "Unknown")),
            },
        )


def is_downloadable_report(report: dict) -> bool:
    result = report.get("result")
    return (
        report["decision"].get("action", "run_workflow") == "run_workflow"
        and bool(report.get("sql"))
        and isinstance(result, pd.DataFrame)
        and not result.empty
    )


def submit_question(question: str, supervisor_mode: str) -> None:
    decision = supervisor_decision(question, supervisor_mode)
    report = create_report_package(question, decision)
    send_ga4_event(
        "analysis_question_submitted",
        {
            "analysis_mode": supervisor_mode,
            "action": str(decision.get("action", "unknown")),
            "workflow_key": str(decision.get("query_key", "unsupported")),
        },
    )
    if supervisor_mode == GUIDED_AI_MODE:
        send_ga4_event(
            "guided_ai_mode_used",
            {
                "action": str(decision.get("action", "unknown")),
                "workflow_key": str(decision.get("query_key", "unsupported")),
            },
        )
    if decision.get("action") == "run_workflow":
        send_ga4_event(
            "analysis_workflow_run",
            {
                "analysis_mode": supervisor_mode,
                "workflow_key": str(decision.get("query_key", "unsupported")),
                "workflow_title": str(report.get("workflow_title", "Unknown")),
            },
        )
    elif decision.get("action") == "propose_new_analysis":
        send_ga4_event(
            "new_analysis_proposed",
            {
                "analysis_mode": supervisor_mode,
                "workflow_key": str(decision.get("query_key", "unsupported")),
            },
        )
    if is_downloadable_report(report):
        st.session_state.latest_report = report
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append(
        {
            "role": "assistant",
            "query_key": decision["query_key"],
            "decision": decision,
            "report": report,
        }
    )


def render_suggested_question_buttons(suggestions: list[str], supervisor_mode: str, key_prefix: str) -> None:
    if not suggestions:
        return

    st.write("Suggested questions to try next:")
    for index, item in enumerate(suggestions):
        question = str(item)
        if st.button(question, key=f"{key_prefix}_{index}", use_container_width=True):
            submit_question(question, supervisor_mode)
            st.rerun()


def render_report(report: dict) -> None:
    query_key = report["query_key"]
    result = report["result"]

    if report["decision"].get("action", "run_workflow") != "run_workflow" or query_key == "unsupported":
        st.caption(f"Interpretation source: {report.get('interpretation_source', 'Supervisor guidance')}")
        st.info(report["interpretation"])
        if report["decision"].get("action") == "suggest_analysis_plan":
            st.write("Suggested 1-2 step path:")
            st.write("1. Establish the baseline with an overview metric.")
            st.write("2. Compare the most likely drivers or segments.")
        if report["decision"].get("action") == "propose_new_analysis":
            proposal = report.get("proposed_analysis", {})
            st.write("Proposed analysis:")
            st.write(f"**Title:** {proposal.get('title', 'Untitled proposed analysis')}")
            required_columns = proposal.get("required_columns", [])
            if required_columns:
                st.write("**Fields needed:** " + ", ".join(str(column) for column in required_columns))
            st.warning(proposal.get("status", "Proposed only. Not executed automatically."))
            with st.expander("Draft SQL for review"):
                st.code(proposal.get("draft_sql", "No draft SQL was generated."), language="sql")
        suggestions = report.get("suggested_questions", DEFAULT_SUGGESTED_QUESTIONS)
        if suggestions:
            render_suggested_question_buttons(
                suggestions,
                st.session_state.get("supervisor_mode", SUPERVISOR_MODES[0]),
                f"suggested_{id(report)}",
            )
        return

    st.caption(report["workflow_description"])

    if query_key == "cancellation_overview" and not result.empty:
        row = result.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Bookings", f"{int(row['total_bookings']):,}")
        col2.metric("Cancelled Bookings", f"{int(row['cancelled_bookings']):,}")
        col3.metric("Cancellation Rate", f"{row['cancellation_rate_pct']}%")
        col4.metric("Average ADR", f"{row['avg_adr']}")

    st.caption(f"Interpretation source: {report.get('interpretation_source', 'Unknown')}")
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


def render_latest_report_section() -> None:
    st.subheader("Generated Report")
    latest_report = st.session_state.latest_report
    if latest_report:
        st.write(f"**Question:** {latest_report['question']}")
        st.write(f"**Workflow:** {latest_report['workflow_title']}")
        st.write(f"**Analysis mode:** {latest_report['decision'].get('supervisor')}")
        st.write(f"**Interpretation source:** {latest_report.get('interpretation_source', 'Unknown')}")
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


st.set_page_config(page_title="AI Data Analyst Workbench", layout="wide")
render_ga4_tracking()
send_ga4_server_page_view()

st.title("AI Data Analyst Workbench")
st.caption("Governed AI workflow for stakeholder self-service analytics.")
st.markdown(
    "**Built by Nuonan (Juana) Zhang** · "
    "LinkedIn: [www.linkedin.com/in/juanazhang](https://www.linkedin.com/in/juanazhang/) · "
    "GitHub: [github.com/Juana-Zhang/ai-data-analyst-agent](https://github.com/Juana-Zhang/ai-data-analyst-agent)"
)
st.info(
    "**How to use this demo**\n\n"
    "1. Use **Rule-based Mode** for structured, recurring stakeholder questions.\n\n"
    "2. Use **Guided AI Mode** for exploratory questions, onboarding, or unclear analysis needs.\n\n"
    "3. Review SQL evidence and download an executive report after an approved workflow runs."
)

if not DATA_PATH.exists():
    st.error("No dataset was found. Add data.csv for local analysis or sample_data.csv for a public demo.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "latest_report" not in st.session_state:
    st.session_state.latest_report = None

with st.sidebar:
    st.header("Workbench")
    st.subheader("Data Source")
    data_source_mode = st.radio("Source mode", ["Local CSV demo", "Company database preview"])
    if data_source_mode == "Local CSV demo":
        st.write(f"Data source: `{DATA_SOURCE_NAME}`")
        st.caption("Domain: synthetic sample business dataset")
    else:
        st.write("Status: preview only")
        st.caption("Future connectors: PostgreSQL, Snowflake, BigQuery, Redshift")

    st.divider()
    st.subheader("Analysis Mode")
    supervisor_mode = st.radio("Choose how questions are routed", SUPERVISOR_MODES)
    st.session_state.supervisor_mode = supervisor_mode
    selected_question = st.selectbox("Business question templates", list(QUESTION_TEMPLATES.keys()))

    if st.button("Run Template", use_container_width=True):
        submit_question(selected_question, supervisor_mode)

    st.divider()
    st.subheader("Routing Logic")
    st.write("Rule-based Mode runs stable predefined workflows.")
    st.write("Guided AI Mode uses Gemini to clarify vague questions, suggest analysis paths, or route to trusted workflows.")

    st.divider()
    st.subheader("Integration Preview")
    integration_mode = st.radio("Interface", ["Streamlit UI", "API endpoint", "Slack / Teams"])
    if integration_mode == "Streamlit UI":
        st.caption("Current demo interface for interactive analysis.")
    elif integration_mode == "API endpoint":
        st.caption("Future pattern: POST /analyze for internal apps and BI portals.")
    else:
        st.caption("Future pattern: ask questions from Slack or Teams and receive report links.")

overview_tab, profile_tab, library_tab, report_tab = st.tabs(
    ["Ask Data", "Dataset Profile", "Workflow Library", "Executive Brief"]
)

with overview_tab:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                decision = message.get("decision")
                report = message.get("report")
                if decision:
                    st.write(f"Analysis mode: **{decision['supervisor']}**")
                    st.caption(f"Confidence: {decision['confidence']}")
                    st.caption(f"Action: {decision.get('action', 'run_workflow')}")
                    st.write(decision["reasoning"])
                if not report:
                    report = create_report_package(message.get("content", ""), decision)
                    message["report"] = report
                if decision.get("action", "run_workflow") == "run_workflow":
                    st.write(f"Selected analysis: **{report['workflow_title']}**")
                    with st.expander("SQL used"):
                        st.code(report["sql"], language="sql")
                else:
                    st.write(f"Supervisor guidance: **{report['workflow_title']}**")
                render_report(report)
                if is_downloadable_report(report):
                    render_download_button(report, key=f"download_{id(message)}")

    prompt = st.chat_input("Ask your data...", key="ask_data_prompt")

    if prompt:
        submit_question(prompt, supervisor_mode)
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
        "the limitation or guides the user toward concrete analysis questions instead of forcing an unreliable answer."
    )

with report_tab:
    st.subheader("Project Goal")
    st.write(
        "This project demonstrates how AI can support repetitive, structured analytics work for "
        "cross-functional teams. In many business settings, stakeholders frequently need SQL-based "
        "data pulls, KPI checks, recurring summaries, and report-ready outputs. Instead of asking "
        "analysts to rewrite similar SQL every time, analysts can pre-design trusted data extraction "
        "logic and analysis frameworks, then let an AI-guided interface help stakeholders access "
        "them through natural language."
    )
    st.write(
        "This demo uses one sample business domain dataset to illustrate the pattern. The approach "
        "can be adapted to other domains by replacing the schema metadata, metric definitions, and "
        "workflow library."
    )

    st.subheader("Build Approach")
    st.markdown(
        """
        <style>
          .workflow-frame {
            border: 1px solid rgba(120, 128, 140, 0.28);
            border-radius: 8px;
            padding: 18px;
            margin: 10px 0 22px;
            background: rgba(148, 163, 184, 0.08);
          }
          .workflow-row {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 10px;
            align-items: stretch;
          }
          .workflow-card {
            border: 1px solid rgba(120, 128, 140, 0.28);
            border-radius: 8px;
            padding: 12px;
            min-height: 116px;
            background: rgba(255, 255, 255, 0.04);
          }
          .workflow-kicker {
            color: #64748b;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
          }
          .workflow-title {
            font-size: 15px;
            font-weight: 750;
            margin-top: 6px;
          }
          .workflow-copy {
            color: #94a3b8;
            font-size: 13px;
            line-height: 1.45;
            margin-top: 8px;
          }
          .workflow-arrow {
            color: #ef4444;
            font-weight: 800;
          }
          .mode-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 14px;
          }
          .mode-card {
            border: 1px solid rgba(120, 128, 140, 0.28);
            border-radius: 8px;
            padding: 14px;
            background: rgba(15, 23, 42, 0.04);
          }
          @media (max-width: 900px) {
            .workflow-row, .mode-grid {
              grid-template-columns: 1fr;
            }
          }
        </style>
        <div class="workflow-frame">
          <div class="workflow-row">
            <div class="workflow-card">
              <div class="workflow-kicker">Step 1</div>
              <div class="workflow-title">Sample domain data</div>
              <div class="workflow-copy">Use a synthetic dataset to demonstrate the pattern without exposing private data.</div>
            </div>
            <div class="workflow-card">
              <div class="workflow-kicker">Step 2</div>
              <div class="workflow-title">Schema + metric understanding</div>
              <div class="workflow-copy">Inspect available fields and define what questions can be answered safely.</div>
            </div>
            <div class="workflow-card">
              <div class="workflow-kicker">Step 3</div>
              <div class="workflow-title">Analyst-defined framework</div>
              <div class="workflow-copy">Pre-design reusable SQL, metric logic, and analysis workflows before adding AI.</div>
            </div>
            <div class="workflow-card">
              <div class="workflow-kicker">Step 4</div>
              <div class="workflow-title">AI routing layer</div>
              <div class="workflow-copy">Clarify intent, suggest paths, or route questions to trusted workflows.</div>
            </div>
            <div class="workflow-card">
              <div class="workflow-kicker">Step 5</div>
              <div class="workflow-title">Evidence + report</div>
              <div class="workflow-copy">DuckDB runs approved SQL and returns interpretation, limitations, and report output.</div>
            </div>
          </div>
          <div class="mode-grid">
            <div class="mode-card">
              <div class="workflow-title">Rule-based Mode</div>
              <div class="workflow-copy">For structured, recurring stakeholder questions. Routes directly to predefined SQL workflows.</div>
            </div>
            <div class="mode-card">
              <div class="workflow-title">Guided AI Mode</div>
              <div class="workflow-copy">For onboarding, vague questions, or exploratory needs. AI helps users choose a safe path.</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Analysis Modes")
    st.table(
        pd.DataFrame(
            [
                {
                    "Mode": "Rule-based Mode",
                    "Best for": "Clear, repetitive business questions",
                    "What it does": "Routes directly to predefined SQL workflows",
                    "Control": "Fully deterministic and reproducible",
                },
                {
                    "Mode": "Guided AI Mode",
                    "Best for": "Vague questions, new stakeholders, or exploratory analysis needs",
                    "What it does": "Uses Gemini to clarify intent, suggest analysis paths, or select workflows",
                    "Control": "Constrained by schema metadata, workflow library, and approved SQL execution",
                },
            ]
        )
    )

    st.subheader("Why This Matters")
    value_col1, value_col2 = st.columns(2)
    with value_col1:
        st.markdown("**For stakeholders**")
        st.write(
            "- Ask business questions without writing SQL\n"
            "- Get consistent answers for recurring analysis needs\n"
            "- Use AI guidance when they are unsure where to start"
        )
    with value_col2:
        st.markdown("**For analysts**")
        st.write(
            "- Reuse trusted SQL and metric logic instead of rewriting repetitive queries\n"
            "- Keep control over definitions, schema assumptions, and data boundaries\n"
            "- Turn structured analysis work into a self-serve workflow"
        )

    st.subheader("Design Guardrails")
    st.table(
        pd.DataFrame(
            [
                {
                    "Risk": "Free-form LLM-to-SQL",
                    "Guardrail": "SQL execution is limited to approved workflows.",
                },
                {
                    "Risk": "Unsupported fields or hallucinated logic",
                    "Guardrail": "AI responses are grounded in available schema metadata and workflow coverage.",
                },
                {
                    "Risk": "Unreviewed new analysis",
                    "Guardrail": "New analyses can be proposed, but untrusted SQL is not automatically executed.",
                },
                {
                    "Risk": "Black-box answers",
                    "Guardrail": "Every completed analysis exposes SQL evidence, data context, limitations, and next steps.",
                },
                {
                    "Risk": "Private data or key exposure",
                    "Guardrail": "The public demo uses synthetic sample data; real data and API keys stay outside the repo.",
                },
            ]
        )
    )

    st.subheader("What This Demonstrates")
    st.write(
        "- Product thinking for non-technical analytics self-service\n"
        "- SQL framework design for structured and repetitive analysis work\n"
        "- AI workflow design with clear safety boundaries\n"
        "- DuckDB-based local analytics and transparent evidence generation\n"
        "- Executive reporting UX for decision support"
    )

    st.divider()
    render_latest_report_section()
