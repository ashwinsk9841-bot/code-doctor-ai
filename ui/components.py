"""
Reusable UI components for Code Doctor AI.

These render consistent, themed Streamlit elements (cards, metrics, issue
views, code viewers, progress) so app.py stays clean and the look stays
consistent with the dark/gold identity.
"""
import streamlit as st

from config import Config

SEVERITY_LABEL = {
    "CRITICAL": ("🔴", "#ff5c5c"),
    "HIGH": ("🟠", "#ff9f43"),
    "MEDIUM": ("🟡", "#f5d061"),
    "LOW": ("🔵", "#5aa9ff"),
    "INFO": ("⚪", "#9aa0a6"),
}


def card(title: str = "", key=None):
    """Open a themed card container."""
    return st.container(border=False)


def metric_row(metrics: dict):
    """Render a row of metric cards with counts."""
    cols = st.columns(max(len(metrics), 1))
    for col, (label, value) in zip(cols, metrics.items()):
        with col:
            st.markdown(
                f"""
                <div class="cd-card cd-glow" style="text-align:center;">
                  <div style="font-size:2rem;font-weight:800;color:#f5d061;">{value}</div>
                  <div style="color:#8a8794;font-size:.85rem;letter-spacing:.5px;">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.write("")


def issue_card(issue: dict, index: int):
    """Render a single issue as an expandable card."""
    severity = issue.get("severity", "INFO")
    mark, color = SEVERITY_LABEL.get(severity, ("⚪", "#9aa0a6"))
    category = issue.get("category", "OTHER")
    cat_emoji = Config.CATEGORIES.get(category, "📋")
    title = issue.get("title", "Untitled issue")
    file = issue.get("file", "?")
    line = issue.get("line", "?")

    header = f"{mark} **#{index}** {cat_emoji} {title} — {severity} · `{file}:{line}`"

    with st.expander(header, expanded=severity in ("CRITICAL", "HIGH")):
        cols = st.columns(3)
        cols[0].markdown(f"**Category:** {category}")
        cols[1].markdown(f"**Severity:** <span style='color:{color}'>{severity}</span>", unsafe_allow_html=True)
        cols[2].markdown(f"**Confidence:** {issue.get('confidence', 'n/a')}")
        st.markdown(f"**Problem:**\n\n{issue.get('description', '')}")
        if issue.get("why_it_matters"):
            st.markdown(f"**Why it matters:** {issue['why_it_matters']}")
        if issue.get("evidence"):
            st.markdown("**Evidence:**")
            st.code(issue["evidence"], language="")
        if issue.get("recommended_fix"):
            st.markdown(f"**Recommended fix:**\n\n{issue['recommended_fix']}")
        ver = issue.get("verification_status", "NOT_VERIFIED")
        st.markdown(f"**Verification:** {ver}")
    return header


def code_view(record: dict, highlight_lines=None):
    """Render a file's source with line numbers."""
    content = (record.get("content") or "").split("\n")
    highlight_lines = set(highlight_lines or [])
    if not content:
        st.info("No source content available for this file.")
        return
    st.markdown(f"`{record.get('path')}` · {len(content)} lines")
    cols = st.columns([0.6, 9.4])
    with cols[0]:
        st.code("".join(f"{i}\n" for i in range(1, len(content) + 1)), language=None)
    with cols[1]:
        marked = []
        for i, line in enumerate(content, 1):
            if i in highlight_lines:
                marked.append(f"👉 {line}")
            else:
                marked.append(line)
        st.code("\n".join(marked), language=record.get("language", ""))
    st.write("")


def before_after(original: str, new: str, language: str = "python"):
    """Render original vs proposed fix side by side."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Before**")
        st.code(original, language=language)
    with col2:
        st.markdown("**After**")
        st.code(new, language=language)


def status_badge(status: str):
    colors = {"PASS": "#2ecc71", "FAIL": "#ff5c5c", "BLOCKED": "#f5d061", "NOT_VERIFIED": "#9aa0a6"}
    return f"**{status}** <span style='color:{colors.get(status, '#9aa0a6')}'>{status}</span>"


def progress_lines(stages: list):
    """Render the scanning progress checklist."""
    for done, label in stages:
        icon = "✅" if done else ("⏳" if not done and label else "○")
        st.markdown(f"{icon} {label}")


def section(title: str):
    st.markdown(f"<div class='cd-title'>{title}</div>", unsafe_allow_html=True)
    st.write("")
