from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import database as db
import random
import string
import json
import hashlib
import hmac
import urllib.parse
import os

app = Flask(__name__)
CORS(app)

# ---------- Helper: generate join code ----------
def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ---------- API Routes ----------

# 1. Add a question
@app.route('/api/questions', methods=['POST'])
def add_question():
    data = request.json
    question = data.get('question')
    options = data.get('options')
    correct = data.get('correct')
    if not all([question, options, correct]):
        return jsonify({'error': 'Missing fields'}), 400
    if len(options) != 4:
        return jsonify({'error': 'Need exactly 4 options'}), 400
    qid = db.add_question(question, options, correct)
    return jsonify({'id': qid, 'message': 'Question added'}), 201

# 2. Get all questions
@app.route('/api/questions', methods=['GET'])
def get_questions():
    questions = db.get_all_questions()
    return jsonify(questions)

# 3. Delete a question
@app.route('/api/questions/<int:qid>', methods=['DELETE'])
def delete_question(qid):
    db.delete_question(qid)
    return jsonify({'message': 'Deleted'}), 200

# 4. IMPORT questions
@app.route('/api/questions/import', methods=['POST'])
def import_questions():
    data = request.json
    imported = data.get('questions', [])
    if not imported:
        return jsonify({'error': 'No questions provided'}), 400
    
    added_count = 0
    for q in imported:
        question = q.get('question')
        options = q.get('options')
        correct = q.get('correct')
        if question and options and correct and len(options) == 4:
            db.add_question(question, options, correct)
            added_count += 1
    
    return jsonify({'message': f'Successfully imported {added_count} questions'}), 201

# 5. Launch a quiz
@app.route('/api/quiz/launch', methods=['POST'])
def launch_quiz():
    data = request.json
    num_questions = data.get('num_questions', 10)
    time_per_question = data.get('time_per_question', 30)
    
    all_q = db.get_all_questions()
    if len(all_q) < num_questions:
        return jsonify({'error': f'Only {len(all_q)} questions available'}), 400
    
    selected = random.sample(all_q, num_questions)
    random.shuffle(selected)
    
    for q in selected:
        options = q['options']
        correct = q['correct']
        paired = list(enumerate(options, start=1))
        random.shuffle(paired)
        new_options = [p[1] for p in paired]
        new_correct = 1
        for idx, (orig_idx, opt) in enumerate(paired):
            if orig_idx == correct:
                new_correct = idx + 1
                break
        q['options'] = new_options
        q['correct'] = new_correct
    
    question_ids = [q['id'] for q in selected]
    code = generate_code()
    quiz_id = db.create_quiz(code, question_ids, time_per_question)
    
    return jsonify({
        'quiz_id': quiz_id,
        'code': code,
        'questions': selected,
        'time_per_question': time_per_question
    }), 201

# 6. Join quiz (participant)
@app.route('/api/quiz/join', methods=['POST'])
def join_quiz():
    data = request.json
    code = data.get('code')
    user_id = data.get('user_id', 'anonymous')
    if not code:
        return jsonify({'error': 'Code required'}), 400
    
    quiz = db.get_active_quiz_by_code(code)
    if not quiz:
        return jsonify({'error': 'Invalid or expired code'}), 404
    
    question_ids = json.loads(quiz['question_ids'])
    questions = []
    for qid in question_ids:
        q = db.get_question_by_id(qid)
        if q:
            questions.append(q)
    
    participant = db.add_participant(quiz['id'], user_id)
    
    return jsonify({
        'quiz_id': quiz['id'],
        'questions': questions,
        'participant_id': participant['id'],
        'time_per_question': quiz.get('time_per_question', 30)
    })

# 7. Submit answer
@app.route('/api/quiz/submit', methods=['POST'])
def submit_answer():
    data = request.json
    participant_id = data.get('participant_id')
    answers = data.get('answers')
    time_taken = data.get('time_taken')
    
    if not participant_id or answers is None:
        return jsonify({'error': 'Missing data'}), 400
    
    conn = db.get_db()
    part = conn.execute('SELECT * FROM participants WHERE id = ?', (participant_id,)).fetchone()
    if not part:
        return jsonify({'error': 'Participant not found'}), 404
    quiz_id = part['quiz_id']
    
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    if not quiz:
        return jsonify({'error': 'Quiz not found'}), 404
    question_ids = json.loads(quiz['question_ids'])
    
    all_q = db.get_all_questions()
    q_map = {q['id']: q for q in all_q}
    
    score = 0
    for i, qid in enumerate(question_ids):
        if i < len(answers):
            chosen = answers[i]
            correct = q_map[qid]['correct']
            if chosen == correct:
                score += 1
            else:
                score -= 1
    
    db.update_participant(participant_id, answers, score, time_taken)
    return jsonify({'score': score})

# 8. Finish quiz
@app.route('/api/quiz/finish', methods=['POST'])
def finish_quiz():
    data = request.json
    quiz_id = data.get('quiz_id')
    if not quiz_id:
        return jsonify({'error': 'Quiz ID required'}), 400
    db.finish_quiz(quiz_id)
    return jsonify({'message': 'Quiz finished'})

# 9. Get results
@app.route('/api/quiz/results/<int:quiz_id>', methods=['GET'])
def get_results(quiz_id):
    results = db.get_quiz_results(quiz_id)
    return jsonify(results)

# 10. Serve the frontend
@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html')

# ---------- Run the app ----------
if __name__ == '__main__':
    # Initialize database
    db.init_db()
    
    # Get port from environment (Railway sets this automatically)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(debug=False, host='0.0.0.0', port=port)