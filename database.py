"""
database.py - SQLite storage for the Student Learning Companion.

Tables:
  students            student profiles
  quiz_attempts       one row per completed quiz
  question_responses  the answer to every question in every quiz
  topic_scores        summary per student/subject/topic (rebuilt from attempts)
  study_tasks         study planner tasks (Pending / Completed)
  learning_history    log of events (quizzes, tasks, resets)

The database file is data/learning_companion.db and is created automatically.
Run this file directly to self-test it (uses a temporary database, so your
real data is never touched):  python database.py
"""

import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from quiz_data import DIFFICULTIES, get_subjects, get_topics

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "learning_companion.db"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# ----------------------------------------------------------------------
# Connection helper
# ----------------------------------------------------------------------
@contextmanager
def db():
    """
    Open a connection, commit if everything worked, roll back on any error,
    and always close the connection.

    Usage:  with db() as conn:  conn.execute(...)
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # enforce links between tables
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now():
    return datetime.now().strftime(TIME_FORMAT)


# ----------------------------------------------------------------------
# Create tables
# ----------------------------------------------------------------------
def init_db():
    """Create all tables if they do not exist yet. Safe to call many times."""
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL
                           REFERENCES students(id) ON DELETE CASCADE,
                subject    TEXT NOT NULL,
                topic      TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                score      INTEGER NOT NULL,
                total      INTEGER NOT NULL,
                percentage REAL NOT NULL,
                taken_at   TEXT NOT NULL,
                is_demo    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS question_responses (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id     INTEGER NOT NULL
                               REFERENCES quiz_attempts(id) ON DELETE CASCADE,
                question_id    TEXT NOT NULL,
                selected_index INTEGER,
                correct_index  INTEGER NOT NULL,
                is_correct     INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS topic_scores (
                student_id     INTEGER NOT NULL
                               REFERENCES students(id) ON DELETE CASCADE,
                subject        TEXT NOT NULL,
                topic          TEXT NOT NULL,
                attempts       INTEGER NOT NULL,
                latest_score   REAL NOT NULL,
                previous_score REAL NOT NULL,
                average_score  REAL NOT NULL,
                best_score     REAL NOT NULL,
                last_practiced TEXT NOT NULL,
                PRIMARY KEY (student_id, subject, topic)
            );

            CREATE TABLE IF NOT EXISTS study_tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id   INTEGER NOT NULL
                             REFERENCES students(id) ON DELETE CASCADE,
                subject      TEXT NOT NULL,
                topic        TEXT NOT NULL,
                description  TEXT NOT NULL,
                reason       TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'Pending'
                             CHECK (status IN ('Pending', 'Completed')),
                created_at   TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS learning_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL
                           REFERENCES students(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                details    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


# ----------------------------------------------------------------------
# Small internal helpers
# ----------------------------------------------------------------------
def _require_student(conn, student_id):
    row = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        raise ValueError(f"Student with id {student_id} does not exist")


def _check_subject_topic(subject, topic):
    if subject not in get_subjects():
        raise ValueError(f"Unknown subject: {subject}")
    if topic not in get_topics(subject):
        raise ValueError(f"Topic '{topic}' does not belong to subject '{subject}'")


def _log(conn, student_id, event_type, details):
    conn.execute(
        "INSERT INTO learning_history (student_id, event_type, details, created_at) "
        "VALUES (?, ?, ?, ?)",
        (student_id, event_type, details, _now()),
    )


# ----------------------------------------------------------------------
# Student profiles
# ----------------------------------------------------------------------
def create_student(name):
    """Create a student profile and return its id."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Student name cannot be empty")
    if len(name) > 50:
        raise ValueError("Student name must be 50 characters or fewer")
    try:
        with db() as conn:
            cursor = conn.execute(
                "INSERT INTO students (name, created_at) VALUES (?, ?)", (name, _now())
            )
            student_id = cursor.lastrowid
            _log(conn, student_id, "Profile", f"Profile '{name}' created")
            return student_id
    except sqlite3.IntegrityError:
        raise ValueError(f"A student named '{name}' already exists")


def get_students():
    """Return a list of dictionaries: id, name, created_at."""
    with db() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM students ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_student(student_id):
    """Return one student as a dictionary, or None."""
    with db() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        return dict(row) if row else None


def get_or_create_default_student(name="Student"):
    """Return the id of the first student, creating one if none exists."""
    students = get_students()
    if students:
        return students[0]["id"]
    return create_student(name)


# ----------------------------------------------------------------------
# Quiz attempts and topic scores
# ----------------------------------------------------------------------
def _insert_attempt(conn, student_id, subject, topic, difficulty, score, total,
                    details=None, taken_at=None, is_demo=False):
    """Validate and insert one attempt (and its answers). Returns the attempt id."""
    _require_student(conn, student_id)
    _check_subject_topic(subject, topic)
    if difficulty not in ["Mixed"] + DIFFICULTIES:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    if total <= 0:
        raise ValueError("A quiz must have at least one question")
    if not 0 <= score <= total:
        raise ValueError("Score must be between 0 and the total number of questions")

    percentage = round(score / total * 100, 1)
    cursor = conn.execute(
        "INSERT INTO quiz_attempts "
        "(student_id, subject, topic, difficulty, score, total, percentage, taken_at, is_demo) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, subject, topic, difficulty, score, total, percentage,
         taken_at or _now(), 1 if is_demo else 0),
    )
    attempt_id = cursor.lastrowid

    if details:
        conn.executemany(
            "INSERT INTO question_responses "
            "(attempt_id, question_id, selected_index, correct_index, is_correct) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (attempt_id, d["id"], d["selected_index"], d["correct_index"],
                 1 if d["is_correct"] else 0)
                for d in details
            ],
        )

    _rebuild_topic_score(conn, student_id, subject, topic)
    return attempt_id


def _rebuild_topic_score(conn, student_id, subject, topic):
    """
    Recalculate the topic_scores row from the attempts table.
    Because it is always rebuilt from attempts, the summary can never
    disagree with the real quiz history.
    """
    rows = conn.execute(
        "SELECT percentage, taken_at FROM quiz_attempts "
        "WHERE student_id = ? AND subject = ? AND topic = ? "
        "ORDER BY taken_at, id",
        (student_id, subject, topic),
    ).fetchall()

    if not rows:
        conn.execute(
            "DELETE FROM topic_scores WHERE student_id = ? AND subject = ? AND topic = ?",
            (student_id, subject, topic),
        )
        return

    percentages = [r["percentage"] for r in rows]
    latest = percentages[-1]
    # With only one attempt there is no earlier score, so previous = latest.
    previous = percentages[-2] if len(percentages) >= 2 else latest

    conn.execute(
        "INSERT OR REPLACE INTO topic_scores "
        "(student_id, subject, topic, attempts, latest_score, previous_score, "
        " average_score, best_score, last_practiced) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, subject, topic, len(percentages), latest, previous,
         round(sum(percentages) / len(percentages), 1), max(percentages),
         rows[-1]["taken_at"]),
    )


def save_quiz_attempt(student_id, subject, topic, difficulty, score, total, details=None):
    """
    Save a finished quiz. 'details' is the list from quiz_data.score_quiz()["details"].
    Updates topic scores and the history log. Returns the new attempt id.
    """
    with db() as conn:
        attempt_id = _insert_attempt(
            conn, student_id, subject, topic, difficulty, score, total, details
        )
        _log(conn, student_id, "Quiz",
             f"{subject} / {topic} ({difficulty}): {score}/{total}")
        return attempt_id


def get_attempts(student_id, limit=None):
    """Return quiz attempts (newest first) as a pandas DataFrame."""
    sql = (
        "SELECT id, subject, topic, difficulty, score, total, percentage, taken_at, is_demo "
        "FROM quiz_attempts WHERE student_id = ? ORDER BY taken_at DESC, id DESC"
    )
    params = [student_id]
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    with db() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    df["taken_at"] = pd.to_datetime(df["taken_at"])
    return df


def get_topic_scores(student_id):
    """Return the topic summary table as a pandas DataFrame."""
    with db() as conn:
        df = pd.read_sql_query(
            "SELECT subject, topic, attempts, latest_score, previous_score, "
            "average_score, best_score, last_practiced "
            "FROM topic_scores WHERE student_id = ? ORDER BY subject, topic",
            conn, params=[student_id],
        )
    df["last_practiced"] = pd.to_datetime(df["last_practiced"])
    return df


def get_topic_features(student_id, subject, topic):
    """
    Return the four ML features for one topic, or None if never practised:
      previous_score, latest_score, num_attempts, days_since_last_practice
    These are ACTUAL measured values from the database.
    """
    with db() as conn:
        row = conn.execute(
            "SELECT attempts, latest_score, previous_score, last_practiced "
            "FROM topic_scores WHERE student_id = ? AND subject = ? AND topic = ?",
            (student_id, subject, topic),
        ).fetchone()
    if row is None:
        return None
    last = datetime.strptime(row["last_practiced"], TIME_FORMAT)
    days = max(0, int((datetime.now() - last).total_seconds() // 86400))
    return {
        "previous_score": row["previous_score"],
        "latest_score": row["latest_score"],
        "num_attempts": row["attempts"],
        "days_since_last_practice": days,
    }


def get_summary(student_id):
    """Numbers for the dashboard cards."""
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, AVG(percentage) AS avg_pct, MAX(taken_at) AS last_time "
            "FROM quiz_attempts WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        topics = conn.execute(
            "SELECT COUNT(*) AS n FROM topic_scores WHERE student_id = ?", (student_id,)
        ).fetchone()
    return {
        "total_quizzes": row["n"],
        "average_score": round(row["avg_pct"], 1) if row["avg_pct"] is not None else 0.0,
        "topics_practiced": topics["n"],
        "last_activity": row["last_time"],
    }


# ----------------------------------------------------------------------
# Study tasks
# ----------------------------------------------------------------------
def add_study_task(student_id, subject, topic, description, reason=""):
    """
    Add a Pending study task and return its id. If an identical Pending task
    already exists, its id is returned and no duplicate is created.
    """
    description = (description or "").strip()
    if not description:
        raise ValueError("Task description cannot be empty")
    _check_subject_topic(subject, topic)
    with db() as conn:
        _require_student(conn, student_id)
        existing = conn.execute(
            "SELECT id FROM study_tasks WHERE student_id = ? AND subject = ? "
            "AND topic = ? AND description = ? AND status = 'Pending'",
            (student_id, subject, topic, description),
        ).fetchone()
        if existing:
            return existing["id"]
        cursor = conn.execute(
            "INSERT INTO study_tasks (student_id, subject, topic, description, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (student_id, subject, topic, description, reason, _now()),
        )
        return cursor.lastrowid


def get_study_tasks(student_id, status=None):
    """Return study tasks as a DataFrame. status: None, 'Pending' or 'Completed'."""
    if status not in (None, "Pending", "Completed"):
        raise ValueError("status must be None, 'Pending' or 'Completed'")
    sql = (
        "SELECT id, subject, topic, description, reason, status, created_at, completed_at "
        "FROM study_tasks WHERE student_id = ?"
    )
    params = [student_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id"
    with db() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def complete_study_task(task_id):
    """Mark a task as Completed. Returns True if a Pending task was updated."""
    with db() as conn:
        row = conn.execute(
            "SELECT student_id, topic, description FROM study_tasks "
            "WHERE id = ? AND status = 'Pending'", (task_id,)
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE study_tasks SET status = 'Completed', completed_at = ? WHERE id = ?",
            (_now(), task_id),
        )
        _log(conn, row["student_id"], "Task",
             f"Completed: {row['description']} ({row['topic']})")
        return True


def reopen_study_task(task_id):
    """Undo a completion (set the task back to Pending)."""
    with db() as conn:
        cursor = conn.execute(
            "UPDATE study_tasks SET status = 'Pending', completed_at = NULL "
            "WHERE id = ? AND status = 'Completed'", (task_id,)
        )
        return cursor.rowcount > 0


def delete_pending_tasks(student_id, topic=None):
    """Remove Pending tasks (used when recommendations are refreshed)."""
    sql = "DELETE FROM study_tasks WHERE student_id = ? AND status = 'Pending'"
    params = [student_id]
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    with db() as conn:
        return conn.execute(sql, params).rowcount


# ----------------------------------------------------------------------
# Learning history
# ----------------------------------------------------------------------
def get_history(student_id, limit=50):
    """Return the activity log (newest first) as a DataFrame."""
    with db() as conn:
        return pd.read_sql_query(
            "SELECT event_type, details, created_at FROM learning_history "
            "WHERE student_id = ? ORDER BY id DESC LIMIT ?",
            conn, params=[student_id, int(limit)],
        )


# ----------------------------------------------------------------------
# Demo data and safe resets
# ----------------------------------------------------------------------
# How strong the demo student is in each topic (0 = weak, 1 = strong).
DEMO_SKILL = {
    "Variables and Data Types": 0.85,
    "Loops and Conditions": 0.75,
    "Functions and Lists": 0.70,
    "Arrays and Linked Lists": 0.65,
    "Stacks and Queues": 0.55,
    "Trees and Graphs": 0.35,
    "OSI and TCP/IP Models": 0.50,
    "IP Addressing": 0.40,
    "Network Protocols": 0.60,
}


def load_demo_data(student_id):
    """
    Add sample quiz attempts spread over the last 30 days so charts and
    recommendations have something to show. Demo rows are marked is_demo = 1,
    so clear_demo_data() can remove them without touching real attempts.
    Returns the number of attempts added.
    """
    rng = random.Random(7)          # fixed seed: same demo data every time
    clear_demo_data(student_id)     # never create duplicates
    now = datetime.now()
    added = 0

    with db() as conn:
        _require_student(conn, student_id)
        for subject in get_subjects():
            for topic in get_topics(subject):
                skill = DEMO_SKILL.get(topic, 0.6)
                n_attempts = rng.randint(2, 4)
                days_ago = sorted(rng.sample(range(1, 31), n_attempts), reverse=True)
                for i, d in enumerate(days_ago):
                    probability = min(0.95, skill + 0.04 * i)   # slight improvement
                    score = sum(rng.random() < probability for _ in range(6))
                    when = now - timedelta(days=d, hours=rng.randint(0, 5))
                    _insert_attempt(
                        conn, student_id, subject, topic, "Mixed", score, 6,
                        taken_at=when.strftime(TIME_FORMAT), is_demo=True,
                    )
                    added += 1
        _log(conn, student_id, "Demo", f"Demo data loaded ({added} attempts)")
    return added


def clear_demo_data(student_id):
    """Delete ONLY demo attempts, keep real ones, and rebuild topic scores."""
    with db() as conn:
        _require_student(conn, student_id)
        pairs = conn.execute(
            "SELECT DISTINCT subject, topic FROM quiz_attempts "
            "WHERE student_id = ? AND is_demo = 1", (student_id,)
        ).fetchall()
        if not pairs:
            return 0
        removed = conn.execute(
            "DELETE FROM quiz_attempts WHERE student_id = ? AND is_demo = 1", (student_id,)
        ).rowcount
        for p in pairs:
            _rebuild_topic_score(conn, student_id, p["subject"], p["topic"])
        _log(conn, student_id, "Demo", f"Demo data cleared ({removed} attempts)")
        return removed


def reset_student_data(student_id):
    """
    Delete ALL learning data of ONE student (attempts, scores, tasks, history).
    The profile itself is kept. Other students are not affected.
    The app must ask for confirmation before calling this.
    """
    with db() as conn:
        _require_student(conn, student_id)
        conn.execute("DELETE FROM quiz_attempts WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM topic_scores WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM study_tasks WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM learning_history WHERE student_id = ?", (student_id,))
        _log(conn, student_id, "Reset", "All learning data was reset")


# ----------------------------------------------------------------------
# Self-test: python database.py  (uses a temporary database)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as temp_folder:
        DB_PATH = Path(temp_folder) / "test.db"   # real database is NOT used

        init_db()
        init_db()   # calling twice must be harmless
        with db() as conn:
            names = [r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        print("1. Tables created:", ", ".join(names))
        assert len(names) == 6

        sid = create_student("Test Student")
        print("2. Student created with id", sid)
        try:
            create_student("Test Student")
            raise SystemExit("Duplicate name should have been rejected")
        except ValueError:
            print("   Duplicate name rejected: OK")

        S, T = "Data Structures", "Trees and Graphs"
        save_quiz_attempt(sid, S, T, "Mixed", 4, 6)
        f = get_topic_features(sid, S, T)
        print("3. After 1st quiz (4/6):", f)
        assert f["latest_score"] == 66.7 and f["previous_score"] == 66.7
        assert f["num_attempts"] == 1 and f["days_since_last_practice"] == 0

        save_quiz_attempt(sid, S, T, "Mixed", 2, 6)
        f = get_topic_features(sid, S, T)
        print("4. After 2nd quiz (2/6):", f)
        assert f["latest_score"] == 33.3 and f["previous_score"] == 66.7
        assert f["num_attempts"] == 2

        summary = get_summary(sid)
        print("5. Summary:", summary)
        assert summary["total_quizzes"] == 2 and summary["average_score"] == 50.0
        assert summary["topics_practiced"] == 1

        t1 = add_study_task(sid, S, T, "Revise tree traversals")
        t2 = add_study_task(sid, S, T, "Revise tree traversals")
        assert t1 == t2
        assert len(get_study_tasks(sid, "Pending")) == 1
        assert complete_study_task(t1) is True
        assert complete_study_task(t1) is False        # already completed
        assert len(get_study_tasks(sid, "Completed")) == 1
        print("6. Study tasks: add, no duplicates, complete: OK")

        added = load_demo_data(sid)
        print(f"7. Demo attempts added: {added}")
        assert 18 <= added <= 36
        assert len(get_attempts(sid)) == added + 2
        removed = clear_demo_data(sid)
        assert removed == added
        assert len(get_attempts(sid)) == 2             # real attempts survive
        print("   Demo data cleared, real attempts kept: OK")

        reset_student_data(sid)
        assert len(get_attempts(sid)) == 0
        assert len(get_study_tasks(sid)) == 0
        assert len(get_topic_scores(sid)) == 0
        assert get_student(sid) is not None            # profile is kept
        print("8. Reset removed all learning data, kept the profile: OK")

        for bad in [(7, 6), (-1, 6), (3, 0)]:
            try:
                save_quiz_attempt(sid, S, T, "Mixed", *bad)
                raise SystemExit(f"Bad input {bad} should have been rejected")
            except ValueError:
                pass
        print("9. Invalid scores rejected: OK")

    print("\nAll Stage 4 checks passed.")