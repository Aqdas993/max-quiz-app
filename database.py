import sqlite3
import json

DB_NAME = 'quiz.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def column_exists(conn, table, column):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                correct INTEGER NOT NULL
            )
        ''')
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
        
        if not column_exists(conn, 'quizzes', 'time_per_question'):
            conn.execute('ALTER TABLE quizzes ADD COLUMN time_per_question INTEGER DEFAULT 30')
            print("✅ Migrated database: added 'time_per_question' column.")
        
        conn.commit()

def add_question(question, options, correct):
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO questions (question, options, correct) VALUES (?, ?, ?)',
            (question, json.dumps(options), correct)
        )
        return cur.lastrowid

def get_all_questions():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM questions').fetchall()
        questions = []
        for row in rows:
            q = dict(row)
            q['options'] = json.loads(q['options'])
            questions.append(q)
        return questions

def get_question_by_id(qid):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM questions WHERE id = ?', (qid,)).fetchone()
        if row:
            q = dict(row)
            q['options'] = json.loads(q['options'])
            return q
        return None

def delete_question(qid):
    with get_db() as conn:
        conn.execute('DELETE FROM questions WHERE id = ?', (qid,))
        conn.commit()
        return True

def create_quiz(code, question_ids, time_per_question=30):
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO quizzes (code, question_ids, time_per_question, start_time, is_active) VALUES (?, ?, ?, datetime("now"), 1)',
            (code, json.dumps(question_ids), time_per_question)
        )
        return cur.lastrowid

def get_active_quiz_by_code(code):
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM quizzes WHERE code = ? AND is_active = 1',
            (code,)
        ).fetchone()
        if row:
            return dict(row)
        return None

def add_participant(quiz_id, user_id):
    with get_db() as conn:
        existing = conn.execute(
            'SELECT * FROM participants WHERE quiz_id = ? AND user_id = ?',
            (quiz_id, user_id)
        ).fetchone()
        if existing:
            return dict(existing)
        cur = conn.execute(
            'INSERT INTO participants (quiz_id, user_id) VALUES (?, ?)',
            (quiz_id, user_id)
        )
        return dict(conn.execute(
            'SELECT * FROM participants WHERE id = ?', (cur.lastrowid,)
        ).fetchone())

def update_participant(participant_id, answers, score, time_taken):
    with get_db() as conn:
        conn.execute(
            'UPDATE participants SET answers = ?, score = ?, time_taken = ? WHERE id = ?',
            (json.dumps(answers), score, time_taken, participant_id)
        )
        conn.commit()

def finish_quiz(quiz_id):
    with get_db() as conn:
        conn.execute(
            'UPDATE quizzes SET is_active = 0, end_time = datetime("now") WHERE id = ?',
            (quiz_id,)
        )
        conn.commit()

def get_quiz_results(quiz_id):
    with get_db() as conn:
        participants = conn.execute(
            'SELECT * FROM participants WHERE quiz_id = ? ORDER BY score DESC, time_taken ASC',
            (quiz_id,)
        ).fetchall()
        return [dict(p) for p in participants]