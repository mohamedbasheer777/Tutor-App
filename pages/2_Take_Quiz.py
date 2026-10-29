import streamlit as st

import database
import quiz_data
import recommender
import ui

student_id = ui.setup_page("Take Quiz", "📝")
ui.hero("Take a Quiz", "Choose a subject, topic and difficulty, then answer one question at a time")


def fresh_state():
    return {"quiz_stage": "setup", "quiz": [], "quiz_answers": {}, "quiz_index": 0,
            "quiz_meta": None, "quiz_result": None, "quiz_student": student_id}


def reset_quiz():
    for key, value in fresh_state().items():
        st.session_state[key] = value


if "quiz_stage" not in st.session_state:
    reset_quiz()
if "quiz_run" not in st.session_state:
    st.session_state["quiz_run"] = 0
if st.session_state["quiz_student"] != student_id:   # student changed in the sidebar
    reset_quiz()

# Coming from the Study Planner ("Start quiz on this topic")?
preselect = st.session_state.pop("quiz_preselect", None)
if preselect:
    reset_quiz()
    subject_pre, topic_pre, difficulty_pre = preselect
    st.session_state["setup_subject"] = subject_pre
    st.session_state[f"setup_topic_{subject_pre}"] = topic_pre
    st.session_state["setup_diff"] = difficulty_pre

stage = st.session_state["quiz_stage"]

# ======================================================================
# STAGE 1: choose the quiz
# ======================================================================
if stage == "setup":
    c1, c2, c3 = st.columns(3)
    subject = c1.selectbox("Subject", quiz_data.get_subjects(), key="setup_subject")
    topic = c2.selectbox("Topic", quiz_data.get_topics(subject), key=f"setup_topic_{subject}")
    difficulty = c3.selectbox("Difficulty", quiz_data.get_difficulties(), key="setup_diff",
                              help="Mixed uses Easy, Medium and Hard questions together.")

    features = database.get_topic_features(student_id, subject, topic)
    if features:
        suggestion = recommender.suggest_difficulty(features["latest_score"])
        st.info(f"Your latest score in this topic is {features['latest_score']:.0f}%. "
                f"Suggested difficulty: **{suggestion}**.")
    else:
        st.info("You have not practised this topic yet. A good start is Easy or Mixed.")

    pool = quiz_data.get_questions(subject, topic, difficulty)
    if len(pool) > 1:
        count = st.slider("Number of questions", 1, len(pool), len(pool),
                          key=f"setup_n_{subject}_{topic}_{difficulty}")
    else:
        count = len(pool)
    if difficulty != "Mixed":
        st.caption(f"{len(pool)} questions are available at this level. "
                   "Choose Mixed for a longer quiz and a more reliable score.")

    if st.button("▶ Start quiz", type="primary"):
        quiz = quiz_data.build_quiz(subject, topic, difficulty, count)
        st.session_state.update(
            quiz=quiz, quiz_answers={}, quiz_index=0, quiz_result=None,
            quiz_meta={"subject": subject, "topic": topic, "difficulty": difficulty},
            quiz_stage="quiz", quiz_student=student_id,
        )
        st.session_state["quiz_run"] += 1
        st.rerun()

# ======================================================================
# STAGE 2: answer questions one at a time
# ======================================================================
elif stage == "quiz":
    quiz = st.session_state["quiz"]
    meta = st.session_state["quiz_meta"]
    answers = st.session_state["quiz_answers"]
    i = st.session_state["quiz_index"]
    q = quiz[i]
    run = st.session_state["quiz_run"]

    st.markdown(f"**{meta['subject']} › {meta['topic']}** · {meta['difficulty']}")
    st.progress((i + 1) / len(quiz), text=f"Question {i + 1} of {len(quiz)}")
    st.markdown(f"### Q{i + 1}. {q['question']}")

    key = f"ans_{run}_{q['id']}"
    if key not in st.session_state and q["id"] in answers:   # coming back to a question
        st.session_state[key] = answers[q["id"]]
    choice = st.radio("Select your answer", [0, 1, 2, 3], index=None,
                      format_func=lambda k: q["options"][k], key=key,
                      label_visibility="collapsed")
    if choice is not None:
        answers[q["id"]] = choice

    st.caption(f"Answered {len(answers)} of {len(quiz)}")

    left, middle, right = st.columns(3)
    last = i == len(quiz) - 1

    if left.button("⬅ Previous", disabled=(i == 0)):
        st.session_state["quiz_index"] = i - 1
        st.rerun()
    if middle.button("✖ Cancel quiz"):
        reset_quiz()
        st.rerun()

    if not last:
        if right.button("Next ➡", type="primary"):
            st.session_state["quiz_index"] = i + 1
            st.rerun()
    else:
        if right.button("✅ Submit quiz", type="primary"):
            missing = [n + 1 for n, item in enumerate(quiz) if item["id"] not in answers]
            if missing:
                st.error("Please answer question(s) "
                         + ", ".join(map(str, missing)) + " before submitting.")
            else:
                try:
                    result = quiz_data.score_quiz(quiz, answers)
                    database.save_quiz_attempt(
                        student_id, meta["subject"], meta["topic"], meta["difficulty"],
                        result["score"], result["total"], result["details"])
                    ui.sync_tasks(student_id)          # recommendations update here
                    st.session_state["quiz_result"] = result
                    st.session_state["quiz_stage"] = "result"
                    st.rerun()
                except ValueError as error:
                    st.error(f"Your quiz could not be saved: {error}")

# ======================================================================
# STAGE 3: results and explanations
# ======================================================================
elif stage == "result":
    result = st.session_state["quiz_result"]
    meta = st.session_state["quiz_meta"]
    pct = result["percentage"]

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.card("Score", f"{result['score']} / {result['total']}", f"{meta['topic']}", "#2563eb")
    with c2:
        ui.card("Percentage", f"{pct:.1f}%", f"{meta['difficulty']} difficulty",
                "#059669" if pct >= 50 else "#dc2626")
    with c3:
        ui.card("Saved", "Yes ✔", "Stored in your local database", "#7c3aed")

    if pct >= 80:
        st.success("Excellent work!")
    elif pct >= 50:
        st.info("Good effort. Review the explanations below to improve further.")
    else:
        st.warning("This topic needs more practice. Read the explanations carefully.")

    st.subheader("Review your answers")
    for n, d in enumerate(result["details"], start=1):
        icon = "✅" if d["is_correct"] else "❌"
        with st.expander(f"{icon} Q{n}. {d['question']}", expanded=not d["is_correct"]):
            sel = d["selected_index"]
            st.markdown(f"Your answer: **{d['options'][sel] if sel is not None else 'Not answered'}**")
            st.markdown(f"Correct answer: **{d['options'][d['correct_index']]}**")
            st.info(f"💡 {d['explanation']}")

    st.subheader("What this means for your plan")
    recs = ui.get_recs(student_id)
    rec = next((r for r in recs if r["subject"] == meta["subject"]
                and r["topic"] == meta["topic"]), None)
    if rec:
        ui.render_rec_details(rec)

    b1, b2, b3 = st.columns(3)
    if b1.button("🔁 Retry this topic"):
        st.session_state["quiz_preselect"] = (meta["subject"], meta["topic"], meta["difficulty"])
        st.rerun()
    if b2.button("➕ Take a different quiz"):
        reset_quiz()
        st.rerun()
    if b3.button("🗓️ Open Study Planner"):
        st.switch_page("pages/3_Study_Planner.py")