import sqlite3
import json
import os

DB_NAME = 'quiz.db'

# ---------- DATABASE CONNECTION ----------
def get_db():
    """Get database connection with row factory for dict-like rows"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- HELPER: CHECK IF COLUMN EXISTS ----------
def column_exists(conn, table, column):
    """Check if a specific column exists in a table"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

# ---------- INITIALIZE DATABASE ----------
def init_db():
    """Create all tables and run migrations if needed"""
    with get_db() as conn:
        # Create questions table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                correct INTEGER NOT NULL
            )
        ''')
        
        # Create quizzes table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                question_ids TEXT NOT NULL,
                time_per_question INTEGER DEFAULT 30,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create participants table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                answers TEXT,
                score INTEGER DEFAULT 0,
                time_taken INTEGER,
                FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
            )
        ''')
        
        # ----- MIGRATION: Add time_per_question column if missing -----
        if not column_exists(conn, 'quizzes', 'time_per_question'):
            conn.execute('ALTER TABLE quizzes ADD COLUMN time_per_question INTEGER DEFAULT 30')
            print("✅ Migrated database: added 'time_per_question' column to quizzes table")
        
        conn.commit()
        print("✅ Database initialized successfully!")

# ---------- QUESTION OPERATIONS ----------
def add_question(question, options, correct):
    """Add a new question to the database"""
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO questions (question, options, correct) VALUES (?, ?, ?)',
            (question, json.dumps(options), correct)
        )
        return cur.lastrowid

def get_all_questions():
    """Get all questions from the database"""
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM questions ORDER BY id').fetchall()
        questions = []
        for row in rows:
            q = dict(row)
            q['options'] = json.loads(q['options'])
            questions.append(q)
        return questions

def get_question_by_id(qid):
    """Get a single question by ID"""
    with get_db() as conn:
        row = conn.execute('SELECT * FROM questions WHERE id = ?', (qid,)).fetchone()
        if row:
            q = dict(row)
            q['options'] = json.loads(q['options'])
            return q
        return None

def delete_question(qid):
    """Delete a question by ID"""
    with get_db() as conn:
        conn.execute('DELETE FROM questions WHERE id = ?', (qid,))
        conn.commit()
        return True

def get_question_count():
    """Get total number of questions"""
    with get_db() as conn:
        row = conn.execute('SELECT COUNT(*) as count FROM questions').fetchone()
        return row['count']

# ---------- QUIZ OPERATIONS ----------
def create_quiz(code, question_ids, time_per_question=30):
    """Create a new quiz with the given questions"""
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO quizzes (code, question_ids, time_per_question, start_time, is_active) VALUES (?, ?, ?, datetime("now"), 1)',
            (code, json.dumps(question_ids), time_per_question)
        )
        return cur.lastrowid

def get_active_quiz_by_code(code):
    """Get an active quiz by its join code"""
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM quizzes WHERE code = ? AND is_active = 1',
            (code,)
        ).fetchone()
        if row:
            return dict(row)
        return None

def get_quiz_by_id(quiz_id):
    """Get quiz by ID"""
    with get_db() as conn:
        row = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
        if row:
            return dict(row)
        return None

def finish_quiz(quiz_id):
    """Mark a quiz as finished (inactive)"""
    with get_db() as conn:
        conn.execute(
            'UPDATE quizzes SET is_active = 0, end_time = datetime("now") WHERE id = ?',
            (quiz_id,)
        )
        conn.commit()
        return True

# ---------- PARTICIPANT OPERATIONS ----------
def add_participant(quiz_id, user_id):
    """Add a participant to a quiz, or get existing participant"""
    with get_db() as conn:
        # Check if participant already exists for this quiz
        existing = conn.execute(
            'SELECT * FROM participants WHERE quiz_id = ? AND user_id = ?',
            (quiz_id, user_id)
        ).fetchone()
        
        if existing:
            return dict(existing)
        
        # Create new participant
        cur = conn.execute(
            'INSERT INTO participants (quiz_id, user_id) VALUES (?, ?)',
            (quiz_id, user_id)
        )
        conn.commit()
        
        # Return the newly created participant
        return dict(conn.execute(
            'SELECT * FROM participants WHERE id = ?', (cur.lastrowid,)
        ).fetchone())

def update_participant(participant_id, answers, score, time_taken):
    """Update participant's answers, score, and time taken"""
    with get_db() as conn:
        conn.execute(
            'UPDATE participants SET answers = ?, score = ?, time_taken = ? WHERE id = ?',
            (json.dumps(answers), score, time_taken, participant_id)
        )
        conn.commit()
        return True

def get_participant_by_id(participant_id):
    """Get participant by ID"""
    with get_db() as conn:
        row = conn.execute('SELECT * FROM participants WHERE id = ?', (participant_id,)).fetchone()
        if row:
            return dict(row)
        return None

def get_participants_by_quiz(quiz_id):
    """Get all participants for a quiz"""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM participants WHERE quiz_id = ? ORDER BY score DESC, time_taken ASC',
            (quiz_id,)
        ).fetchall()
        return [dict(row) for row in rows]

# ---------- RESULTS OPERATIONS ----------
def get_quiz_results(quiz_id):
    """Get sorted results for a quiz"""
    with get_db() as conn:
        participants = conn.execute(
            'SELECT * FROM participants WHERE quiz_id = ? ORDER BY score DESC, time_taken ASC',
            (quiz_id,)
        ).fetchall()
        return [dict(p) for p in participants]

# ---------- CLEANUP OPERATIONS ----------
def delete_all_questions():
    """Delete all questions (use with caution!)"""
    with get_db() as conn:
        conn.execute('DELETE FROM questions')
        conn.execute("DELETE FROM sqlite_sequence WHERE name='questions'")
        conn.commit()
        return True

def delete_all_quizzes():
    """Delete all quizzes and participants (use with caution!)"""
    with get_db() as conn:
        conn.execute('DELETE FROM participants')
        conn.execute('DELETE FROM quizzes')
        conn.execute("DELETE FROM sqlite_sequence WHERE name='quizzes'")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='participants'")
        conn.commit()
        return True

# ---------- DATABASE UTILITIES ----------
def get_db_info():
    """Get database statistics"""
    with get_db() as conn:
        questions = conn.execute('SELECT COUNT(*) as count FROM questions').fetchone()['count']
        quizzes = conn.execute('SELECT COUNT(*) as count FROM quizzes').fetchone()['count']
        participants = conn.execute('SELECT COUNT(*) as count FROM participants').fetchone()['count']
        return {
            'questions': questions,
            'quizzes': quizzes,
            'participants': participants
        }

def vacuum_db():
    """Optimize database (remove deleted data)"""
    with get_db() as conn:
        conn.execute('VACUUM')
        conn.commit()
        return True