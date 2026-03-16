import os
from datetime import datetime
from flask import Flask, render_template, url_for, redirect, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)

# --- CONFIGURATION ---
# For Vercel, we use /tmp for the SQLite DB to avoid permission issues
if os.environ.get('VERCEL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/food_secure.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///food_secure.db'

app.config['SECRET_KEY'] = 'jasreen_kour_secure_key_2026' 

# Initialize Professional Tools
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- DATABASE MODELS ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'donor' or 'ngo'
    donations = db.relationship('FoodItem', backref='donor', lazy=True)

class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    address = db.Column(db.String(200)) # Stores Custom Landmark
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    status = db.Column(db.String(20), default='available') # available, picked_up
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- AUTHORIZED NGO CREDENTIALS ---
NGO_ACCOUNTS = {
    'jasreeenkour748@gmail.com': 'ngoPass123',
    'ngo@foodsecure.org': 'ngoPass456',
    'community@help.org': 'ngoPass789'
}

# --- ROUTES ---

@app.route('/')
def base_landing():
    if current_user.is_authenticated:
        if current_user.role == 'ngo':
            return redirect(url_for('ngo_home'))
        return redirect(url_for('home'))
    return render_template('base.html')

@app.route('/home')
@login_required
def home():
    if current_user.role != 'donor':
        return redirect(url_for('ngo_home'))
    user_posts = FoodItem.query.filter_by(donor_id=current_user.id).order_by(FoodItem.date_posted.desc()).all()
    return render_template('home.html', posts=user_posts)

@app.route('/ngo-home')
@login_required
def ngo_home():
    if current_user.role != 'ngo':
        return redirect(url_for('home'))
    available_food = FoodItem.query.filter_by(status='available').order_by(FoodItem.date_posted.desc()).all()
    return render_template('ngo-home.html', food_list=available_food)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(full_name=full_name, email=email, password=hashed_pw, role='donor')
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Email already registered. Try logging in.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.role == 'donor' and bcrypt.check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid Donor credentials.', 'danger')
    return render_template('login.html')

@app.route('/ngo-login', methods=['GET', 'POST'])
def ngo_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email in NGO_ACCOUNTS and NGO_ACCOUNTS[email] == password:
            user = User.query.filter_by(email=email).first()
            if not user:
                hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
                user = User(full_name="NGO Partner", email=email, password=hashed_pw, role='ngo')
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('ngo_home'))
        flash('Unauthorized NGO access.', 'danger')
    return render_template('ngo-login.html')

@app.route('/post-food', methods=['POST'])
@login_required
def post_food():
    new_food = FoodItem(
        title=request.form.get('title'),
        description=request.form.get('description'),
        address=request.form.get('custom_address'),
        lat=float(request.form.get('lat')) if request.form.get('lat') else None,
        lng=float(request.form.get('lng')) if request.form.get('lng') else None,
        donor_id=current_user.id
    )
    db.session.add(new_food)
    db.session.commit()
    flash('Food shared successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/mark-picked/<int:food_id>')
@login_required
def mark_picked(food_id):
    food = FoodItem.query.get_or_404(food_id)
    food.status = 'picked_up'
    db.session.commit()
    flash(f'{food.title} marked as picked up!', 'success')
    return redirect(url_for('ngo_home'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('base_landing'))

# --- VERCEL / LOCAL RUN ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
