import streamlit as st

import recommender
import tutor
import ui

student_id = ui.setup_page("AI Tutor", "🧑‍🏫")
ui.hero("AI Tutor", "Ask a question, or review your own mistakes")

with st.sidebar:
    mode = st.radio("Tutor mode", ["Built-in (notes search)", "Local LLM (Ollama)"])
    model = st.text_input("Ollama model", tutor.DEFAULT_MODEL) if mode.startswith("Local") else None

use_llm = False
if mode.startswith("Local"):
    if tutor.llm_ready():
        use_llm = True
        st.success(f"Local LLM ready: {model}")
    else:
        st.warning("Ollama is not running or the `ollama` package is missing, so the "
                   "built-in tutor is used. See the setup steps in the project guide.")

st.info("The built-in tutor searches the question bank. The optional LLM is a small "
        "local model and can make mistakes, so check important answers in your notes.")

key = f"tutor_chat_{student_id}"
history = st.session_state.setdefault(key, [])

c1, c2, c3 = st.columns(3)
quick = None
if c1.button("🔍 Review my recent mistakes"):
    quick = "__mistakes__"
if c2.button("🎯 What should I revise first?"):
    quick = "__revise__"
if c3.button("🧹 Clear chat"):
    st.session_state[key] = history = []

for m in history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Ask about Python, Data Structures or Computer Networks")

if quick == "__mistakes__":
    history.append({"role": "assistant", "content": tutor.mistakes_answer(student_id)})
    st.rerun()
elif quick == "__revise__":
    top = recommender.topics_needing_practice(ui.get_recs(student_id))[:3]
    text = ("Based on your results, revise these first:\n\n" + "\n".join(
        f"- **{r['topic']}** ({r['subject']}), priority {r['priority_level']}" for r in top)
        if top else "No topic needs practice right now. Take more quizzes to get advice.")
    history.append({"role": "assistant", "content": text})
    st.rerun()

if prompt:
    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        notes = tutor.retrieve(prompt)
        reply = None
        if use_llm:
            weak = [r["topic"] for r in
                    recommender.topics_needing_practice(ui.get_recs(student_id))[:3]]
            try:
                reply = st.write_stream(tutor.stream_llm(model, history, notes, weak))
            except Exception as error:
                st.warning(f"The local model failed ({error}). Using the built-in tutor.")
        if reply is None:
            reply = tutor.builtin_answer(prompt)
            st.markdown(reply)
    history.append({"role": "assistant", "content": reply})