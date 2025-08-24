from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'demo_secret_key'

# Database setup
DATABASE = 'users.db'

def init_db():
    """Initialize the database with users, notes, and game stats tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT DEFAULT '',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            ties INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id)
        )
    ''')

    # Create a demo user (username: demo, password: demo123)
    demo_password_hash = generate_password_hash('demo123')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password_hash) 
        VALUES (?, ?, ?)
    ''', ('demo', 'demo@example.com', demo_password_hash))

    conn.commit()
    conn.close()

def get_user(username):
    """Get user from database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

@app.route('/')
def landing():
    """Landing page"""
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = get_user(username)

        if user and check_password_hash(user[3], password):  # user[3] is password_hash
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page and handler"""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        if get_user(username):
            flash('Username already exists', 'error')
            return render_template('register.html')

        # Create new user
        password_hash = generate_password_hash(password)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash) 
                VALUES (?, ?, ?)
            ''', (username, email, password_hash))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'error')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard - protected route"""
    if 'user_id' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('login'))

    return render_template('dashboard.html', username=session['username'])

@app.route('/notepad', methods=['GET', 'POST'])
def notepad():
    """Notepad page - protected route"""
    if 'user_id' not in session:
        flash('Please login to access the notepad', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        # Save notes
        notes_content = request.form['notes']

        # Check if user already has notes
        cursor.execute('SELECT id FROM notes WHERE user_id = ?', (user_id,))
        existing_note = cursor.fetchone()

        if existing_note:
            # Update existing notes
            cursor.execute('''
                UPDATE notes SET content = ?, last_updated = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (notes_content, user_id))
        else:
            # Create new notes entry
            cursor.execute('''
                INSERT INTO notes (user_id, content) VALUES (?, ?)
            ''', (user_id, notes_content))

        conn.commit()
        flash('Notes saved successfully!', 'success')

    # Fetch user's notes
    cursor.execute('SELECT content, last_updated FROM notes WHERE user_id = ?', (user_id,))
    note_data = cursor.fetchone()

    notes = note_data[0] if note_data else ''
    last_saved = note_data[1] if note_data else None

    # Format last_saved timestamp
    if last_saved:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(last_saved.replace('Z', '+00:00'))
            last_saved = dt.strftime('%Y-%m-%d at %I:%M %p')
        except:
            last_saved = last_saved

    conn.close()

    return render_template('notepad.html',
                         username=session['username'],
                         notes=notes,
                         last_saved=last_saved)

@app.route('/tictactoe')
def tictactoe():
    """Tic Tac Toe game - protected route"""
    if 'user_id' not in session:
        flash('Please login to access the game', 'error')
        return redirect(url_for('login'))

    # Get leaderboard data
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.username, g.wins 
        FROM users u 
        JOIN game_stats g ON u.id = g.user_id 
        WHERE g.wins > 0
        ORDER BY g.wins DESC 
        LIMIT 5
    ''')
    leaderboard = cursor.fetchall()
    conn.close()

    return render_template('tictactoe.html', username=session['username'], leaderboard=leaderboard)

@app.route('/update_game_stats', methods=['POST'])
def update_game_stats():
    """Update game statistics"""
    if 'user_id' not in session:
        return jsonify({'status': 'error'}), 401

    user_id = session['user_id']
    result = request.json.get('result')  # 'win', 'loss', or 'tie'

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Check if user has stats record
    cursor.execute('SELECT wins, losses, ties FROM game_stats WHERE user_id = ?', (user_id,))
    stats = cursor.fetchone()

    if stats:
        wins, losses, ties = stats
        if result == 'win':
            wins += 1
        elif result == 'loss':
            losses += 1
        elif result == 'tie':
            ties += 1

        cursor.execute('''
            UPDATE game_stats SET wins = ?, losses = ?, ties = ? WHERE user_id = ?
        ''', (wins, losses, ties, user_id))
    else:
        # Create new stats record
        wins = 1 if result == 'win' else 0
        losses = 1 if result == 'loss' else 0
        ties = 1 if result == 'tie' else 0

        cursor.execute('''
            INSERT INTO game_stats (user_id, wins, losses, ties) VALUES (?, ?, ?, ?)
        ''', (user_id, wins, losses, ties))

    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})


@app.route('/wordgame')
def wordgame():
    """Word game - protected route"""
    if 'user_id' not in session:
        flash('Please login to access the word game', 'error')
        return redirect(url_for('login'))

    return render_template('wordgame.html', username=session['username'])

@app.route('/logout')
def logout():
    """Logout handler"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('landing'))

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    app.run(debug=False, host='0.0.0.0', port=80)