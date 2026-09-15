"""Traceable Streamlit UI for the Day 04 IT Helpdesk Agent."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from chat import ROOT, run_model_tool_loop, trim_history
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version


ARTIFACTS = ROOT / "artifacts"
TRANSCRIPTS = ROOT / "transcripts"
load_lab_env(ROOT)


def save_ui_transcript() -> Path:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    path = TRANSCRIPTS / f"ui_v3_{datetime.now():%Y%m%dT%H%M%S%f}.transcript.json"
    payload = {"version": "v3", "created_at": datetime.now().isoformat(timespec="seconds"), "turns": st.session_state.turns}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    st.set_page_config(page_title="Northstar IT Helpdesk", page_icon="🛠️", layout="wide")
    st.title("Northstar IT Helpdesk Agent")
    with st.sidebar:
        provider_name = st.selectbox("Provider", ["openai", "openrouter", "anthropic", "gemini"])
        model = st.text_input("Model override (optional)") or None
        if st.button("Clear chat"):
            st.session_state.turns = []
            st.rerun()

    prompt_path, tools_path = ARTIFACTS / "system_prompt.md", ARTIFACTS / "tools.yaml"
    artifact_version = build_artifact_version("v3", prompt_path, tools_path)
    st.caption(f"Artifact version: `{artifact_version.artifact_version}`")
    if "turns" not in st.session_state:
        st.session_state.turns = []

    for turn in st.session_state.turns:
        with st.chat_message("user"):
            st.write(turn["user"])
        with st.chat_message("assistant"):
            st.write(turn["assistant_text"])
            with st.expander("Tool trace"):
                st.json({"status": turn["status"], "rounds": turn["rounds"], "tool_events": turn["tool_events"]})

    user_text = st.chat_input("Describe an IT helpdesk issue")
    if not user_text:
        return
    with st.chat_message("user"):
        st.write(user_text)

    history: list[dict[str, str]] = []
    for turn in st.session_state.turns:
        history.extend([{"role": "user", "content": turn["user"]}, {"role": "assistant", "content": turn["assistant_text"]}])
    try:
        provider = make_provider(provider_name)
        declarations = load_tool_declarations(tools_path)
        result = run_model_tool_loop(provider=provider, messages=[{"role": "system", "content": prompt_path.read_text(encoding="utf-8")}, *trim_history(history, 5), {"role": "user", "content": user_text}], tools=to_openai_tools(declarations), model=model, max_tool_rounds=4)
    except Exception as exc:
        result = {"status": "provider_error", "assistant_text": f"Provider error: {type(exc).__name__}: {exc}", "rounds": [], "tool_events": []}

    turn = {"user": user_text, **result}
    st.session_state.turns.append(turn)
    with st.chat_message("assistant"):
        st.write(result["assistant_text"])
        with st.expander("Tool trace", expanded=True):
            st.json({"status": result["status"], "rounds": result["rounds"], "tool_events": result["tool_events"]})
    st.caption(f"Transcript saved: `{save_ui_transcript().relative_to(ROOT)}`")


if __name__ == "__main__":
    main()
