import streamlit as st

import auth
import database
import ui

ui.setup_page("Owner", "🔑", require_login=False)
ui.hero("Owner Page", "Manage accounts. Protected by the owner password.")

# ---------- first-time setup ----------
if not auth.owner_exists():
    st.info("No owner password exists yet. Create it now, before anyone else opens "
            "this page. Whoever knows it can manage all accounts.")
    with st.form("owner_setup"):
        o1 = st.text_input("New owner password", type="password")
        o2 = st.text_input("Repeat owner password", type="password")
        go = st.form_submit_button("Create owner password")
    if go:
        if o1 != o2:
            st.error("The two passwords are different.")
        else:
            try:
                auth.set_owner_password(o1)
                st.session_state["owner_ok"] = True
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    st.stop()

# ---------- owner login ----------
if not st.session_state.get("owner_ok"):
    with st.form("owner_login"):
        pw = st.text_input("Owner password", type="password")
        go = st.form_submit_button("Open owner page")
    if go:
        wait = auth.locked_seconds(st.session_state, "owner")
        if wait:
            st.error(f"Too many wrong attempts. Please wait {wait} seconds.")
        elif auth.verify_owner(pw):
            auth.clear_failures(st.session_state, "owner")
            st.session_state["owner_ok"] = True
            st.rerun()
        else:
            auth.register_failure(st.session_state, "owner")
            st.error("Wrong owner password.")
    st.stop()

# ---------- owner dashboard ----------
if st.button("🔒 Lock owner page"):
    st.session_state["owner_ok"] = False
    st.rerun()

overview = auth.students_overview()
c1, c2, c3 = st.columns(3)
with c1:
    ui.card("Accounts", len(overview), "Registered students", "#2563eb")
with c2:
    ui.card("Quizzes taken", int(overview["quizzes"].sum()) if len(overview) else 0,
            "All accounts together", "#059669")
with c3:
    ui.card("Without password", int((overview["has_password"] == 0).sum()) if len(overview) else 0,
            "Old profiles not yet claimed", "#d97706")

st.subheader("Accounts")
if overview.empty:
    st.info("No accounts yet.")
    st.stop()

table = overview.copy()
table["Password set"] = ["Yes" if v else "No" for v in table["has_password"]]
st.dataframe(table.rename(columns={"name": "Name", "created_at": "Created",
                                   "quizzes": "Quizzes", "last_quiz": "Last quiz"})
             [["Name", "Created", "Quizzes", "Last quiz", "Password set"]], hide_index=True)
st.caption("Passwords are stored only as salted hashes, so nobody can read them. "
           "This page shows counts only, never quiz answers or scores.")

st.subheader("Manage one account")
chosen = st.selectbox("Account", list(overview["name"]))
sid = int(overview.loc[overview["name"] == chosen, "id"].iloc[0])
tab_pw, tab_data, tab_del = st.tabs(["🔑 New password", "🧹 Erase learning data", "🗑️ Delete account"])

with tab_pw:
    with st.form("owner_set_pw", clear_on_submit=True):
        new_pw = st.text_input(f"New password for {chosen}", type="password")
        if st.form_submit_button("Set password"):
            try:
                auth.set_student_password(sid, new_pw)
                st.success("Password changed. Tell the student the new password.")
            except ValueError as error:
                st.error(str(error))

with tab_data:
    with st.form("owner_erase", clear_on_submit=True):
        typed = st.text_input(f"Type RESET to erase all learning data of {chosen}")
        if st.form_submit_button("Erase learning data"):
            if typed.strip() == "RESET":
                database.reset_student_data(sid)
                st.success("Learning data erased. The account was kept.")
            else:
                st.error("Nothing was erased. Type RESET exactly.")

with tab_del:
    with st.form("owner_delete", clear_on_submit=True):
        typed = st.text_input(f"Type the name '{chosen}' to delete the account")
        if st.form_submit_button("Delete account permanently"):
            if typed.strip() == chosen:
                auth.delete_student(sid)
                st.session_state["_flash"] = ("success", f"Account '{chosen}' deleted.")
                st.rerun()
            else:
                st.error("Nothing was deleted. The name did not match.")

with st.expander("Change owner password"):
    with st.form("owner_change", clear_on_submit=True):
        a = st.text_input("New owner password", type="password")
        b = st.text_input("Repeat", type="password")
        if st.form_submit_button("Change owner password"):
            if a != b:
                st.error("The two passwords are different.")
            else:
                try:
                    auth.set_owner_password(a)
                    st.success("Owner password changed.")
                except ValueError as error:
                    st.error(str(error))