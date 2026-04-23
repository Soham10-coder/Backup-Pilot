# AWS Backup Project - Developer & Architecture Guide

Welcome to the internal guide for your Cloud Backup Application. This document summarizes everything that was built, how the different technical pieces come together, and how you can track down your data.

## 1. Project Overview & Architecture
This project is a fully-featured **Python Flask** web application designed to automatically compress local server directories and upload them to **Amazon S3** on a schedule (or manually). 

### The Tech Stack
*   **Backend:** Python 3 + Flask (Handles web routing and logic).
*   **Database:** SQLite via Flask-SQLAlchemy (Stores users, schedules, and backup history).
*   **Cloud Storage:** AWS Boto3 SDK (Communicates directly with Amazon S3).
*   **Task Scheduler:** APScheduler (Runs in the background and triggers backups at specific times).
*   **Server / Production Environment:** Amazon Linux 2023 EC2 Server, running Nginx (Reverse Proxy) and Gunicorn (WSGI Application Server).

---

## 2. Core Files & What They Do
Here is a breakdown of the most critical files in your project directory:

*   **`app.py`**: The heart of the application. It routes all web requests (like `/login`, `/dashboard`, `/api/start-backup`). It initializes the database and handles user security.
*   **`database.py`**: Defines your database tables (referred to as "Models" in Python). It contains the schemas for `User`, `Backup`, `Schedule`, and `Settings`. It creates the default Admin on startup.
*   **`backup.py`**: Contains the core logic for actually zipping a folder and pushing it securely to AWS S3 using Boto3.
*   **`scheduler.py`**: Configures `APScheduler`. This loop waits in the background and executes the logic from `backup.py` when a user's scheduled time arrives.
*   **`config.py`** & **`.env`**: Manage the security keys and database connections. The `.env` file is excluded from GitHub for security.
*   **`templates/`**: Contains all of your HTML files. These are rendered to the user.
*   **`requirements.txt`**: The list of Python modules (like `flask`, `boto3`) required to make the app work.

---

## 3. Where is the Database?

Because you are using **SQLite**, your database does not live on an external server like MySQL or Oracle. Instead, the database is a literal file that lives inside your project directory.

*   **Locally (On your Windows PC):** It is located at `D:\aws-backup-project\database.db`.
*   **On AWS EC2 (Production):** It is located at `/home/ec2-user/aws-backup-project/database.db`.

### How to View the Database Data:
To actually look at the rows and columns inside `database.db`, you cannot just open it in Notepad. You need an SQLite Viewer application.
1. Download a free program like **DB Browser for SQLite** (SQLiteBrowser).
2. Open the program and click *File > Open Database*.
3. Select your `database.db` file. 
4. Click the "Browse Data" tab to visually see all your users, backups, and settings!

---

## 4. How the Production Deployment Works

When deploying to AWS, we created a specialized web-server architecture that is dramatically different from running the app locally on Windows.

1.  **Nginx (Port 80):** When a user types `http://18.176.68.222` into their browser, the request hits the server on Port 80. Nginx is listening there. Nginx is incredibly fast at handling thousands of requests, but it doesn't understand Python. So, it securely hands the request over to Gunicorn.
2.  **Gunicorn (Port 8000):** Gunicorn is a Python WSGI server that translates the HTTP request into Python objects. We configured it to run 1 "Worker" and 4 "Threads". (Limiting it to a single worker is incredibly important because if we had multiple workers, `APScheduler` would start 4 times, leading to duplicated backups!).
3.  **Systemd Services:** To ensure your app stays alive forever, we added `backupapp.service` to the Linux OS. If the AWS server crashes or reboots, Linux will automatically turn Gunicorn and Nginx back on without you having to touch it.

## 5. Security & GitHub
*   **GitHub Exclusion:** Your AWS access keys are hyper-sensitive. We created a `.gitignore` file so that your local `.env`, your AWS `.pem` server key, and your `database.db` (containing hashed passwords) are **never** accidentally submitted natively to your public open-source code on GitHub.
*   **In-App Keys:** The app allows you to save AWS credentials securely inside the Database via the Settings page. This dynamically binds AWS S3 to the web interface securely.
