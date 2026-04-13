from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, init_db, User, Backup, Schedule, Settings
from config import Config
from scheduler import init_scheduler, add_job_for_schedule, remove_job
from backup import run_backup_job
import os
import boto3
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- TEMPLATE ROUTES ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        remember = data.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/backup')
@login_required
def backup():
    return render_template('backup.html', user=current_user)

@app.route('/schedule')
@login_required
def schedule():
    sched = Schedule.query.filter_by(user_id=current_user.id).first()
    return render_template('schedule.html', user=current_user, schedule=sched)

@app.route('/history')
@login_required
def history():
    return render_template('history.html', user=current_user)

@app.route('/settings')
@login_required
def settings_page():
    # Only admin sees AWS stuff, users see their own settings
    settings = Settings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Settings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    admin_settings = None
    if current_user.role == 'admin':
        admin_settings = settings
        
    return render_template('settings.html', user=current_user, settings=settings, admin_settings=admin_settings)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('admin/users.html', user=current_user, users=users)

@app.route('/admin/user/<int:id>')
@login_required
def view_user(id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    target_user = User.query.get_or_404(id)
    return render_template('admin/user_detail.html', user=current_user, target_user=target_user)


# --- API ROUTES ---

@app.route('/api/start-backup', methods=['POST'])
@login_required
def start_backup():
    data = request.json
    folder_path = data.get('folder_path')
    
    if not folder_path or not os.path.exists(folder_path):
        return jsonify({'success': False, 'message': 'Invalid folder path.'}), 400
        
    admin = User.query.filter_by(role='admin').first()
    admin_settings = Settings.query.filter_by(user_id=admin.id).first()
    
    if not admin_settings or not admin_settings.aws_access_key:
        return jsonify({'success': False, 'message': 'AWS Configuration missing. Ask Admin to setup Settings.'}), 400
        
    user_settings = Settings.query.filter_by(user_id=current_user.id).first()
    notification_email = user_settings.notification_email if (user_settings and user_settings.email_notifications) else None
    
    success, zip_file, size, s3_path, msg = run_backup_job(
        folder_path=folder_path,
        aws_access_key=admin_settings.aws_access_key,
        aws_secret_key=admin_settings.aws_secret_key,
        bucket_name=admin_settings.bucket_name,
        region=admin_settings.region,
        notification_email=notification_email
    )
    
    status = 'success' if success else 'failed'
    
    new_backup = Backup(
        user_id=current_user.id,
        filename=zip_file if zip_file else "failed_backup",
        file_size=size if size else "0MB",
        s3_path=s3_path if s3_path else "",
        status=status
    )
    db.session.add(new_backup)
    db.session.commit()
    
    return jsonify({
        'success': success,
        'message': msg,
        'backup': {
            'filename': new_backup.filename,
            'size': new_backup.file_size,
            'date': new_backup.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'status': status
        }
    })

@app.route('/api/backup-history', methods=['GET'])
@login_required
def get_backup_history():
    if current_user.role == 'admin':
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
    else:
        backups = Backup.query.filter_by(user_id=current_user.id).order_by(Backup.created_at.desc()).all()
        
    data = []
    for b in backups:
        u = User.query.get(b.user_id)
        data.append({
            'id': b.id,
            'username': u.username if u else 'Unknown',
            'filename': b.filename,
            'file_size': b.file_size,
            'status': b.status,
            'created_at': b.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({'data': data})

@app.route('/api/storage-stats', methods=['GET'])
@login_required
def get_storage_stats():
    if current_user.role == 'admin':
        total_users = User.query.count()
        backups = Backup.query.all()
    else:
        total_users = 1
        backups = Backup.query.filter_by(user_id=current_user.id).all()
        
    total_backups = len(backups)
    
    total_mb = 0
    for b in backups:
        if b.file_size and 'MB' in b.file_size:
            try:
                total_mb += float(b.file_size.replace('MB', '').strip())
            except: pass
            
    recent_activity = {}
    for b in backups[-5:]:
         date_str = b.created_at.strftime('%Y-%m-%d')
         recent_activity[date_str] = recent_activity.get(date_str, 0) + 1
         
    return jsonify({
        'total_users': total_users,
        'total_backups': total_backups,
        'total_storage_mb': round(total_mb, 2),
        'last_backup': backups[-1].created_at.strftime('%Y-%m-%d %H:%M:%S') if backups else 'Never',
        'activity_labels': list(recent_activity.keys()),
        'activity_data': list(recent_activity.values())
    })

@app.route('/api/save-settings', methods=['POST'])
@login_required
def save_settings():
    data = request.json
    settings = Settings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Settings(user_id=current_user.id)
        db.session.add(settings)
        
    # User settings
    settings.email_notifications = data.get('email_notifications', False)
    settings.notification_email = data.get('notification_email', '')
    
    # Password change
    new_password = data.get('new_password')
    if new_password:
        current_user.password = generate_password_hash(new_password)
        
    # Admin only settings
    if current_user.role == 'admin':
        if 'aws_access_key' in data: settings.aws_access_key = str(data['aws_access_key']).strip()
        if 'aws_secret_key' in data: settings.aws_secret_key = str(data['aws_secret_key']).strip()
        if 'bucket_name' in data: settings.bucket_name = str(data['bucket_name']).strip()
        if 'region' in data: settings.region = str(data['region']).strip()
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Settings saved successfully'})

@app.route('/api/save-schedule', methods=['POST'])
@login_required
def save_schedule():
    data = request.json
    sched = Schedule.query.filter_by(user_id=current_user.id).first()
    
    if not sched:
        sched = Schedule(user_id=current_user.id)
        db.session.add(sched)
        
    sched.frequency = data.get('frequency', 'daily')
    sched.backup_time = data.get('backup_time', '00:00')
    sched.folder_path = data.get('folder_path', '')
    sched.is_active = data.get('is_active', False)
    
    db.session.commit()
    
    add_job_for_schedule(app, sched)
    
    return jsonify({'success': True, 'message': 'Schedule updated!'})

@app.route('/api/add-user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')
    
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
        
    new_user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role=role
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'User created'})

@app.route('/api/delete-user', methods=['POST'])
@login_required
def delete_user():
    if current_user.role != 'admin':
         return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    data = request.json
    user_id = data.get('id')
    user = User.query.get(user_id)
    if user and user.role != 'admin': # Don't delete admin
        # delete schedules, backups, settings
        Backup.query.filter_by(user_id=user.id).delete()
        Schedule.query.filter_by(user_id=user.id).delete()
        Settings.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Cannot delete user'})
    
@app.route('/api/delete-backup', methods=['POST'])
@login_required
def delete_backup():
    # Only let users delete their own, admin can delete any
    data = request.json
    b_id = data.get('id')
    backup = Backup.query.get(b_id)
    
    if not backup:
        return jsonify({'success': False, 'message': 'Not found'}), 404
        
    if current_user.role != 'admin' and backup.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    # Delete from S3
    admin = User.query.filter_by(role='admin').first()
    admin_settings = Settings.query.filter_by(user_id=admin.id).first()
    
    try:
        s3 = boto3.client('s3',
            aws_access_key_id=admin_settings.aws_access_key,
            aws_secret_access_key=admin_settings.aws_secret_key,
            region_name=admin_settings.region
        )
        s3.delete_object(Bucket=admin_settings.bucket_name, Key=backup.s3_path)
    except Exception as e:
        print(f"S3 Delete Error: {e}")
        # Proceed to delete from db anyway
        
    db.session.delete(backup)
    db.session.commit()
    return jsonify({'success': True})
    
@app.route('/api/download-backup', methods=['POST'])
@login_required
def download_backup():
    data = request.json
    b_id = data.get('id')
    backup = Backup.query.get(b_id)
    
    if not backup:
        return jsonify({'success': False, 'message': 'Not found'}), 404
        
    if current_user.role != 'admin' and backup.user_id != current_user.id:
         return jsonify({'success': False, 'message': 'Unauthorized'}), 403
         
    admin = User.query.filter_by(role='admin').first()
    admin_settings = Settings.query.filter_by(user_id=admin.id).first()
    try:
         s3 = boto3.client('s3',
            aws_access_key_id=admin_settings.aws_access_key,
            aws_secret_access_key=admin_settings.aws_secret_key,
            region_name=admin_settings.region
        )
         url = s3.generate_presigned_url('get_object',
                                        Params={'Bucket': admin_settings.bucket_name,
                                                'Key': backup.s3_path},
                                        ExpiresIn=3600)
         return jsonify({'success': True, 'url': url})
    except Exception as e:
         return jsonify({'success': False, 'message': str(e)}), 400

if __name__ == '__main__':
    init_db(app)
    init_scheduler(app)
    app.run(debug=True, use_reloader=False) # set use_reloader=False for apscheduler
