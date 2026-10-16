from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chainwealth_secret_key_2026_secure')

# Writable path on Render free tier
DB_PATH = '/tmp/chainwealth.db' if os.environ.get('RENDER') else os.path.join(os.path.dirname(__file__), 'chainwealth.db')

CRYPTO_PRICES = {
    'BTC': 67500.00,
    'ETH': 2650.00,
    'SOL': 145.00,
    'BNB': 580.00,
    'XRP': 0.55,
    'ADA': 0.38,
    'DOGE': 0.12,
    'DOT': 4.20
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            asset TEXT,
            usd_amount REAL,
            quantity REAL,
            price_at_purchase REAL,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        c.execute("SELECT * FROM users WHERE username = 'admin'")
        if not c.fetchone():
            admin_pass = generate_password_hash('ChainWealth@Admin2026')
            c.execute("INSERT INTO users (username, email, password, balance, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                      ('admin', 'admin@chainwealthcapital.com', admin_pass, 0.0, 1, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print("Database ready")
    except Exception as e:
        print(f"DB error: {e}")

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        if not username or not email or not password:
            flash('All fields required')
            return redirect(url_for('register'))
        conn = get_db()
        try:
            hashed = generate_password_hash(password)
            conn.execute("INSERT INTO users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                         (username, email, hashed, datetime.now().isoformat()))
            conn.commit()
            flash('Account created! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            flash('Logged in successfully')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    investments = conn.execute("SELECT * FROM investments WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],)).fetchall()
    deposits = conn.execute("SELECT * FROM deposits WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],)).fetchall()
    conn.close()
    portfolio = {}
    total_invested = 0
    for inv in investments:
        asset = inv['asset']
        if asset not in portfolio:
            portfolio[asset] = {'quantity': 0, 'invested': 0}
        portfolio[asset]['quantity'] += inv['quantity']
        portfolio[asset]['invested'] += inv['usd_amount']
        total_invested += inv['usd_amount']
    current_value = sum(data['quantity'] * CRYPTO_PRICES.get(asset, 0) for asset, data in portfolio.items())
    return render_template('dashboard.html', user=user, investments=investments, deposits=deposits,
                           portfolio=portfolio, prices=CRYPTO_PRICES, total_invested=total_invested, current_value=current_value)

@app.route('/invest', methods=['POST'])
def invest():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    asset = request.form.get('asset')
    usd_amount = float(request.form.get('amount', 0))
    if asset not in CRYPTO_PRICES or usd_amount <= 0:
        return jsonify({'error': 'Invalid investment'}), 400
    conn = get_db()
    user = conn.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    if user['balance'] < usd_amount:
        conn.close()
        return jsonify({'error': 'Insufficient balance'}), 400
    price = CRYPTO_PRICES[asset]
    quantity = usd_amount / price
    conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (usd_amount, session['user_id']))
    conn.execute("INSERT INTO investments (user_id, asset, usd_amount, quantity, price_at_purchase, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                 (session['user_id'], asset, usd_amount, quantity, price, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Invested ${usd_amount:.2f} in {asset}'})

@app.route('/request_deposit', methods=['POST'])
def request_deposit():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    amount = float(request.form.get('amount', 0))
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
    conn = get_db()
    conn.execute("INSERT INTO deposits (user_id, amount, status, created_at) VALUES (?, ?, 'pending', ?)",
                 (session['user_id'], amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Deposit request submitted'})

@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Admin access required')
        return redirect(url_for('login'))
    conn = get_db()
    users = conn.execute("SELECT id, username, email, balance, is_admin, created_at FROM users ORDER BY created_at DESC").fetchall()
    pending_deposits = conn.execute('''SELECT d.id, d.amount, d.created_at, u.username, u.email 
                                       FROM deposits d JOIN users u ON d.user_id = u.id 
                                       WHERE d.status = 'pending' ORDER BY d.created_at DESC''').fetchall()
    conn.close()
    return render_template('admin.html', users=users, pending_deposits=pending_deposits)

@app.route('/admin/activate_balance', methods=['POST'])
def activate_balance():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    user_id = request.form.get('user_id')
    amount = float(request.form.get('amount', 0))
    action = request.form.get('action')
    if not user_id or amount < 0:
        return jsonify({'error': 'Invalid'}), 400
    conn = get_db()
    if action == 'set':
        conn.execute("UPDATE users SET balance = ? WHERE id = ?", (amount, user_id))
    else:
        conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Balance updated'})

@app.route('/admin/approve_deposit', methods=['POST'])
def approve_deposit():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    deposit_id = request.form.get('deposit_id')
    conn = get_db()
    dep = conn.execute("SELECT * FROM deposits WHERE id = ? AND status = 'pending'", (deposit_id,)).fetchone()
    if not dep:
        conn.close()
        return jsonify({'error': 'Deposit not found'}), 404
    conn.execute("UPDATE deposits SET status = 'approved' WHERE id = ?", (deposit_id,))
    conn.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (dep['amount'], dep['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Deposit approved'})

@app.route('/admin/reject_deposit', methods=['POST'])
def reject_deposit():
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    deposit_id = request.form.get('deposit_id')
    conn = get_db()
    conn.execute("UPDATE deposits SET status = 'rejected' WHERE id = ?", (deposit_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
