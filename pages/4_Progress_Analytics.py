import pandas as pd
import plotly.express as px
import streamlit as st

import database
import ui
from quiz_data import get_subjects

student_id = ui.setup_page("Progress Analytics", "📈")
ui.hero("Progress Analytics", "Topic scores, performance over time and task progress")

attempts = database.get_attempts(student_id)
if attempts.empty:
    st.info("No quiz data yet. Take a quiz, or load demo data on the Home page.")
    st.stop()

if attempts["is_demo"].any():
    st.info("Some attempts are demo data (see the Type column in the table at the bottom). "
            "You can remove them on the Home page.")

chosen = st.selectbox("Subject", ["All subjects"] + get_subjects())
asc = attempts.sort_values(["taken_at", "id"]).reset_index(drop=True)
scores = database.get_topic_scores(student_id)
if chosen != "All subjects":
    asc = asc[asc["subject"] == chosen]
    scores = scores[scores["subject"] == chosen]
if asc.empty:
    st.info("No attempts for this subject yet.")
    st.stop()

# ----------------------------------------------------------------------
st.subheader("Topic-wise scores")
long = scores.melt(id_vars=["subject", "topic"],
                   value_vars=["latest_score", "average_score", "best_score"],
                   var_name="Measure", value_name="Score (%)")
long["Measure"] = long["Measure"].map({"latest_score": "Latest", "average_score": "Average",
                                       "best_score": "Best"})
fig = px.bar(long, x="Score (%)", y="topic", color="Measure", orientation="h",
             barmode="group", range_x=[0, 100], height=max(380, 70 * len(scores) + 120),
             color_discrete_map={"Latest": "#2563eb", "Average": "#94a3b8", "Best": "#10b981"},
             labels={"topic": "Topic"})
fig.add_vline(x=50, line_dash="dash", line_color="#dc2626",
              annotation_text="50% line", annotation_position="top")
ui.show_plot(fig)

# ----------------------------------------------------------------------
st.subheader("Quiz performance over time")
fig = px.line(asc, x="taken_at", y="percentage", color="subject", markers=True,
              hover_data=["topic", "difficulty", "score", "total"],
              labels={"taken_at": "Date", "percentage": "Score (%)", "subject": "Subject"})
fig.update_yaxes(range=[0, 105])
ui.show_plot(fig)

# ----------------------------------------------------------------------
st.subheader("Recent performance vs earlier performance")
if len(asc) < 2:
    st.info("At least 2 attempts are needed for this comparison.")
else:
    max_recent = len(asc) - 1
    if max_recent > 1:
        n = st.slider("How many of your latest attempts count as 'recent'?",
                      1, max_recent, min(5, max(1, len(asc) // 2)))
    else:
        n = 1
    earlier, recent = asc.iloc[:-n], asc.iloc[-n:]
    earlier_avg, recent_avg = earlier["percentage"].mean(), recent["percentage"].mean()
    change = recent_avg - earlier_avg

    m1, m2, m3 = st.columns(3)
    m1.metric(f"Earlier average ({len(earlier)} attempts)", f"{earlier_avg:.1f}%")
    m2.metric(f"Recent average ({len(recent)} attempts)", f"{recent_avg:.1f}%")
    m3.metric("Change", f"{change:+.1f} points", delta=f"{change:+.1f}")

    if change >= 3:
        st.success("Your recent scores are higher than before. You are improving.")
    elif change <= -3:
        st.warning("Your recent scores are lower than before. Revise your weak topics.")
    else:
        st.info("Your recent performance is about the same as before.")

    comparison = pd.DataFrame({
        "Earlier": earlier.groupby("subject")["percentage"].mean(),
        "Recent": recent.groupby("subject")["percentage"].mean(),
    })
    comparison.index.name = "subject"
    comparison = comparison.reset_index().melt(id_vars="subject", var_name="Period",
                                               value_name="Average score (%)")
    fig = px.bar(comparison.dropna(), x="subject", y="Average score (%)", color="Period",
                 barmode="group", range_y=[0, 100],
                 color_discrete_map={"Earlier": "#94a3b8", "Recent": "#2563eb"},
                 labels={"subject": "Subject"})
    ui.show_plot(fig)
    st.caption("With few attempts these averages can change a lot from one quiz, so treat them as a guide.")

# ----------------------------------------------------------------------
st.subheader("Study tasks: completed vs pending")
pending = database.get_study_tasks(student_id, "Pending")
completed = database.get_study_tasks(student_id, "Completed")
if pending.empty and completed.empty:
    st.info("No study tasks yet. Open the Study Planner to generate them.")
else:
    t1, t2 = st.columns([1, 2])
    with t1:
        counts = pd.DataFrame({"Status": ["Completed", "Pending"],
                               "Tasks": [len(completed), len(pending)]})
        fig = px.pie(counts, names="Status", values="Tasks", hole=0.5, color="Status",
                     color_discrete_map={"Completed": "#10b981", "Pending": "#f59e0b"})
        ui.show_plot(fig)
    with t2:
        st.markdown("**Pending**")
        st.dataframe(pending[["subject", "topic", "description"]], hide_index=True)
        st.markdown("**Completed**")
        st.dataframe(completed[["topic", "description", "completed_at"]], hide_index=True)

with st.expander("All quiz attempts"):
    table = asc.sort_values("taken_at", ascending=False).copy()
    table["Type"] = ["Demo" if d == 1 else "Real" for d in table["is_demo"]]
    st.dataframe(table[["taken_at", "subject", "topic", "difficulty", "score", "total",
                        "percentage", "Type"]], hide_index=True)