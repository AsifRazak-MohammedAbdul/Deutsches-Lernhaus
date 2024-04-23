from flask import Flask, request, session, render_template, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import os, random
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = '@DeutschesLearnhaus123'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'vocab.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Vocabulary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    german = db.Column(db.String(100), nullable=False)
    english = db.Column(db.String(100), nullable=False)

def populate_db():
    if not Vocabulary.query.first():
        df = pd.read_excel(os.path.join(basedir, 'vocab.xlsx'), sheet_name='Tabelle1') 
        for index, row in df.iterrows():
            word = Vocabulary(german=row['german'], english=row['english'])
            db.session.add(word)
        db.session.commit()
        print("Database populated with vocabulary.")

with app.app_context():
    db.create_all()
    populate_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_game():
    session['total_questions'] = int(request.form['length'])
    session['correct_answers'] = 0
    session['questions_asked'] = 0
    session['difficulty'] = request.form['difficulty']
    session['direction'] = request.form['direction']
    session['game_type'] = request.form['game_type']
    session['wrong_answers'] = []  # Store wrong answers for the results table
    if session['game_type'] == 'multiple_choice':
        return redirect(url_for('next_multiple_choice_question'))
    else:
        return redirect(url_for('next_question'))

@app.route('/question')
def next_question():
    if 'total_questions' not in session or session['questions_asked'] >= session['total_questions']:
        return redirect(url_for('game_over'))
    word = Vocabulary.query.order_by(db.func.random()).first()
    session['current_word_id'] = word.id
    session['current_word'] = word.german if session['direction'] == 'DE->EN' else word.english
    session['correct_translation'] = word.english if session['direction'] == 'DE->EN' else word.german
    return render_template('question.html', word=session['current_word'], direction=session['direction'])

@app.route('/check_translation_answer', methods=['POST'])
def check_translation_answer():
    # Retrieve the current word from the session
    word_id = session.get('current_word_id')
    word = Vocabulary.query.get(word_id)

    # If word not found, flash error and redirect to home
    if not word:
        flash('Word not found.', 'error')
        return redirect(url_for('home'))

    # check user answer
    user_answer = request.form['answer'].strip().lower()
    correct_answer = session.get('correct_translation', '').lower()

    correct = user_answer == correct_answer
    if correct:
        session['correct_answers'] += 1
    else:
        session['wrong_answers'].append({'german': word.german, 'english': word.english})

    # Increment the number of questions 
    session['questions_asked'] += 1
    session.modified = True
    
    # Add the logic to prepare a JSON response
    response = {
        'correct': correct,
        'correctAnswer': session['correct_translation'],
        'gameOver': session['questions_asked'] >= session['total_questions']
    }
    return jsonify(response)


@app.route('/check_multiple_choice_answer', methods=['POST'])
def check_multiple_choice_answer():
    word_id = session.get('current_word_id')
    word = Vocabulary.query.get(word_id)
    if not word:
        return jsonify({'error': 'Word not found'}), 404

    user_answer = request.form['answer'].strip().lower()
    correct_answer = session.get('correct_translation', '').lower()

    correct = user_answer == correct_answer
    if correct:
        session['correct_answers'] += 1
    else:
        session['wrong_answers'].append({'german': word.german, 'english': word.english})

    session['questions_asked'] += 1
    session.modified = True

    # Check if it's time to end the game
    game_over = session['questions_asked'] >= session['total_questions']
    next_question_url = url_for('next_multiple_choice_question') if not game_over else None

    response = {
        'correct': correct,
        'correctAnswer': session['correct_translation'],
        'nextQuestionUrl': next_question_url,
        'gameOver': game_over
    }
    return jsonify(response)



@app.route('/game_over')
def game_over():
    score = round((session['correct_answers'] / session['total_questions']) * 100, 2)
    required_score = 70 if session['difficulty'] == 'easy' else 80 if session['difficulty'] == 'medium' else 90
    won = score >= required_score
    wrong_answers = session.get('wrong_answers', [])
    session.clear()
    return render_template('game_over.html', won=won, score=score, required_score=required_score, wrong_answers=wrong_answers)

@app.route('/multiple_choice_question')
def next_multiple_choice_question():
    # Logic is similar to next_question but with multiple choices
    if 'total_questions' not in session or session['questions_asked'] >= session['total_questions']:
        return redirect(url_for('game_over'))
    correct_word = Vocabulary.query.order_by(db.func.random()).first()
    # Get three random words that are not the correct word
    options = [correct_word] + random.sample(Vocabulary.query.filter(Vocabulary.id != correct_word.id).all(), 3)
    random.shuffle(options)
    session['current_word_id'] = correct_word.id
    session['correct_translation'] = correct_word.english if session['direction'] == 'DE->EN' else correct_word.german
    session.modified = True
    return render_template('multiple_choice_question.html', word=correct_word, options=options, direction=session['direction'])

@app.route('/add_word', methods=['POST'])
def add_word():
    german_word = request.form['german_word'].strip().lower()
    english_word = request.form['english_word'].strip().lower()

    # Check if the word already exists in the database in either German or English
    existing_word = Vocabulary.query.filter((Vocabulary.german == german_word) | (Vocabulary.english == english_word)).first()

    # If the word exists, redirect back to home with an error message
    if existing_word:
        flash('This word already exists in the database!', 'error')
    else:
        # Otherwise, add the new word to the database
        new_word = Vocabulary(german=german_word, english=english_word)
        db.session.add(new_word)
        db.session.commit()
        flash('New word added successfully!', 'success')

    return redirect(url_for('home'))

@app.route('/display_words')
def display_words():
    words = Vocabulary.query.all()
    return render_template('display_words.html', words=words)

@app.route('/delete_word/<int:word_id>')
def delete_word(word_id):
    word_to_delete = Vocabulary.query.get_or_404(word_id)
    db.session.delete(word_to_delete)
    db.session.commit()
    flash('Word deleted successfully', 'success')
    return redirect(url_for('display_words'))

@app.route('/edit_word/<int:word_id>', methods=['GET', 'POST'])
def edit_word(word_id):
    word_to_edit = Vocabulary.query.get_or_404(word_id)
    if request.method == 'POST':
        german_word = request.form['german'].strip().lower()
        english_word = request.form['english'].strip().lower()
        word_to_edit.german = german_word
        word_to_edit.english = english_word
        db.session.commit()
        flash('Word updated successfully', 'success')
        return redirect(url_for('display_words'))
    return render_template('edit_word.html', word=word_to_edit)

if __name__ == '__main__':
    app.run(debug=True)