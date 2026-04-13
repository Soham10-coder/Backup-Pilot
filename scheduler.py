from apscheduler.schedulers.background import BackgroundScheduler
import datetime
from backup import run_backup_job
from database import db, Backup, Settings, User, Schedule

scheduler = BackgroundScheduler()

def scheduled_backup_task(app, user_id, folder_path):
    with app.app_context():
        # Get admin settings for AWS credentials
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            print("No admin user found for settings.")
            return

        settings = Settings.query.filter_by(user_id=admin.id).first()
        if not settings or not settings.aws_access_key:
            print("Admin has not configured AWS settings.")
            return
            
        user_settings = Settings.query.filter_by(user_id=user_id).first()
        notification_email = None
        if user_settings and user_settings.email_notifications:
            notification_email = user_settings.notification_email
            
        print(f"[{datetime.datetime.now()}] Starting scheduled backup for user {user_id}")
        success, zip_file, size, s3_path, msg = run_backup_job(
            folder_path=folder_path,
            aws_access_key=settings.aws_access_key,
            aws_secret_key=settings.aws_secret_key,
            bucket_name=settings.bucket_name,
            region=settings.region,
            notification_email=notification_email
        )
        
        status = 'success' if success else 'failed'
        new_backup = Backup(
            user_id=user_id,
            filename=zip_file if zip_file else "FAILED",
            file_size=size if size else "0",
            s3_path=s3_path if s3_path else "",
            status=status
        )
        db.session.add(new_backup)
        db.session.commit()
        print(f"[{datetime.datetime.now()}] Scheduled backup complete for user {user_id}: {status}")

def init_scheduler(app):
    scheduler.start()
    
    # We would ideally load existing schedules from DB on startup,
    # but for simplicity, the API will add jobs dynamically.
    with app.app_context():
        schedules = Schedule.query.filter_by(is_active=True).all()
        for sched in schedules:
            add_job_for_schedule(app, sched)

def add_job_for_schedule(app, schedule):
    job_id = f"backup_job_{schedule.id}"
    
    # remove existing if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    if not schedule.is_active:
        return
        
    hour, minute = 0, 0
    try:
        if schedule.backup_time:
            time_parts = schedule.backup_time.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
    except:
        pass
        
    if schedule.frequency == 'daily':
        trigger = 'cron'
        scheduler.add_job(
            func=scheduled_backup_task,
            trigger=trigger,
            hour=hour,
            minute=minute,
            args=[app, schedule.user_id, schedule.folder_path],
            id=job_id
        )
    elif schedule.frequency == 'weekly': # e.g. every Sunday
        trigger = 'cron'
        scheduler.add_job(
            func=scheduled_backup_task,
            trigger=trigger,
            day_of_week='sun',
            hour=hour,
            minute=minute,
            args=[app, schedule.user_id, schedule.folder_path],
            id=job_id
        )
    elif schedule.frequency == 'monthly': # 1st of month
        trigger = 'cron'
        scheduler.add_job(
            func=scheduled_backup_task,
            trigger=trigger,
            day='1',
            hour=hour,
            minute=minute,
            args=[app, schedule.user_id, schedule.folder_path],
            id=job_id
        )

def remove_job(schedule_id):
    job_id = f"backup_job_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
