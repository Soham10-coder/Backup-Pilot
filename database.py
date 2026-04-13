from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user') # admin / user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    backups = db.relationship('Backup', backref='user', lazy=True)
    schedules = db.relationship('Schedule', backref='user', lazy=True)
    settings = db.relationship('Settings', backref='user', uselist=False, lazy=True)

class Backup(db.Model):
    __tablename__ = 'backups'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.String(50))
    s3_path = db.Column(db.String(500))
    status = db.Column(db.String(50), default='pending') # pending, success, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Schedule(db.Model):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    frequency = db.Column(db.String(50), nullable=False) # daily / weekly / monthly
    backup_time = db.Column(db.String(50), nullable=False) # e.g. "14:30"
    folder_path = db.Column(db.String(500), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    next_run = db.Column(db.DateTime)

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    aws_access_key = db.Column(db.String(255))
    aws_secret_key = db.Column(db.String(255))
    bucket_name = db.Column(db.String(255))
    region = db.Column(db.String(100), default='us-east-1')
    email_notifications = db.Column(db.Boolean, default=False)
    notification_email = db.Column(db.String(120))

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_default_admin()

def create_default_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='admin', email='admin@example.com', password=hashed_pw, role='admin')
        db.session.add(admin)
        db.session.commit()
        
        # Give admin default settings
        default_settings = Settings(user_id=admin.id)
        db.session.add(default_settings)
        db.session.commit()
        print("Default admin created successfully.")
