import pandas as pd
import plotly.express as px
import streamlit as st

import database
import recommender
import ui
from quiz_data import get_subjects, get_topics

student_id = ui.setup_page("Dashboard", "📊")
student = database.get_student(student_id)
summary = database.get_summary(student_id)
recs = ui.get_recs(student_id)
needing = recommender.topics_needing_practice(recs)

ui.hero(f"Welcome back, {student['name']}", "Here is where you stand today.")

left, right = st.columns([1, 1])
with left:
    if summary["total_quizzes"]:
        ui.ring(summary["average_score"], "Average score",
                f"{summary['total_quizzes']} quizzes taken so far")
    else:
        ui.empty_state("No quizzes yet",
                       "Take your first quiz, or load demo data on the Home page.")
with right:
    if needing:
        top = needing[0]
        ui.next_up(f"Revise {top['topic']}",
                   f"{top['subject']} · priority {top['priority_level']}",
                   top["advice"])
        if st.button(f"Start a {top['recommended_difficulty']} quiz on this topic",
                     type="primary"):
            st.session_state["quiz_preselect"] = (
                top["subject"], top["topic"], top["recommended_difficulty"])
            st.switch_page("pages/2_Take_Quiz.py")
    elif summary["total_quizzes"]:
        ui.next_up("You are on track", "No topic needs urgent practice",
                   "Take a quiz now and then to stay sharp.")
    else:
        ui.next_up("Start here", "Step 1",
                   "Open Take Quiz and pick any topic to measure your level.")

c1, c2, c3 = st.columns(3)
with c1:
    ui.card("Topics needing practice", len(needing), "High or Medium priority",
            ui.CORAL if needing else ui.GREEN)
with c2:
    ui.card("Topics practised", f"{summary['topics_practiced']} of 9", "Across all subjects", ui.VIOLET)
with c3:
    ui.card("Last quiz", summary["last_activity"] or "None yet", "Date and time", ui.TEAL)

st.subheader("Progress by subject")
scores = database.get_topic_scores(student_id)
cols = st.columns(3)
for col, subject in zip(cols, get_subjects()):
    part = scores[scores["subject"] == subject]
    average = float(part["latest_score"].mean()) if len(part) else 0.0
    with col:
        st.markdown(f"**{subject}**")
        st.progress(min(max(average / 100, 0.0), 1.0))
        st.caption(f"Average of latest scores: {average:.0f}%. "
                   f"{len(part)} of {len(get_topics(subject))} topics practised."
                   if len(part) else "Not started yet.")

attempts_desc = database.get_attempts(student_id, limit=10)
if len(attempts_desc) >= 2:
    recent = attempts_desc.sort_values("taken_at")
    fig = px.line(recent, x="taken_at", y="percentage", markers=True,
                  hover_data=["subject", "topic"], title="Your last 10 quizzes",
                  labels={"taken_at": "Date", "percentage": "Score (%)"})
    fig.update_yaxes(range=[0, 105])
    ui.show_plot(fig)

st.subheader("Topics that need attention")
if needing:
    for r in needing[:5]:
        m, ml = r["measured"], r["ml"]
        st.markdown(f"**{r['topic']}** ({r['subject']}) {ui.priority_badge(r['priority_level'])}",
                    unsafe_allow_html=True)
        st.caption(f"Measured latest score: {m['latest_score']:.0f}%"
                   + (f". Model prediction: {ml['label']}." if ml else ""))
    st.caption("The Study Planner shows the reasons and your tasks.")
elif summary["total_quizzes"]:
    st.success("No topics need practice right now. Keep it up!")

st.subheader("Recent quizzes")
recent_attempts = database.get_attempts(student_id, limit=8)
if recent_attempts.empty:
    ui.empty_state("Nothing here yet", "Your finished quizzes will appear in this table.")
else:
    table = pd.DataFrame({
        "When": recent_attempts["taken_at"].dt.strftime("%d %b %Y, %H:%M"),
        "Subject": recent_attempts["subject"],
        "Topic": recent_attempts["topic"],
        "Difficulty": recent_attempts["difficulty"],
        "Score": recent_attempts["score"].astype(str) + "/" + recent_attempts["total"].astype(str),
        "Percent": recent_attempts["percentage"].round(1),
        "Type": ["Demo" if d == 1 else "Real" for d in recent_attempts["is_demo"]],
    })
    st.dataframe(table, hide_index=True)

st.subheader("Recent activity")
history = database.get_history(student_id, limit=8)
if history.empty:
    ui.empty_state("No activity yet", "Quizzes, completed tasks and resets will be listed here.")
else:
    st.dataframe(history.rename(columns={"event_type": "Event", "details": "Details",
                                         "created_at": "When"})[["When", "Event", "Details"]],
                 hide_index=True)