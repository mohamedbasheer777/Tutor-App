"""
app.py - Home page: sign in / create account, then intro, demo data and reset.
Run with:  python -m streamlit run app.py
"""

import streamlit as st

import auth
import database
import ui

student_id = ui.setup_page("Home", "🎓", require_login=False)

ui.hero("AI-Powered Student Learning Companion",
        "An Adaptive Learning and Weak Topic Detection System")

# ======================================================================
# Not signed in: show sign-in and sign-up only (no list of students)
# ======================================================================
if student_id is None:
    st.markdown("Sign in to see your own quizzes, study plan and progress. "
                "Each account is private. Other students' names are never shown.")
    tab_in, tab_new = st.tabs(["🔐 Sign in", "🆕 Create account"])

    with tab_in:
        with st.form("login_form"):
            name = st.text_input("Name", max_chars=50)
            password = st.text_input("Password", type="password")
            go = st.form_submit_button("Sign in")
        if go:
            wait = auth.locked_seconds(st.session_state, "login")
            if wait:
                st.error(f"Too many wrong attempts. Please wait {wait} seconds.")
            else:
                try:
                    st.session_state["auth_student_id"] = auth.login_student(name, password)
                    auth.clear_failures(st.session_state, "login")
                    st.rerun()
                except ValueError as error:
                    auth.register_failure(st.session_state, "login")
                    st.error(str(error))
        st.caption("A profile created before passwords existed is claimed by the "
                   "first password entered for it.")

    with tab_new:
        with st.form("register_form"):
            new_name = st.text_input("Choose a name", max_chars=50)
            p1 = st.text_input(f"Choose a password ({auth.MIN_PASSWORD}+ characters)",
                               type="password")
            p2 = st.text_input("Repeat the password", type="password")
            create = st.form_submit_button("Create account")
        if create:
            if p1 != p2:
                st.error("The two passwords are different.")
            else:
                try:
                    st.session_state["auth_student_id"] = auth.register_student(new_name, p1)
                    ui.flash("success", f"Welcome, {new_name.strip()}! Your account was created.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    st.stop()

# ======================================================================
# Signed in
# ======================================================================
student = database.get_student(student_id)

st.markdown(
    f"Hello, **{student['name']}**! This app helps you find weak topics, practise "
    "with quizzes, follow a study plan and track progress. Everything runs on "
    "your laptop, with no internet, no API keys and no paid services."
)

st.subheader("How to use it")
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.card("Step 1", "Quiz", "Take a quiz on the Take Quiz page", "#2563eb")
with c2:
    ui.card("Step 2", "Detect", "The model flags topics that need practice", "#7c3aed")
with c3:
    ui.card("Step 3", "Plan", "Follow the Study Planner tasks", "#059669")
with c4:
    ui.card("Step 4", "Track", "Watch your progress in Analytics", "#d97706")

st.warning(
    "**About the machine learning model:** it is a Random Forest trained on "
    "**synthetic (computer-generated) data** until real student data is collected. "
    "Its scores show it learned that synthetic pattern, not that it is accurate for "
    "real students. It is not a large language model."
)

st.subheader("Demonstration data")
st.caption(
    "Demo data adds sample quiz attempts over the last 30 days so the charts and "
    "recommendations have something to show. Demo attempts are marked as demo, so "
    "removing them never touches your real attempts."
)
d1, d2 = st.columns(2)
if d1.button("📥 Load demo data for my account"):
    try:
        added = database.load_demo_data(student_id)
        ui.sync_tasks(student_id)
        ui.flash("success", f"{added} demo quiz attempts added.")
        st.rerun()
    except Exception as error:
        st.error(f"Could not load demo data: {error}")
if d2.button("🧹 Remove demo data only"):
    try:
        removed = database.clear_demo_data(student_id)
        ui.sync_tasks(student_id)
        ui.flash("success", f"{removed} demo attempts removed. Real attempts were kept.")
        st.rerun()
    except Exception as error:
        st.error(f"Could not remove demo data: {error}")

with st.expander("⚠️ Danger zone: delete ALL my learning data"):
    st.write("This deletes every quiz attempt, score, study task and history entry of "
             f"**{student['name']}**. The account itself is kept. This cannot be undone.")
    with st.form("reset_form", clear_on_submit=True):
        confirm = st.text_input("Type RESET to confirm")
        if st.form_submit_button("Delete all my learning data"):
            if confirm.strip() == "RESET":
                database.reset_student_data(student_id)
                ui.flash("success", "All your learning data was deleted.")
                st.rerun()
            else:
                st.error("Nothing was deleted. You must type RESET exactly.")

with st.expander("🗑️ Delete my account"):
    st.write("This permanently deletes your account and all its data.")
    with st.form("delete_form", clear_on_submit=True):
        confirm_del = st.text_input("Type DELETE to confirm")
        if st.form_submit_button("Delete my account permanently"):
            if confirm_del.strip() == "DELETE":
                auth.delete_student(student_id)
                st.session_state.clear()
                st.rerun()
            else:
                st.error("Nothing was deleted. You must type DELETE exactly.")

st.caption("Use the sidebar to open Dashboard, Take Quiz, Study Planner, "
           "Progress Analytics and Model Evaluation.")