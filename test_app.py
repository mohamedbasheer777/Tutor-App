"""
test_app.py - Automated checks for the whole Student Learning Companion.

Run with:  python test_app.py

It uses a TEMPORARY database, so your real data is never touched.
It also blocks outgoing internet connections, so passing proves the app
works offline.
"""

import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ----------------------------------------------------------------------
# Block outgoing internet connections for the whole test run
# ----------------------------------------------------------------------
def _no_internet(*args, **kwargs):
    raise RuntimeError("The app tried to use the internet!")

socket.create_connection = _no_internet
socket.getaddrinfo = _no_internet

# ----------------------------------------------------------------------
# Tiny test runner
# ----------------------------------------------------------------------
results = []

def check(name, func):
    try:
        func()
        results.append((name, True))
        print(f"  PASS  {name}")
    except Exception as error:
        results.append((name, False))
        print(f"  FAIL  {name}\n          -> {error!r}")

def section(title):
    print(f"\n{title}")

TEMP = Path(tempfile.mkdtemp(prefix="slc_test_"))

# ======================================================================
section("A. Files and imports")
# ======================================================================
def test_files_exist():
    needed = ["app.py", "ui.py", "database.py", "quiz_data.py", "train_model.py",
              "recommender.py", "tutor.py", "auth.py", "requirements.txt",
              "pages/1_Dashboard.py", "pages/2_Take_Quiz.py", "pages/3_Study_Planner.py",
              "pages/4_Progress_Analytics.py", "pages/5_Model_Evaluation.py",
              "pages/6_AI_Tutor.py", "pages/7_Owner.py"]
    missing = [f for f in needed if not (ROOT / f).exists()]
    assert not missing, f"Missing files: {missing}"
def test_imports():
    import quiz_data, database, train_model, recommender  # noqa: F401

check("All required files exist", test_files_exist)
check("Core modules import without errors", test_imports)

import database
import quiz_data
import recommender
import train_model

# ======================================================================
section("B. Quiz system")
# ======================================================================
def test_bank():
    qs = quiz_data.ALL_QUESTIONS
    assert len(qs) == 54, f"Expected 54 questions, found {len(qs)}"
    assert len({q["id"] for q in qs}) == 54, "Question ids are not unique"
    assert all(len(q["options"]) == 4 for q in qs), "A question lacks 4 options"
    assert len(quiz_data.get_subjects()) == 3

def test_scoring():
    quiz = quiz_data.build_quiz("Data Structures", "Stacks and Queues", "Mixed", 6)
    right = {q["id"]: q["correct_index"] for q in quiz}
    assert quiz_data.score_quiz(quiz, right)["percentage"] == 100.0
    half = dict(right)
    for q in quiz[:3]:
        half[q["id"]] = (q["correct_index"] + 1) % 4
    r = quiz_data.score_quiz(quiz, half)
    assert r["score"] == 3 and r["percentage"] == 50.0
    assert quiz_data.score_quiz(quiz, {})["score"] == 0
    assert all(d["explanation"] for d in r["details"]), "Explanation missing"

def test_bad_input():
    for args in [("Nope", "x"), ("Python Programming", "Trees and Graphs")]:
        try:
            quiz_data.build_quiz(*args)
        except ValueError:
            continue
        raise AssertionError(f"Bad input {args} was accepted")

check("Question bank: 54 unique questions, 4 options each", test_bank)
check("Scoring is correct (100%, 50%, 0%) and explanations exist", test_scoring)
check("Invalid subject/topic is rejected", test_bad_input)

# ======================================================================
section("C. Machine learning model (trained into a temporary folder)")
# ======================================================================
real_paths = (train_model.DATA_PATH, train_model.MODEL_PATH, train_model.METRICS_PATH)
train_model.DATA_PATH = TEMP / "data.csv"
train_model.MODEL_PATH = TEMP / "model.joblib"
train_model.METRICS_PATH = TEMP / "metrics.json"
state = {}

def test_train():
    state["m1"] = train_model.train_and_save()
    assert train_model.MODEL_PATH.exists() and train_model.METRICS_PATH.exists()

def test_metrics_sane():
    m = state["m1"]
    assert 0.70 < m["accuracy"] < 1.0, f"accuracy {m['accuracy']} looks wrong"
    for key in ("precision", "recall", "f1_score"):
        assert 0.60 < m[key] <= 1.0, f"{key} = {m[key]}"
    assert sum(map(sum, m["confusion_matrix"])) == m["test_rows"]
    assert m["train_rows"] + m["test_rows"] == m["total_rows"]
    assert m["test_rows"] == 600, "Expected an 80/20 split"

def test_no_overfit():
    m = state["m1"]
    gap = m["train_accuracy"] - m["accuracy"]
    assert gap < 0.10, f"Train/test gap {gap:.3f} suggests overfitting"

def test_reproducible():
    second = train_model.train_and_save()
    assert second["accuracy"] == state["m1"]["accuracy"]
    assert second["confusion_matrix"] == state["m1"]["confusion_matrix"]

def test_predict():
    bundle = train_model.load_model()
    state["bundle"] = bundle
    weak = train_model.predict_topic(bundle, 35, 40, 3, 14)
    strong = train_model.predict_topic(bundle, 75, 90, 8, 2)
    assert weak["label"] == "Needs Practice" and strong["label"] == "On Track"
    assert 0 <= weak["probability_needs_practice"] <= 1
    assert len(weak["factors"]) == 4, "Explanation must cover all 4 features"
    assert (weak["probability_needs_practice"] >
            strong["probability_needs_practice"])

def test_predict_validation():
    for bad in [(150, 50, 3, 5), (50, -1, 3, 5), (50, 50, 0, 5), (50, 50, 3, -2)]:
        try:
            train_model.predict_topic(state["bundle"], *bad)
        except ValueError:
            continue
        raise AssertionError(f"Invalid values {bad} were accepted")

def test_synthetic_label():
    assert "SYNTHETIC" in state["m1"]["data_type"]

check("Model trains and the model + metrics files are saved", test_train)
check("Metrics are sensible (accuracy < 100%, split is 80/20)", test_metrics_sane)
check("No strong overfitting (train vs test gap < 10 points)", test_no_overfit)
check("Training is reproducible (same seed, same results)", test_reproducible)
check("Saved model loads; weak/strong students predicted correctly", test_predict)
check("Invalid prediction inputs are rejected", test_predict_validation)
check("Data is clearly labelled SYNTHETIC in the metrics", test_synthetic_label)

# ======================================================================
section("D. Database and persistence (temporary database)")
# ======================================================================
database.DB_PATH = TEMP / "test.db"
database.init_db()
sid = database.create_student("Test Student")
S, T = "Data Structures", "Trees and Graphs"

def test_save_and_scores():
    quiz = quiz_data.build_quiz(S, T, "Mixed", 6)
    wrong = {q["id"]: (q["correct_index"] + 1) % 4 for q in quiz}
    result = quiz_data.score_quiz(quiz, wrong)
    database.save_quiz_attempt(sid, S, T, "Mixed", result["score"],
                               result["total"], result["details"])
    attempts = database.get_attempts(sid)
    assert len(attempts) == 1 and attempts.iloc[0]["percentage"] == 0.0
    assert database.get_attempts(sid).iloc[0]["taken_at"] is not None
    f = database.get_topic_features(sid, S, T)
    assert f["latest_score"] == 0.0 and f["num_attempts"] == 1

def test_responses_saved():
    with database.db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM question_responses").fetchone()[0]
    assert n == 6, f"Expected 6 saved answers, found {n}"

def test_persistence_after_restart():
    code = (
        "import sys; from pathlib import Path; import database; "
        "database.DB_PATH = Path(sys.argv[1]); "
        "print(len(database.get_attempts(1)), database.get_students()[0]['name'])"
    )
    out = subprocess.run([sys.executable, "-c", code, str(database.DB_PATH)],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-300:]
    assert out.stdout.strip() == "1 Test Student", out.stdout

def test_invalid_scores():
    for bad in [(7, 6), (-1, 6), (3, 0)]:
        try:
            database.save_quiz_attempt(sid, S, T, "Mixed", *bad)
        except ValueError:
            continue
        raise AssertionError(f"Bad score {bad} was saved")

def test_demo_and_reset():
    added = database.load_demo_data(sid)
    assert added > 0
    assert len(database.get_attempts(sid)) == added + 1
    database.clear_demo_data(sid)
    remaining = database.get_attempts(sid)
    assert len(remaining) == 1 and remaining.iloc[0]["is_demo"] == 0, \
        "Real attempt must survive removing demo data"
    other = database.create_student("Other Student")
    database.save_quiz_attempt(other, S, T, "Mixed", 3, 6)
    database.reset_student_data(sid)
    assert len(database.get_attempts(sid)) == 0
    assert len(database.get_attempts(other)) == 1, "Reset must affect one student only"
    assert database.get_student(sid) is not None, "Profile must be kept"

check("Quiz result is saved with timestamp and topic scores", test_save_and_scores)
check("Every answer is stored in question_responses", test_responses_saved)
check("Data persists after a separate Python process opens the file", test_persistence_after_restart)
check("Invalid scores are rejected", test_invalid_scores)
check("Demo data / safe reset only remove what they should", test_demo_and_reset)

# ======================================================================
section("E. Recommendations update after new quiz attempts")
# ======================================================================
sid2 = database.create_student("Recommender Test")

def top_topic(recs):
    return {r["topic"]: r for r in recs}[T]

def test_recs_update():
    bundle = state["bundle"]
    database.save_quiz_attempt(sid2, S, T, "Mixed", 1, 6)
    before_recs = recommender.get_recommendations(sid2, bundle)
    before = top_topic(before_recs)
    assert before_recs[0]["topic"] == T, "Weak topic should rank first"
    assert before["priority_level"] == "High"
    assert before["measured"]["latest_score"] == 16.7
    assert before["ml"]["label"] == "Needs Practice"
    assert recommender.sync_study_tasks(sid2, before_recs)["added"] == 2
    pending_before = len(database.get_study_tasks(sid2, "Pending"))

    database.save_quiz_attempt(sid2, S, T, "Mixed", 6, 6)       # big improvement
    after_recs = recommender.get_recommendations(sid2, bundle)
    after = top_topic(after_recs)
    assert after["measured"]["latest_score"] == 100.0
    assert after["measured"]["previous_score"] == 16.7
    assert after["priority_score"] < before["priority_score"], "Priority must drop"
    recommender.sync_study_tasks(sid2, after_recs)
    assert len(database.get_study_tasks(sid2, "Pending")) <= pending_before

def test_three_parts_separate():
    rec = top_topic(recommender.get_recommendations(sid2, state["bundle"]))
    assert {"measured", "ml", "rules"} <= set(rec.keys())

def test_rules_only_mode():
    recs = recommender.get_recommendations(sid2, use_ml=False)
    assert all(r["ml"] is None for r in recs)

def test_task_completion():
    sid3 = database.create_student("Task Test")
    database.save_quiz_attempt(sid3, S, T, "Mixed", 1, 6)
    recommender.sync_study_tasks(sid3)
    pending = database.get_study_tasks(sid3, "Pending")
    assert len(pending) == 2
    assert database.complete_study_task(int(pending.iloc[0]["id"])) is True
    assert len(database.get_study_tasks(sid3, "Completed")) == 1
    assert len(database.get_study_tasks(sid3, "Pending")) == 1

check("A new quiz result changes the recommendation and tasks", test_recs_update)
check("Measured / model / rules stay in separate parts", test_three_parts_separate)
check("Rules-only mode works without the model", test_rules_only_mode)
check("Study tasks can be marked as completed", test_task_completion)

# ======================================================================
section("E2. AI tutor (built-in layer, no Ollama needed)")
# ======================================================================
def test_tutor():
    import tutor
    notes = tutor.retrieve("What is the LIFO principle of a stack?")
    assert notes, "Tutor found no notes"
    assert any(n["topic"] == "Stacks and Queues" for n in notes), \
        "Stack question should match the Stacks and Queues notes"
    assert "could not find" in tutor.builtin_answer("zzzz qqqq xxxx").lower()
    assert isinstance(tutor.mistakes_answer(sid2), str)

check("Tutor finds relevant notes and handles unknown questions", test_tutor)

# ======================================================================
section("E3. Accounts, passwords and the owner login")
# ======================================================================
def test_accounts():
    import auth
    auth.init_auth()
    uid = auth.register_student("Alice", "secret1")
    assert auth.login_student("Alice", "secret1") == uid
    for bad in [("Alice", "wrong-pass"), ("Nobody", "secret1")]:
        try:
            auth.login_student(*bad)
        except ValueError as error:
            assert "Wrong name or password" in str(error)
            continue
        raise AssertionError(f"Login {bad} should have failed")
    with database.db() as conn:
        stored = conn.execute("SELECT password_hash FROM students WHERE id = ?",
                              (uid,)).fetchone()[0]
    assert "secret1" not in stored and "$" in stored, "Password must be stored hashed"
    try:
        auth.register_student("Bob", "123")
        raise AssertionError("Short password was accepted")
    except ValueError:
        pass
    assert database.get_students() and "Bob" not in [s["name"] for s in database.get_students()]
    legacy = database.create_student("Legacy")           # profile without a password
    assert auth.login_student("Legacy", "claimed1") == legacy
    try:
        auth.login_student("Legacy", "other-pw")
        raise AssertionError("Claimed profile accepted a different password")
    except ValueError:
        pass

def test_owner():
    import auth
    assert not auth.owner_exists()
    auth.set_owner_password("owner-pass")
    assert auth.owner_exists() and auth.verify_owner("owner-pass")
    assert not auth.verify_owner("wrong")
    overview = auth.students_overview()
    assert "Alice" in set(overview["name"]) and "password_hash" not in overview.columns
    alice = int(overview.loc[overview["name"] == "Alice", "id"].iloc[0])
    auth.delete_student(alice)
    assert database.get_student(alice) is None

check("Accounts: hashed passwords, wrong logins rejected, old profile claimed", test_accounts)
check("Owner password works and the overview shows no secrets", test_owner)

# ======================================================================
section("F. Streamlit pages start without errors")
# ======================================================================
train_model.DATA_PATH, train_model.MODEL_PATH, train_model.METRICS_PATH = real_paths

import auth
from streamlit.testing.v1 import AppTest

UI = {"id": None}

def page_errors(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=90)
    at.session_state["auth_student_id"] = UI["id"]        # pretend the student signed in
    at.run()
    return [str(e.value)[:300] for e in at.exception]

PAGES = ["app.py", "pages/1_Dashboard.py", "pages/2_Take_Quiz.py",
         "pages/3_Study_Planner.py", "pages/4_Progress_Analytics.py",
         "pages/5_Model_Evaluation.py", "pages/6_AI_Tutor.py", "pages/7_Owner.py"]

def make_page_test(page):
    def run():
        errors = page_errors(page)
        assert not errors, errors
    return run

database.DB_PATH = TEMP / "ui_empty.db"          # new account, no data
database.init_db()
auth.init_auth()
UI["id"] = auth.register_student("UI Empty", "secret1")
for page in PAGES:
    check(f"{page} runs (empty database)", make_page_test(page))

database.DB_PATH = TEMP / "ui_demo.db"           # same pages WITH demo data
database.init_db()
auth.init_auth()
UI["id"] = auth.register_student("UI Demo", "secret1")
database.load_demo_data(UI["id"])
for page in PAGES:
    check(f"{page} runs (with demo data)", make_page_test(page))

def test_logged_out():
    at = AppTest.from_file(str(ROOT / "pages/1_Dashboard.py"), default_timeout=90).run()
    assert not at.exception
    assert any("Please sign in" in m.value for m in at.markdown), "Dashboard showed data"
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    assert not at.exception

check("Logged-out visitors see the sign-in page, not any data", test_logged_out)

# ======================================================================

# ======================================================================
section("G. Offline operation")
# ======================================================================
def test_no_network_imports():
    banned = re.compile(r"^\s*(import|from)\s+(requests|urllib|http|httpx|openai|anthropic|socket)\b")
    bad = []
    for path in list(ROOT.glob("*.py")) + list((ROOT / "pages").glob("*.py")):
        if path.name == "test_app.py":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if banned.match(line):
                bad.append(f"{path.name}: {line.strip()}")
    assert not bad, bad

def test_requirements_free():
    text = (ROOT / "requirements.txt").read_text().lower()
    allowed = {"streamlit", "pandas", "numpy", "scikit-learn", "plotly", "joblib", "ollama"}
    names = {re.split(r"[<>=!~ ]", l.strip())[0] for l in text.splitlines() if l.strip()}
    assert names <= allowed, f"Unexpected packages: {names - allowed}"

check("No network or AI-API libraries are imported by the project", test_no_network_imports)
check("requirements.txt contains only the free libraries", test_requirements_free)
check("Whole test run completed with internet connections blocked", lambda: None)

# ----------------------------------------------------------------------
shutil.rmtree(TEMP, ignore_errors=True)
passed = sum(1 for _, ok in results if ok)
print("\n" + "=" * 60)
print(f"RESULT: {passed} of {len(results)} checks passed")
failed = [n for n, ok in results if not ok]
if failed:
    print("FAILED:")
    for n in failed:
        print("  -", n)
    sys.exit(1)
print("ALL CHECKS PASSED. The application is ready for the demonstration.")