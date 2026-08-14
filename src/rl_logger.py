import sqlite3
import os
from datetime import datetime

# We will save this in our existing Chainlit database
DB_FILE = "jonaki_history.db"

def _ensure_db_exists():
    """Creates the feedback table if it doesn't exist yet."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user_question TEXT,
            jonaki_answer TEXT,
            user_feedback TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_feedback(question: str, answer: str, feedback_type: str):
    """Appends a new row of feedback to the SQLite database."""
    _ensure_db_exists()
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute(
        "INSERT INTO feedback (timestamp, user_question, jonaki_answer, user_feedback) VALUES (?, ?, ?, ?)",
        (timestamp, question, answer, feedback_type)
    )
    conn.commit()
    conn.close()
    print(f"DEBUG: Successfully logged {feedback_type} feedback to database.")