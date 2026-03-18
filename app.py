import os
import sqlite3
import csv
import io
from datetime import date, datetime
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
    make_response,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "jobtracker.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

STATUS_OPTIONS = [
    "Saved",
    "Applied",
    "In Progress",
    "Interview",
    "Rejected",
    "Accepted",
    "Offer",
]

PRIORITY_OPTIONS = ["High", "Medium", "Low"]
WORK_MODE_OPTIONS = ["Remote", "Hybrid", "Onsite"]
JOB_SOURCE_OPTIONS = [
    "LinkedIn",
    "Indeed",
    "Company Website",
    "Referral",
    "Handshake",
    "Dice",
    "Other",
]


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT 'User',
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Applied',
            location TEXT,
            applied_date TEXT,
            due_date TEXT,
            follow_up_date TEXT,
            priority TEXT,
            job_source TEXT,
            salary TEXT,
            work_mode TEXT,
            resume_version TEXT,
            interview_notes TEXT,
            rejection_reason TEXT,
            jd_text TEXT,
            link TEXT,
            notes TEXT,
            resume_filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    demo_email = "demo@example.com"
    demo_password = "demo123"

    existing_user = cur.execute(
        "SELECT * FROM users WHERE email = ?",
        (demo_email,)
    ).fetchone()

    if not existing_user:
        cur.execute(
            "INSERT INTO users (full_name, email, password) VALUES (?, ?, ?)",
            ("Demo User", demo_email, generate_password_hash(demo_password))
        )

    conn.commit()
    conn.close()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def get_today_str():
    return date.today().isoformat()


def get_due_badge(due_date_value):
    if not due_date_value:
        return ""

    today = get_today_str()

    if due_date_value < today:
        return "overdue"
    if due_date_value == today:
        return "due-today"
    return ""


@app.context_processor
def inject_globals():
    return {
        "theme": session.get("theme", "light"),
        "today_date": get_today_str()
    }


@app.route("/theme/<mode>")
def set_theme(mode):
    if mode in ["light", "dark"]:
        session["theme"] = mode
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not full_name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        conn = get_db_connection()
        existing = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            flash("Account already exists. Please login.", "error")
            return redirect(url_for("login"))

        conn.execute(
            "INSERT INTO users (full_name, email, password) VALUES (?, ?, ?)",
            (full_name, email, generate_password_hash(password))
        )
        conn.commit()
        conn.close()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"] if "full_name" in user.keys() else "User"
            if "theme" not in session:
                session["theme"] = "light"
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    theme = session.get("theme", "light")
    session.clear()
    session["theme"] = theme
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    source_filter = request.args.get("source", "").strip()

    conn = get_db_connection()

    query = "SELECT * FROM jobs WHERE user_id = ?"
    params = [session["user_id"]]

    if search:
        query += """ AND (
            company LIKE ? OR role LIKE ? OR location LIKE ? OR notes LIKE ? OR
            interview_notes LIKE ? OR jd_text LIKE ? OR rejection_reason LIKE ? OR job_source LIKE ?
        )"""
        keyword = f"%{search}%"
        params.extend([keyword, keyword, keyword, keyword, keyword, keyword, keyword, keyword])

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    if priority_filter:
        query += " AND priority = ?"
        params.append(priority_filter)

    if source_filter:
        query += " AND job_source = ?"
        params.append(source_filter)

    query += """
        ORDER BY
            CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END,
            due_date ASC,
            created_at DESC
    """

    jobs_raw = conn.execute(query, params).fetchall()

    jobs = []
    for row in jobs_raw:
        job = dict(row)
        job["due_badge"] = get_due_badge(job.get("due_date"))
        jobs.append(job)

    total_count = conn.execute(
        "SELECT COUNT(*) AS count FROM jobs WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()["count"]

    counts = {}
    for status in STATUS_OPTIONS:
        counts[status] = conn.execute(
            "SELECT COUNT(*) AS count FROM jobs WHERE user_id = ? AND status = ?",
            (session["user_id"], status)
        ).fetchone()["count"]

    upcoming_followups = conn.execute("""
        SELECT COUNT(*) AS count
        FROM jobs
        WHERE user_id = ?
          AND follow_up_date IS NOT NULL
          AND follow_up_date != ''
          AND follow_up_date >= ?
    """, (session["user_id"], get_today_str())).fetchone()["count"]

    overdue_deadlines = conn.execute("""
        SELECT COUNT(*) AS count
        FROM jobs
        WHERE user_id = ?
          AND due_date IS NOT NULL
          AND due_date != ''
          AND due_date < ?
    """, (session["user_id"], get_today_str())).fetchone()["count"]

    conn.close()

    return render_template(
        "dashboard.html",
        jobs=jobs,
        search=search,
        status_filter=status_filter,
        priority_filter=priority_filter,
        source_filter=source_filter,
        status_options=STATUS_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
        source_options=JOB_SOURCE_OPTIONS,
        work_mode_options=WORK_MODE_OPTIONS,
        total_count=total_count,
        counts=counts,
        upcoming_followups=upcoming_followups,
        overdue_deadlines=overdue_deadlines,
    )


@app.route("/job/add", methods=["GET", "POST"])
@login_required
def add_job():
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        role = request.form.get("role", "").strip()
        status = request.form.get("status", "Applied").strip()
        location = request.form.get("location", "").strip()
        applied_date = request.form.get("applied_date", "").strip()
        due_date = request.form.get("due_date", "").strip()
        follow_up_date = request.form.get("follow_up_date", "").strip()
        priority = request.form.get("priority", "").strip()
        job_source = request.form.get("job_source", "").strip()
        salary = request.form.get("salary", "").strip()
        work_mode = request.form.get("work_mode", "").strip()
        resume_version = request.form.get("resume_version", "").strip()
        interview_notes = request.form.get("interview_notes", "").strip()
        rejection_reason = request.form.get("rejection_reason", "").strip()
        jd_text = request.form.get("jd_text", "").strip()
        link = request.form.get("link", "").strip()
        notes = request.form.get("notes", "").strip()

        if not company or not role:
            flash("Company and role are required.", "error")
            return redirect(url_for("add_job"))

        if status not in STATUS_OPTIONS:
            status = "Applied"

        if priority and priority not in PRIORITY_OPTIONS:
            priority = ""

        if work_mode and work_mode not in WORK_MODE_OPTIONS:
            work_mode = ""

        resume_filename = None
        resume_file = request.files.get("resume")

        if resume_file and resume_file.filename:
            if not allowed_file(resume_file.filename):
                flash("Only PDF resumes are allowed.", "error")
                return redirect(url_for("add_job"))

            safe_name = secure_filename(resume_file.filename)
            unique_name = f"{uuid4().hex}_{safe_name}"
            resume_file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
            resume_filename = unique_name

        conn = get_db_connection()
        conn.execute("""
            INSERT INTO jobs (
                user_id, company, role, status, location,
                applied_date, due_date, follow_up_date, priority,
                job_source, salary, work_mode, resume_version,
                interview_notes, rejection_reason, jd_text,
                link, notes, resume_filename
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            company,
            role,
            status,
            location,
            applied_date if applied_date else None,
            due_date if due_date else None,
            follow_up_date if follow_up_date else None,
            priority if priority else None,
            job_source if job_source else None,
            salary if salary else None,
            work_mode if work_mode else None,
            resume_version if resume_version else None,
            interview_notes if interview_notes else None,
            rejection_reason if rejection_reason else None,
            jd_text if jd_text else None,
            link if link else None,
            notes if notes else None,
            resume_filename,
        ))
        conn.commit()
        conn.close()

        flash("Job added successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template(
        "job_form.html",
        job=None,
        status_options=STATUS_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
        source_options=JOB_SOURCE_OPTIONS,
        work_mode_options=WORK_MODE_OPTIONS,
    )


@app.route("/job/edit/<int:job_id>", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    conn = get_db_connection()
    job = conn.execute(
        "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
        (job_id, session["user_id"])
    ).fetchone()

    if not job:
        conn.close()
        flash("Job not found.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        company = request.form.get("company", "").strip()
        role = request.form.get("role", "").strip()
        status = request.form.get("status", "Applied").strip()
        location = request.form.get("location", "").strip()
        applied_date = request.form.get("applied_date", "").strip()
        due_date = request.form.get("due_date", "").strip()
        follow_up_date = request.form.get("follow_up_date", "").strip()
        priority = request.form.get("priority", "").strip()
        job_source = request.form.get("job_source", "").strip()
        salary = request.form.get("salary", "").strip()
        work_mode = request.form.get("work_mode", "").strip()
        resume_version = request.form.get("resume_version", "").strip()
        interview_notes = request.form.get("interview_notes", "").strip()
        rejection_reason = request.form.get("rejection_reason", "").strip()
        jd_text = request.form.get("jd_text", "").strip()
        link = request.form.get("link", "").strip()
        notes = request.form.get("notes", "").strip()
        remove_resume = request.form.get("remove_resume")

        if not company or not role:
            conn.close()
            flash("Company and role are required.", "error")
            return redirect(url_for("edit_job", job_id=job_id))

        if status not in STATUS_OPTIONS:
            status = "Applied"

        if priority and priority not in PRIORITY_OPTIONS:
            priority = ""

        if work_mode and work_mode not in WORK_MODE_OPTIONS:
            work_mode = ""

        resume_filename = job["resume_filename"]

        if remove_resume == "yes" and resume_filename:
            old_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            resume_filename = None

        resume_file = request.files.get("resume")
        if resume_file and resume_file.filename:
            if not allowed_file(resume_file.filename):
                conn.close()
                flash("Only PDF resumes are allowed.", "error")
                return redirect(url_for("edit_job", job_id=job_id))

            if resume_filename:
                old_path = os.path.join(app.config["UPLOAD_FOLDER"], resume_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)

            safe_name = secure_filename(resume_file.filename)
            unique_name = f"{uuid4().hex}_{safe_name}"
            resume_file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
            resume_filename = unique_name

        conn.execute("""
            UPDATE jobs
            SET company = ?, role = ?, status = ?, location = ?,
                applied_date = ?, due_date = ?, follow_up_date = ?, priority = ?,
                job_source = ?, salary = ?, work_mode = ?, resume_version = ?,
                interview_notes = ?, rejection_reason = ?, jd_text = ?,
                link = ?, notes = ?, resume_filename = ?
            WHERE id = ? AND user_id = ?
        """, (
            company,
            role,
            status,
            location,
            applied_date if applied_date else None,
            due_date if due_date else None,
            follow_up_date if follow_up_date else None,
            priority if priority else None,
            job_source if job_source else None,
            salary if salary else None,
            work_mode if work_mode else None,
            resume_version if resume_version else None,
            interview_notes if interview_notes else None,
            rejection_reason if rejection_reason else None,
            jd_text if jd_text else None,
            link if link else None,
            notes if notes else None,
            resume_filename,
            job_id,
            session["user_id"],
        ))
        conn.commit()
        conn.close()

        flash("Job updated successfully.", "success")
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template(
        "job_form.html",
        job=job,
        status_options=STATUS_OPTIONS,
        priority_options=PRIORITY_OPTIONS,
        source_options=JOB_SOURCE_OPTIONS,
        work_mode_options=WORK_MODE_OPTIONS,
    )


@app.route("/job/delete/<int:job_id>", methods=["POST"])
@login_required
def delete_job(job_id):
    conn = get_db_connection()
    job = conn.execute(
        "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
        (job_id, session["user_id"])
    ).fetchone()

    if not job:
        conn.close()
        flash("Job not found.", "error")
        return redirect(url_for("dashboard"))

    if job["resume_filename"]:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], job["resume_filename"])
        if os.path.exists(file_path):
            os.remove(file_path)

    conn.execute(
        "DELETE FROM jobs WHERE id = ? AND user_id = ?",
        (job_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    flash("Job deleted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/resume/<filename>")
@login_required
def preview_resume(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/export/csv")
@login_required
def export_csv():
    conn = get_db_connection()
    jobs = conn.execute(
        "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "Company", "Role", "Status", "Location", "Applied Date", "Due Date",
        "Follow Up Date", "Priority", "Job Source", "Salary", "Work Mode",
        "Resume Version", "Interview Notes", "Rejection Reason",
        "JD Snapshot", "Link", "Notes", "Resume File", "Created At"
    ]
    writer.writerow(headers)

    for job in jobs:
        writer.writerow([
            job["company"],
            job["role"],
            job["status"],
            job["location"],
            job["applied_date"],
            job["due_date"],
            job["follow_up_date"],
            job["priority"],
            job["job_source"],
            job["salary"],
            job["work_mode"],
            job["resume_version"],
            job["interview_notes"],
            job["rejection_reason"],
            job["jd_text"],
            job["link"],
            job["notes"],
            job["resume_filename"],
            job["created_at"],
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=job_applications.csv"
    response.headers["Content-type"] = "text/csv"
    return response


if __name__ == "__main__":
    init_db()
    app.run(debug=True)