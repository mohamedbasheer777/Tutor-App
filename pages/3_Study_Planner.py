import streamlit as st

import database
import recommender
import ui

student_id = ui.setup_page("Study Planner", "🗓️")
ui.hero("Personalized Study Planner", "What to revise first, based on your latest results")

recs = ui.sync_tasks(student_id)        # tasks always match the newest quiz results
pending = database.get_study_tasks(student_id, "Pending")
completed = database.get_study_tasks(student_id, "Completed")
needing = recommender.topics_needing_practice(recs)
practised = [r for r in recs if r["status"] == "Practised"]
total_tasks = len(pending) + len(completed)

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.card("Pending tasks", len(pending), "Still to do", "#d97706")
with c2:
    ui.card("Completed tasks", len(completed), "Well done", "#059669")
with c3:
    ui.card("Completion rate", f"{len(completed) / total_tasks * 100:.0f}%" if total_tasks else "-",
            "Completed / all tasks", "#2563eb")
with c4:
    ui.card("Topics needing practice", len(needing), "High or Medium priority", "#dc2626")

tab_tasks, tab_topics, tab_how = st.tabs(["✅ Study tasks", "🎯 Recommended topics", "ℹ️ How it works"])

# ----------------------------------------------------------------------
with tab_tasks:
    st.subheader("Pending tasks")
    if pending.empty:
        if not practised:
            st.info("Take your first quiz (or load demo data on the Home page) to get a study plan.")
        elif needing:
            st.info("All current tasks are done. Take a new quiz to check your progress. "
                    "New tasks appear if the topic is still weak.")
        else:
            st.success("You are on track in every practised topic. No tasks needed.")
    for task in pending.to_dict("records"):
        a, b = st.columns([6, 1])
        a.markdown(f"**{task['description']}**  \n"
                   f"{ui.badge(task['subject'] + ' › ' + task['topic'], 'badge-info')}",
                   unsafe_allow_html=True)
        a.caption(task["reason"])
        if b.button("✔ Done", key=f"done_{task['id']}"):
            database.complete_study_task(int(task["id"]))
            ui.flash("success", f"Completed: {task['description']}")
            st.rerun()

    with st.expander(f"Completed tasks ({len(completed)})"):
        if completed.empty:
            st.write("Nothing completed yet.")
        for task in completed.to_dict("records"):
            a, b = st.columns([6, 1])
            a.markdown(f"~~{task['description']}~~  \n*{task['topic']} · completed {task['completed_at']}*")
            if b.button("↩ Undo", key=f"undo_{task['id']}"):
                database.reopen_study_task(int(task["id"]))
                st.rerun()

# ----------------------------------------------------------------------
with tab_topics:
    st.subheader("Revision order")
    st.caption("Rank 1 = revise first. Measured scores, model predictions and rule points "
               "are shown in separate columns.")
    st.dataframe(recommender.recommendations_to_dataframe(recs), hide_index=True)

    st.subheader("Details and practice questions")
    for r in recs:
        title = f"#{r['rank']} · {r['topic']} ({r['subject']}) · {r['priority_level']}"
        with st.expander(title, expanded=(r["rank"] == 1 and r["priority_level"] in ("High", "Medium"))):
            st.markdown(ui.priority_badge(r["priority_level"]), unsafe_allow_html=True)
            ui.render_rec_details(r)
            st.markdown("**Suggested practice questions**")
            for pq in r["practice_questions"]:
                st.markdown(f"- {pq['question']}  \n  *{pq['difficulty']} · {pq['reason']}*")
            if st.button(f"▶ Start a {r['recommended_difficulty']} quiz on this topic",
                         key=f"startquiz_{r['subject']}_{r['topic']}"):
                st.session_state["quiz_preselect"] = (
                    r["subject"], r["topic"], r["recommended_difficulty"])
                st.switch_page("pages/2_Take_Quiz.py")

# ----------------------------------------------------------------------
with tab_how:
    st.markdown(
        "Each topic gets a **priority score**:\n\n"
        f"`priority score = rule points + {recommender.ML_WEIGHT} × P(Needs Practice)`\n\n"
        f"Score ≥ {recommender.HIGH_THRESHOLD} is **High**, ≥ {recommender.MEDIUM_THRESHOLD} is "
        f"**Medium**, otherwise **Low**. Topics never practised are listed as **Not started**."
    )
    st.markdown("**Rules**")
    st.table({"Rule": [r for r, _ in recommender.RULES_DESCRIPTION],
              "Points": [p for _, p in recommender.RULES_DESCRIPTION]})
    st.markdown(
        "**Three kinds of information are kept apart:**\n"
        "1. **Measured performance**: real scores saved from your quizzes.\n"
        "2. **Model prediction**: a Random Forest trained on synthetic data.\n"
        "3. **Rule-based advice**: the visible rules above.\n\n"
        f"Tasks are created for the top {recommender.MAX_TASK_TOPICS} High or Medium topics. "
        "A task you complete stays completed until you take a new quiz on that topic."
    )