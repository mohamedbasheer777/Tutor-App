# AI-Powered Student Learning Companion
An Adaptive Learning and Weak Topic Detection System

A local web app that helps students find weak topics, practise with quizzes,
follow a personalised study plan and track progress. Free, open source and
fully offline: no API keys, no paid services, no generative AI.

## Features
- 3 subjects, 9 topics, 54 multiple-choice questions, 3 difficulty levels
- One-question-at-a-time quiz with automatic scoring and explanations
- Random Forest weak-topic prediction (Needs Practice / On Track)
- Transparent rule-based study planner with tasks you can mark as done
- Dashboard and analytics charts (Plotly)
- SQLite storage that survives restarts; safe demo-data and reset tools

## Important note about the ML model
The model is trained on SYNTHETIC (computer-generated) data. Its metrics show
it learned that synthetic pattern. They do not prove accuracy on real students.
The app keeps three things separate: measured performance, model prediction
and rule-based advice.

## Requirements
Python 3.9 or newer, and these free libraries: streamlit, pandas, numpy,
scikit-learn, plotly, joblib.

## Installation (Windows PowerShell)
    python -m venv venv
    venv\Scripts\activate
    python -m pip install -r requirements.txt

## Run
    python -m streamlit run app.py
Open http://localhost:8501 if the browser does not open automatically.

## Test
    python test_app.py

## Project structure
    app.py                  home page, profiles, demo data, reset
    ui.py                   shared styling and helpers
    quiz_data.py            question bank and scoring
    train_model.py          synthetic data, training, evaluation, prediction
    recommender.py          rules + model -> priorities and study tasks
    database.py             SQLite storage
    test_app.py             automated tests
    pages/                  Dashboard, Take Quiz, Study Planner,
                            Progress Analytics, Model Evaluation
    data/, ml_model/        database, dataset, saved model and metrics

## Limitations
Synthetic training data, small question bank, four features, hand-chosen
rules, single-user local use.