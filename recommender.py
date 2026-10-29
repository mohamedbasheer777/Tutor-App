"""
recommender.py - Study recommendations for the Student Learning Companion.

For every topic this module keeps THREE things separate:
  1. measured   : real quiz results from the database
  2. ml         : prediction of the Random Forest (trained on SYNTHETIC data)
  3. rules      : transparent if-then rules with points

Priority score = rule points + ML_WEIGHT * P(Needs Practice)
Higher score = revise this topic sooner.

Run this file directly to self-test it (uses a temporary database):
    python recommender.py
(Run  python train_model.py  first so the model file exists.)
"""

import pandas as pd

import database
from database import (
    add_study_task,
    complete_study_task,
    delete_pending_tasks,
    get_study_tasks,
    get_topic_features,
    get_topic_scores,
)
from quiz_data import ALL_QUESTIONS, get_questions, get_subjects, get_topics
from train_model import load_model, predict_topic

# ----------------------------------------------------------------------
# Settings (all visible, so the logic is transparent)
# ----------------------------------------------------------------------
ML_WEIGHT = 30               # how much the ML probability adds (0 to 30 points)
HIGH_THRESHOLD = 55          # priority score >= 55  -> "High"
MEDIUM_THRESHOLD = 25        # priority score >= 25  -> "Medium", else "Low"
NOT_STARTED_SCORE = 20       # topics never practised rank above "Low"
MAX_TASK_TOPICS = 5          # study tasks are created for at most 5 topics
PRACTICE_QUESTIONS_PER_TOPIC = 3

RULES_DESCRIPTION = [
    ("Latest score below 50%", "+40 points"),
    ("Latest score from 50% to 69%", "+20 points"),
    ("Score dropped by 10+ points since the previous attempt", "+20 points"),
    ("Not practised for 14 or more days", "+15 points"),
    ("Not practised for 7 to 13 days", "+8 points"),
    ("Only one attempt so far (little evidence)", "+5 points"),
    ("ML model probability of 'Needs Practice'", f"+0 to {ML_WEIGHT} points"),
]

_QUESTION_BY_ID = {q["id"]: q for q in ALL_QUESTIONS}


# ----------------------------------------------------------------------
# Rule engine
# ----------------------------------------------------------------------
def apply_rules(latest, previous, attempts, days):
    """Return a list of triggered rules: [{rule, points, explanation}, ...]."""
    triggered = []

    def add(points, rule, explanation):
        triggered.append({"rule": rule, "points": points, "explanation": explanation})

    if latest < 50:
        add(40, "Low latest score", f"Latest score {latest:.0f}% is below 50%.")
    elif latest < 70:
        add(20, "Moderate latest score", f"Latest score {latest:.0f}% is below 70%.")

    if attempts >= 2 and latest - previous <= -10:
        add(20, "Declining performance",
            f"Score dropped {previous - latest:.0f} points since the previous attempt.")

    if days >= 14:
        add(15, "Not practised for a long time", f"Last practised {days} days ago.")
    elif days >= 7:
        add(8, "Not practised recently", f"Last practised {days} days ago.")

    if attempts < 2:
        add(5, "Little evidence", "Only one attempt so far, so the score may be unreliable.")

    return triggered


def suggest_difficulty(latest):
    """Pick a quiz difficulty that matches the latest measured score."""
    if latest is None or latest < 50:
        return "Easy"
    if latest < 75:
        return "Medium"
    return "Hard"


def _level(priority_score):
    if priority_score >= HIGH_THRESHOLD:
        return "High"
    if priority_score >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


# ----------------------------------------------------------------------
# Practice question suggestions
# ----------------------------------------------------------------------
def _previously_wrong_question_ids(student_id, subject, topic):
    """Questions whose MOST RECENT answer was wrong (needs saved answer details)."""
    with database.db() as conn:
        rows = conn.execute(
            "SELECT r.question_id, r.is_correct FROM question_responses r "
            "JOIN quiz_attempts a ON a.id = r.attempt_id "
            "WHERE a.student_id = ? AND a.subject = ? AND a.topic = ? "
            "ORDER BY a.taken_at, a.id",
            (student_id, subject, topic),
        ).fetchall()
    latest_status = {}
    for row in rows:                      # later rows overwrite earlier ones
        latest_status[row["question_id"]] = bool(row["is_correct"])
    return [qid for qid, correct in latest_status.items() if not correct]


def get_practice_questions(student_id, subject, topic, difficulty,
                           limit=PRACTICE_QUESTIONS_PER_TOPIC):
    """Wrongly answered questions first, then questions at the suggested difficulty."""
    chosen = []
    for qid in _previously_wrong_question_ids(student_id, subject, topic):
        q = _QUESTION_BY_ID.get(qid)
        if q and len(chosen) < limit:
            chosen.append({"id": qid, "question": q["question"], "difficulty": q["difficulty"],
                           "reason": "You answered this incorrectly last time"})
    chosen_ids = {c["id"] for c in chosen}
    for q in get_questions(subject, topic, difficulty):
        if q["id"] not in chosen_ids and len(chosen) < limit:
            chosen.append({"id": q["id"], "question": q["question"], "difficulty": q["difficulty"],
                           "reason": f"Matches your suggested {difficulty} level"})
    return chosen


# ----------------------------------------------------------------------
# Recommendations
# ----------------------------------------------------------------------
def _reason_text(rec):
    parts = [r["explanation"] for r in rec["rules"]]
    if rec["ml"] and rec["ml"]["label"] == "Needs Practice":
        parts.append("The model predicts Needs Practice.")
    return " ".join(parts) or "No concerns found."


def get_recommendations(student_id, bundle=None, use_ml=True):
    """
    Return one recommendation dictionary per topic, sorted with the topic to
    revise FIRST at the top. If the model file is missing, the rules still work
    and the 'ml' part is None.
    """
    if use_ml and bundle is None:
        try:
            bundle = load_model()
        except Exception:
            bundle = None
    if not use_ml:
        bundle = None

    scores = get_topic_scores(student_id)
    lookup = {(r["subject"], r["topic"]): r for r in scores.to_dict("records")}
    recs = []

    for subject in get_subjects():
        for topic in get_topics(subject):
            row = lookup.get((subject, topic))

            # --- never practised ---
            if row is None:
                difficulty = suggest_difficulty(None)
                recs.append({
                    "subject": subject, "topic": topic, "status": "Not started",
                    "measured": None, "ml": None, "rules": [], "rule_points": 0,
                    "priority_score": NOT_STARTED_SCORE, "priority_level": "Not started",
                    "recommended_difficulty": difficulty,
                    "practice_questions": get_practice_questions(student_id, subject, topic, difficulty),
                    "advice": f"Not practised yet. Start with an {difficulty} quiz to measure your level.",
                })
                continue

            # --- 1. measured performance (from the database) ---
            features = get_topic_features(student_id, subject, topic)
            measured = {
                **features,
                "average_score": row["average_score"],
                "best_score": row["best_score"],
                "last_practiced": row["last_practiced"].strftime(database.TIME_FORMAT),
            }

            # --- 2. ML prediction ---
            ml = None
            if bundle is not None:
                try:
                    ml = predict_topic(bundle, **features)
                except Exception:
                    ml = None

            # --- 3. rule-based advice ---
            rules = apply_rules(features["latest_score"], features["previous_score"],
                                features["num_attempts"], features["days_since_last_practice"])
            rule_points = sum(r["points"] for r in rules)
            ml_points = round(ML_WEIGHT * ml["probability_needs_practice"]) if ml else 0
            priority_score = rule_points + ml_points
            level = _level(priority_score)
            difficulty = suggest_difficulty(features["latest_score"])

            if level in ("High", "Medium"):
                advice = (f"Revise {topic}, then take a {difficulty}-level quiz "
                          f"to check your progress.")
            else:
                advice = (f"You are on track in {topic}. Take a {difficulty}-level quiz "
                          f"now and then to stay sharp.")

            recs.append({
                "subject": subject, "topic": topic, "status": "Practised",
                "measured": measured, "ml": ml, "rules": rules,
                "rule_points": rule_points, "priority_score": priority_score,
                "priority_level": level, "recommended_difficulty": difficulty,
                "practice_questions": get_practice_questions(student_id, subject, topic, difficulty),
                "advice": advice,
            })

    recs.sort(key=lambda r: (-r["priority_score"], r["subject"], r["topic"]))
    for rank, rec in enumerate(recs, start=1):
        rec["rank"] = rank
    return recs


def topics_needing_practice(recs):
    """Topics with High or Medium priority (for the dashboard)."""
    return [r for r in recs if r["priority_level"] in ("High", "Medium")]


def recommendations_to_dataframe(recs):
    """A table for the Study Planner page, keeping measured / ML / rules in separate columns."""
    rows = []
    for r in recs:
        measured, ml = r["measured"], r["ml"]
        rows.append({
            "Rank": r["rank"],
            "Subject": r["subject"],
            "Topic": r["topic"],
            "Priority": r["priority_level"],
            "Latest score % (measured)": measured["latest_score"] if measured else None,
            "Model prediction": ml["label"] if ml else "-",
            "P(Needs Practice)": ml["probability_needs_practice"] if ml else None,
            "Rule points": r["rule_points"],
            "Priority score": r["priority_score"],
            "Suggested difficulty": r["recommended_difficulty"],
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# Study tasks (kept in step with the latest quiz results)
# ----------------------------------------------------------------------
def sync_study_tasks(student_id, recs=None):
    """
    Make the Pending tasks match the current recommendations.
    Call this after every quiz and whenever the Study Planner page opens.

      - Tasks are created for High / Medium priority topics (at most 5 topics).
      - A task the student completed is NOT created again until a NEW quiz
        is taken on that topic (so finished tasks stay finished).
      - Pending tasks for topics that no longer need practice are removed.
      - Unchanged pending tasks are left alone.

    Returns {"added": n, "removed": n}.
    """
    if recs is None:
        recs = get_recommendations(student_id)

    completed = get_study_tasks(student_id, "Completed")
    if not completed.empty:
        completed["completed_at"] = pd.to_datetime(completed["completed_at"])
    pending = get_study_tasks(student_id, "Pending")

    desired = {}
    for rec in topics_needing_practice(recs)[:MAX_TASK_TOPICS]:
        subject, topic = rec["subject"], rec["topic"]
        last_practiced = pd.Timestamp(rec["measured"]["last_practiced"])
        reason = f"Priority {rec['priority_level']}: {_reason_text(rec)}"
        wanted = [
            f"Revise the key concepts of {topic}",
            f"Take a {rec['recommended_difficulty']}-level quiz on {topic}",
        ]
        keep = []
        for description in wanted:
            if not completed.empty:
                done = completed[(completed["subject"] == subject)
                                 & (completed["topic"] == topic)
                                 & (completed["description"] == description)]
                # completed AFTER the latest quiz -> do not recreate
                if (done["completed_at"] > last_practiced).any():
                    continue
            keep.append((description, reason))
        desired[(subject, topic)] = keep

    added = removed = 0
    for subject in get_subjects():
        for topic in get_topics(subject):   # topic names are unique across subjects
            existing = set(pending[(pending["subject"] == subject)
                                   & (pending["topic"] == topic)]["description"])
            wanted_tasks = desired.get((subject, topic), [])
            if existing == {d for d, _ in wanted_tasks}:
                continue                     # nothing changed for this topic
            removed += delete_pending_tasks(student_id, topic)
            for description, reason in wanted_tasks:
                add_study_task(student_id, subject, topic, description, reason)
                added += 1
    return {"added": added, "removed": removed}


# ----------------------------------------------------------------------
# Self-test: python recommender.py  (uses a temporary database)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile
    import time
    from datetime import datetime, timedelta
    from pathlib import Path

    from quiz_data import build_quiz, score_quiz

    try:
        model_bundle = load_model()
    except FileNotFoundError as error:
        raise SystemExit(f"{error}\nRun 'python train_model.py' first, then try again.")

    with tempfile.TemporaryDirectory() as temp_folder:
        database.DB_PATH = Path(temp_folder) / "test.db"     # real database is NOT used
        database.init_db()
        sid = database.create_student("Test Student")

        def days_ago(n):
            return (datetime.now() - timedelta(days=n)).strftime(database.TIME_FORMAT)

        def add_old_attempt(subject, topic, score, n_days):
            with database.db() as conn:
                database._insert_attempt(conn, sid, subject, topic, "Mixed", score, 6,
                                         taken_at=days_ago(n_days))

        def pending_topics():
            return set(get_study_tasks(sid, "Pending")["topic"])

        # 1. brand-new student
        recs = get_recommendations(sid, model_bundle)
        assert len(recs) == 9 and all(r["priority_level"] == "Not started" for r in recs)
        assert sync_study_tasks(sid, recs) == {"added": 0, "removed": 0}
        print("1. New student: 9 topics 'Not started', 0 tasks created: OK")

        # 2. a weak topic (older attempt 1/6, newest attempt 0/6 with saved answers)
        S, T = "Data Structures", "Trees and Graphs"
        add_old_attempt(S, T, 1, 2)
        quiz = build_quiz(S, T, "Mixed", 6)
        wrong = {q["id"]: (q["correct_index"] + 1) % 4 for q in quiz}
        result = score_quiz(quiz, wrong)
        database.save_quiz_attempt(sid, S, T, "Mixed", result["score"], result["total"],
                                   result["details"])
        recs = get_recommendations(sid, model_bundle)
        top = recs[0]
        print(f"2. Weak topic: {top['topic']} | measured latest = "
              f"{top['measured']['latest_score']}% | ML = {top['ml']['label']} "
              f"({top['ml']['probability_needs_practice']}) | rule points = "
              f"{top['rule_points']} | priority = {top['priority_score']} ({top['priority_level']})")
        assert top["topic"] == T and top["priority_level"] == "High"
        assert top["practice_questions"][0]["reason"].startswith("You answered")
        assert sync_study_tasks(sid, recs)["added"] == 2
        assert pending_topics() == {T}
        print("   2 study tasks created; practice questions include earlier mistakes: OK")

        # 3. completed tasks must not come back until a NEW quiz is taken
        time.sleep(1.1)       # timestamps have 1-second resolution
        for task_id in get_study_tasks(sid, "Pending")["id"]:
            assert complete_study_task(task_id)
        sync_study_tasks(sid)
        assert len(get_study_tasks(sid, "Pending")) == 0
        print("3. Completed tasks stay completed (no new quiz yet): OK")

        # 4. a new quiz result updates the recommendations
        time.sleep(1.1)
        database.save_quiz_attempt(sid, S, T, "Mixed", 1, 6)
        sync_study_tasks(sid)
        assert len(get_study_tasks(sid, "Pending")) == 2
        print("4. New quiz result -> tasks created again because the topic is still weak: OK")

        # 5. declining score triggers its rule; a strong topic stays Low priority
        add_old_attempt("Python Programming", "Functions and Lists", 5, 3)
        database.save_quiz_attempt(sid, "Python Programming", "Functions and Lists",
                                   "Mixed", 2, 6)
        add_old_attempt(S, "Stacks and Queues", 6, 2)
        database.save_quiz_attempt(sid, S, "Stacks and Queues", "Mixed", 6, 6)
        recs = get_recommendations(sid, model_bundle)
        by_topic = {r["topic"]: r for r in recs}
        assert any(rule["rule"] == "Declining performance"
                   for rule in by_topic["Functions and Lists"]["rules"])
        assert by_topic["Stacks and Queues"]["priority_level"] == "Low"
        assert (by_topic["Stacks and Queues"]["priority_score"]
                < by_topic["Functions and Lists"]["priority_score"])
        sync_study_tasks(sid, recs)
        assert "Stacks and Queues" not in pending_topics()
        print("5. Declining-score rule fires; strong topic is Low and gets no tasks: OK")

        # 6. table output and rules-only mode (no ML model)
        table = recommendations_to_dataframe(recs)
        assert len(table) == 9 and table.iloc[0]["Rank"] == 1
        rules_only = get_recommendations(sid, use_ml=False)
        assert all(r["ml"] is None for r in rules_only)
        print("6. Table output and rules-only mode work: OK")

    print("\nAll Stage 5 checks passed.")