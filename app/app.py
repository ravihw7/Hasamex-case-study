import streamlit as st
from pipeline import (
    load_all_segments,
    get_verified_answer_for_call,
    get_theme_across_calls,
    ask_free_question,
    GUIDE_QUESTIONS,
    FILE_MAP,
)

st.set_page_config(page_title="Expert Call Analyzer", layout="wide")

# Cache so we don't re-parse files on every click
@st.cache_resource
def get_data():
    return load_all_segments()

all_segments, segments_by_call, segments_by_id = get_data()

st.title("🩺 Expert Call Analyzer")
st.caption("Robotic Surgery Market Research — 3 expert calls (France, Germany, UK)")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Interview Guide", "🔀 Themes & Disagreements", "💬 Ask Anything", "📄 Transcripts"]
)


def render_quote_block(quotes):
    if not quotes:
        st.caption("No quotes returned.")
        return
    for q in quotes:
        status = q["status"]
        if status == "verified":
            badge = "✅ Verified"
        elif status == "near_match":
            badge = "⚠️ Near-match (snapped to source)"
        else:
            badge = "❌ Rejected (could not verify — hidden from answer)"

        if status == "rejected":
            with st.expander(f"{badge}", expanded=False):
                st.write("*This quote could not be verified against the transcript and was excluded.*")
            continue

        st.markdown(
            f"> {q['display_quote']}\n\n"
            f"**{badge}** · {q.get('speaker','')} · `{q.get('call_id','')}` @ **{q.get('timestamp','')}**"
        )


# --- TAB 1: Interview Guide -------------------------------------------------
with tab1:
    st.subheader("Answers per question, per expert")
    question = st.selectbox("Choose a guide question:", GUIDE_QUESTIONS, key="guide_q")

    cols = st.columns(len(FILE_MAP))
    for col, call_id in zip(cols, FILE_MAP.keys()):
        expert_name = FILE_MAP[call_id][1]
        market = FILE_MAP[call_id][2]
        with col:
            st.markdown(f"### {expert_name}\n*{market}*")
            if st.button(f"Analyze {call_id}", key=f"btn_{call_id}_{question}"):
                with st.spinner("Analyzing..."):
                    result = get_verified_answer_for_call(
                        question, call_id, segments_by_call, segments_by_id
                    )
                if result["not_addressed"]:
                    st.info("Not addressed in this call.")
                else:
                    st.write(result["answer"])
                    render_quote_block(result["quotes"])

# --- TAB 2: Themes & Disagreements ------------------------------------------
with tab2:
    st.subheader("Cross-expert synthesis")
    theme_question = st.selectbox("Choose a question to compare across experts:", GUIDE_QUESTIONS, key="theme_q")
    if st.button("Compare all 3 experts"):
        with st.spinner("Analyzing all 3 calls and synthesizing..."):
            result = get_theme_across_calls(theme_question, segments_by_call, segments_by_id)

        theme = result["theme"]
        st.markdown(f"**Summary:** {theme.get('theme_summary','')}")
        if theme.get("agreement"):
            st.success(f"**Agreement:** {theme['agreement']}")
        if theme.get("disagreement"):
            st.warning(f"**Disagreement:** {theme['disagreement']}")

        st.divider()
        st.markdown("#### Per-expert detail")
        cols = st.columns(len(FILE_MAP))
        for col, call_id in zip(cols, FILE_MAP.keys()):
            with col:
                st.markdown(f"**{FILE_MAP[call_id][1]}**")
                per_call = result["per_call"][call_id]
                if per_call["not_addressed"]:
                    st.caption("Not addressed.")
                else:
                    st.write(per_call["answer"])
                    render_quote_block(per_call["quotes"])

# --- TAB 3: Ask Anything -----------------------------------------------------
with tab3:
    st.subheader("Ask a question across all 3 transcripts")
    user_q = st.text_input("Your question:", placeholder="e.g. Did any expert mention pricing pressure?")
    if st.button("Ask") and user_q.strip():
        with st.spinner("Searching transcripts..."):
            result = ask_free_question(user_q, all_segments, segments_by_id)
        if result["not_addressed"]:
            st.info("This wasn't addressed in any of the transcripts.")
        else:
            st.write(result["answer"])
            render_quote_block(result["quotes"])

# --- TAB 4: Transcripts -------------------------------------------------------
with tab4:
    st.subheader("Raw transcripts (for manual verification)")
    view_call = st.selectbox("Choose a call:", list(FILE_MAP.keys()), format_func=lambda c: FILE_MAP[c][1])
    for seg in segments_by_call[view_call]:
        st.markdown(f"**`{seg.timestamp}` {seg.speaker}:** {seg.text}")
