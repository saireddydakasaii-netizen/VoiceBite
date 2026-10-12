from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'voice_food_ordering_secret_key_2026'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('database.sqlite')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize Database Tables
def init_db():
    conn = get_db_connection()
    with conn:
        # Users Table
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            number TEXT,
            address TEXT,
            alternate_number TEXT,
            profile_completed INTEGER DEFAULT 0
        )''')

        # Restaurants Table
        conn.execute('''CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            restaurant_name TEXT,
            manager_name TEXT,
            number TEXT,
            address TEXT,
            alternate_number TEXT,
            upi_id TEXT,
            qr_image TEXT,
            profile_completed INTEGER DEFAULT 0
        )''')

        # Food Items Table (with 24hr stock management)
        conn.execute('''CREATE TABLE IF NOT EXISTS food_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id INTEGER,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            image TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
        )''')

        # Orders Table
        conn.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            restaurant_id INTEGER,
            items TEXT,
            total_amount REAL,
            payment_method TEXT,
            status TEXT DEFAULT 'Order Confirmed',
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
        )''')
    conn.close()

init_db()

# --- LOGOUT ROUTES ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing_page')) 

@app.route('/restaurant/logout')
def restaurant_logout():
    session.clear()
    return redirect('/restaurant/login')

# --- PAGE ROUTES (VIEWS) ---

@app.route('/')
def landing_page():
    return render_template('landing.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/profile')
def profile_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('profile.html')

@app.route('/home')
def home_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('home.html')

@app.route('/menu/<int:restaurant_id>')
def menu_page(restaurant_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('menu.html', restaurant_id=restaurant_id)

@app.route('/cart')
def cart_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('cart.html')

@app.route('/track/<int:order_id>')
def track_page(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('track.html', order_id=order_id)

# Restaurant Portal Routes
@app.route('/restaurant/signup')
def rest_signup_page():
    return render_template('restaurant_signup.html')

@app.route('/restaurant/login')
def rest_login_page():
    return render_template('restaurant_login.html')

@app.route('/restaurant/profile')
def rest_profile_page():
    if 'restaurant_id' not in session:
        return redirect(url_for('rest_login_page'))
    return render_template('restaurant_profile.html')

@app.route('/restaurant/dashboard')
def restaurant_dashboard():
    if 'restaurant_id' not in session:
        return redirect(url_for('restaurant_login_page'))
    return render_template('restaurant_dashboard.html')


# --- API ENDPOINTS (AUTHENTICATION & DATA) ---

# User Signup
@app.route('/api/signup', methods=['POST'])
def auth_signup():
    data = request.json
    email = data.get('email')
    password = generate_password_hash(data.get('password'))
    
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
            session['user_id'] = cursor.lastrowid
            session['role'] = 'user'
        return jsonify({'success': True, 'redirect': '/profile'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Email already registered!'}), 400
    finally:
        conn.close()

# User Login
@app.route('/api/login', methods=['POST'])
def auth_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['role'] = 'user'
        if user['profile_completed'] == 1:
            return jsonify({'success': True, 'redirect': '/home'})
        else:
            return jsonify({'success': True, 'redirect': '/profile'})
    return jsonify({'success': False, 'error': 'Invalid email or password!'}), 400

# Complete User Profile
@app.route('/api/user/profile', methods=['GET', 'POST'])
def handle_user_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.json or request.form
        name = data.get('name')
        number = data.get('number') or data.get('phone')
        email = data.get('email')
        address = data.get('address')
        alternate_number = data.get('alternate_number')
        
        with conn:
            conn.execute('''UPDATE users SET name=?, number=?, address=?, alternate_number=?, profile_completed=1 WHERE id=?''',
                         (name, number, address, alternate_number, session['user_id']))
        conn.close()
        return jsonify({'success': True, 'message': 'Profile updated successfully!', 'redirect': '/home'})
    else:
        user = conn.execute('SELECT name, email, number as phone, address FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
        return jsonify(dict(user) if user else {})


# Restaurant Signup
@app.route('/api/restaurant/signup', methods=['POST'])
def rest_signup():
    data = request.json
    email = data.get('email')
    password = generate_password_hash(data.get('password'))
    
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute('INSERT INTO restaurants (email, password) VALUES (?, ?)', (email, password))
            session['restaurant_id'] = cursor.lastrowid
            session['role'] = 'restaurant'
        return jsonify({'success': True, 'redirect': '/restaurant/profile'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Email already registered!'}), 400
    finally:
        conn.close()

# Restaurant Login
@app.route('/api/restaurant/login', methods=['POST'])
def rest_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    conn = get_db_connection()
    rest = conn.execute('SELECT * FROM restaurants WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    if rest and check_password_hash(rest['password'], password):
        session['restaurant_id'] = rest['id']
        session['role'] = 'restaurant'
        if rest['profile_completed'] == 1:
            return jsonify({'success': True, 'redirect': '/restaurant/dashboard'})
        else:
            return jsonify({'success': True, 'redirect': '/restaurant/profile'})
    return jsonify({'success': False, 'error': 'Invalid credentials!'}), 400

# Save Restaurant Profile & QR code upload
@app.route('/api/restaurant/profile', methods=['GET', 'POST'])
def handle_restaurant_profile():
    if 'restaurant_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if request.method == 'POST':
        restaurant_name = request.form.get('restaurant_name')
        manager_name = request.form.get('manager_name')
        number = request.form.get('number') or request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        alternate_number = request.form.get('alternate_number')
        upi_id = request.form.get('upi_id')
        
        qr_filename = None
        if 'qr_image' in request.files:
            file = request.files['qr_image']
            if file and file.filename != '':
                qr_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], qr_filename))
        elif 'upi_qr' in request.files:
            file = request.files['upi_qr']
            if file and file.filename != '':
                qr_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], qr_filename))
                
        with conn:
            if qr_filename:
                conn.execute('''UPDATE restaurants SET restaurant_name=?, manager_name=?, number=?, address=?, upi_id=?, qr_image=?, profile_completed=1 WHERE id=?''',
                             (restaurant_name, manager_name, number, address, upi_id, qr_filename, session['restaurant_id']))
            else:
                conn.execute('''UPDATE restaurants SET restaurant_name=?, manager_name=?, number=?, address=?, upi_id=?, profile_completed=1 WHERE id=?''',
                             (restaurant_name, manager_name, number, address, upi_id, session['restaurant_id']))
        conn.close()
        return jsonify({'success': True, 'message': 'Restaurant profile updated successfully!', 'redirect': '/restaurant/dashboard'})
    else:
        rest = conn.execute('SELECT restaurant_name, email, number as phone, upi_id, qr_image FROM restaurants WHERE id = ?', (session['restaurant_id'],)).fetchone()
        conn.close()
        return jsonify(dict(rest) if rest else {})


# Get Restaurants List for Users
@app.route('/api/restaurants', methods=['GET'])
def get_restaurants():
    conn = get_db_connection()
    restaurants = conn.execute('SELECT id, restaurant_name, address FROM restaurants WHERE profile_completed=1').fetchall()
    conn.close()
    return jsonify([dict(row) for row in restaurants])

# Get Menu Items for Restaurant
@app.route('/api/restaurant/<int:rest_id>/menu', methods=['GET'])
def get_menu(rest_id):
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM food_items WHERE restaurant_id = ? AND quantity > 0', (rest_id,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in items])

@app.route('/api/menu/<int:restaurant_id>')
def get_menu_by_id(restaurant_id):
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM food_items WHERE restaurant_id = ?', (restaurant_id,)).fetchall()
    conn.close()
    return jsonify([dict(item) for item in items])

# Get Restaurant Dashboard Items
@app.route('/api/restaurant/dashboard/items', methods=['GET'])
def get_restaurant_dashboard_items():
    if 'restaurant_id' not in session:
        return jsonify([])
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM food_items WHERE restaurant_id = ?', (session['restaurant_id'],)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in items])

# Add Food Item (Restaurant Manager)
@app.route('/api/restaurant/food', methods=['POST'])
def add_food_item():
    if 'restaurant_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    name = request.form.get('name')
    quantity = request.form.get('quantity')
    price = request.form.get('price')
    
    image_filename = ''
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            image_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            
    conn = get_db_connection()
    with conn:
        conn.execute('INSERT INTO food_items (restaurant_id, name, quantity, price, image) VALUES (?, ?, ?, ?, ?)',
                     (session['restaurant_id'], name, quantity, price, image_filename))
    conn.close()
    return jsonify({'success': True})

@app.route('/reset-data')
def reset_data():
    conn = get_db_connection()
    with conn:
        conn.execute('DELETE FROM restaurants')
        conn.execute('DELETE FROM food_items')
        conn.execute('DELETE FROM orders')
        conn.execute('DELETE FROM users')
    conn.close()
    session.clear()
    return "All database records have been reset! <a href='/'>Go to Home</a>"

@app.route('/api/all-food-items')
def get_all_food_items():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM food_items').fetchall()
    conn.close()
    return jsonify([dict(item) for item in items])

@app.route('/forgot-password')
def forgot_password_page():
    return render_template('forgot_password.html')

@app.route('/restaurant/forgot-password')
def rest_forgot_password_page():
    return render_template('restaurant_forgot_password.html')

@app.route('/api/user/reset-password', methods=['POST'])
def user_reset_password():
    data = request.json
    email = data.get('email')
    new_password = generate_password_hash(data.get('new_password'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Email address not found!'}), 404
        
    with conn:
        conn.execute('UPDATE users SET password = ? WHERE email = ?', (new_password, email))
    conn.close()
    return jsonify({'success': True, 'message': 'Password updated successfully! Please login.'})

@app.route('/api/restaurant/reset-password', methods=['POST'])
def rest_reset_password():
    data = request.json
    email = data.get('email')
    new_password = generate_password_hash(data.get('new_password'))
    
    conn = get_db_connection()
    rest = conn.execute('SELECT * FROM restaurants WHERE email = ?', (email,)).fetchone()
    if not rest:
        conn.close()
        return jsonify({'success': False, 'error': 'Restaurant email not found!'}), 404
        
    with conn:
        conn.execute('UPDATE restaurants SET password = ? WHERE email = ?', (new_password, email))
    conn.close()
    return jsonify({'success': True, 'message': 'Password updated successfully! Please login.'})

# Place Order Endpoint
@app.route('/api/order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    data = request.json
    restaurant_id = data.get('restaurant_id')
    items = str(data.get('items'))
    total_amount = data.get('total_amount')
    payment_method = data.get('payment_method')
    
    conn = get_db_connection()
    with conn:
        cursor = conn.execute('INSERT INTO orders (user_id, restaurant_id, items, total_amount, payment_method) VALUES (?, ?, ?, ?, ?)',
                              (session['user_id'], restaurant_id, items, total_amount, payment_method))
        order_id = cursor.lastrowid
    conn.close()
    return jsonify({'success': True, 'order_id': order_id})

if __name__ == '__main__':
    app.run(debug=True, port=3000)