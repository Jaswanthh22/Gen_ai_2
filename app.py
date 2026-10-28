"""Streamlit entry point for TalentVerse.

The original project also includes ``server.py`` for the local vanilla-JS
frontend. Streamlit Cloud should run this file instead of starting that raw
HTTP server inside Streamlit.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import streamlit as st


def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


# Streamlit Cloud exposes values from its Secrets panel through st.secrets.
# Populate the environment before importing the shared backend module because
# server.py reads its configuration at import time.
for _name in ("GEMINI_API_KEY", "GEMINI_MODEL"):
    if not os.environ.get(_name):
        _value = _secret(_name)
        if _value:
            os.environ[_name] = _value

import server as backend  # noqa: E402  (configuration must be set first)


st.set_page_config(page_title="TalentVerse", page_icon="✦", layout="wide")

MODES = {
    "Profile builder": ("profile", "Turn experience into a clear profile."),
    "Skill-gap map": ("gap", "See the next skill clearly."),
    "Role match": ("match", "Know where you stand."),
    "Portfolio brief": ("portfolio", "Turn curiosity into proof."),
    "Interview debrief": ("interview", "Practice with intention."),
}

SAMPLES = {
    "profile": "I am Aanya Sharma, a final-year computer science student who builds accessible React interfaces and Python data tools. I have completed two internships and a campus marketplace project. My core skills are JavaScript, React, Python, SQL, Figma and communication.",
    "gap": "I want to become a product data analyst in the next 6 months. I already know SQL, Excel, Python and basic statistics, but I need stronger Tableau, experimentation and stakeholder storytelling skills.",
    "match": "We are hiring a Junior Product Analyst. Requirements: SQL, dashboards, A/B testing, Python, communication and product sense. Candidate profile: Aanya has SQL, Python, Excel, React and strong communication, with one analytics internship.",
    "portfolio": "I enjoy climate tech, Python, data visualization and community problem solving. I want a project that demonstrates SQL, product thinking and a useful public impact.",
    "interview": "Practice notes: My STAR answer about leading a hackathon had a clear result and showed collaboration. I rambled during the conflict question and did not quantify the impact. I should practice concise stories and product metrics.",
}


def _show_value(value: object) -> None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                st.markdown(" · ".join(f"**{key}:** {val}" for key, val in item.items()))
            else:
                st.markdown(f"- {item}")
    elif isinstance(value, (int, float)):
        st.metric("Value", value)
    else:
        st.write(value)


def _show_result(result: dict[str, object]) -> None:
    columns = st.columns(2)
    for index, (key, value) in enumerate(result.items()):
        with columns[index % 2]:
            st.subheader(key.replace("_", " ").replace("yearsExperience", "Years of experience").title())
            _show_value(value)


def _save_record(analysis: dict[str, object]) -> None:
    backend.ensure_db()
    data = backend.read_db()
    record = {
        "id": str(uuid.uuid4()),
        "type": analysis["type"],
        "result": analysis["result"],
        "sourcePreview": str(analysis["input"])[:160],
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    data["records"].append(record)
    backend.write_db(data)


st.title("✦ TalentVerse")
st.caption("Skills and career intelligence from your own experience")

mode_label = st.sidebar.radio("Choose an analysis", list(MODES))
kind, description = MODES[mode_label]
st.sidebar.caption(description)

if "source_text" not in st.session_state:
    st.session_state.source_text = ""
if "analysis" not in st.session_state:
    st.session_state.analysis = None

if st.sidebar.button("Use sample input"):
    st.session_state.source_text = SAMPLES[kind]
    st.session_state.analysis = None
    st.rerun()

source = st.text_area(
    "Your input",
    key="source_text",
    height=220,
    placeholder="Describe your experience, skills, goals, or interview notes...",
)
st.caption(f"{len(source)} characters · minimum 20")

if st.button("Structure this input", type="primary"):
    if len(source.strip()) < 20:
        st.error("Please add at least 20 characters so TalentVerse can extract meaningful fields.")
    else:
        with st.spinner("Structuring your input..."):
            result, provider, warning = backend.extract(kind, source.strip())
        st.session_state.analysis = {
            "type": kind,
            "input": source.strip(),
            "result": result,
            "provider": provider,
            "warning": warning,
        }

analysis = st.session_state.analysis
if analysis and analysis["type"] == kind:
    st.divider()
    st.subheader("Structured result")
    validation = backend.validate(kind, analysis["result"])
    if validation["valid"]:
        st.success(f"Validated · {analysis['provider']}")
    else:
        st.warning("Needs review: " + "; ".join(validation["errors"]))
    if analysis["warning"]:
        st.info(analysis["warning"])
    _show_result(analysis["result"])
    if st.button("Save insight"):
        _save_record(analysis)
        st.success("Insight saved.")

with st.expander("Saved insights"):
    records = list(reversed(backend.read_db()["records"]))
    st.caption(f"{len(records)} saved insight{'s' if len(records) != 1 else ''}")
    if records:
        for record in records:
            result = record.get("result", {})
            title = result.get("title") or result.get("roleTitle") or result.get("goalRole") or result.get("name") or "Career insight"
            st.markdown(f"**{title}** · {record.get('type', '').title()}")
            st.caption(record.get("sourcePreview", ""))
    else:
        st.write("No saved insights yet.")
