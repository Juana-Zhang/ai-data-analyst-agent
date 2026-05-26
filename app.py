import duckdb
import streamlit as st


SQL = "SELECT * FROM read_csv_auto('data.csv') LIMIT 10;"


st.set_page_config(page_title="AI Data Analyst Workbench", layout="wide")

st.title("AI Data Analyst Workbench (Prototype)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if "data" in message:
            st.dataframe(message["data"], use_container_width=True)

prompt = st.chat_input("Ask your data...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    try:
        result = duckdb.sql(SQL).df()
        assistant_message = {
            "role": "assistant",
            "content": f"Executed fixed SQL: `{SQL}`",
            "data": result,
        }
    except Exception as exc:
        assistant_message = {
            "role": "assistant",
            "content": f"Error while running the DuckDB query: {exc}",
        }

    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        st.write(assistant_message["content"])
        if "data" in assistant_message:
            st.dataframe(assistant_message["data"], use_container_width=True)
