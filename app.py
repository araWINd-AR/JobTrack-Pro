import csv
import io
import os
from datetime import date
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from dotenv import load_dotenv
from supabase import Client, create_client
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")

ALLOWED_EXTENSIONS = {"pdf"}

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

SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "resumes")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def validate_supabase_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise RuntimeError(
            "SUPABASE_URL is invalid. It must look like: https://your-project-ref.supabase.co"
        )
    return url


def get_supabase() -> Client:
    url = validate_supabase_url(require_env("SUPABASE_URL"))
    key = require_env("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(url, key)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def to_date_value(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:10]
    return str(value)[:10]


def sort_key(job: dict):
    due = job.get("due_date") or ""
    created = job.get("created_at") or ""
    return (1 if not due else 0, due or "9999-12-31", created)


def one_or_none(rows):
    return rows[0] if rows else None


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


def init_db():
    supabase = get_supabase()
    existing = (
        supabase.table("app_users")
        .select("id")
        .eq("email", "demo@example.com")
        .limit(1)
        .execute()
        .data
        or []
    )

    if not existing:
        supabase.table("app_users").insert(
            {
                "full_name": "Demo User",
                "email": "demo@example.com",
                "password_hash": generate_password_hash("demo123"),
            }
        ).execute()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_globals():
    return {
        "theme": session.get("theme", "light"),
        "today_date": get_today_str(),
    }


@app.route("/health")
def health():
    try:
        supabase = get_supabase()
        supabase.table("app_users").select("id").limit(1).execute()
        return {"status": "ok", "storage": "supabase"}, 200
    except Exception as exc:
        return {"status": "error", "storage": "supabase", "message": str(exc)}, 500


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

        supabase = get_supabase()
        existing = (
            supabase.table("app_users")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
            .data
            or []
        )

        if existing:
            flash("Account already exists. Please login.", "error")
            return redirect(url_for("login"))

        supabase.table("app_users").insert(
            {
                "full_name": full_name,
                "email": email,
                "password_hash": generate_password_hash(password),
            }
        ).execute()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        supabase = get_supabase()
        rows = (
            supabase.table("app_users")
            .select("*")
            .eq("email", email)
            .limit(1)
            .execute()
            .data
            or []
        )
        user = one_or_none(rows)

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user.get("full_name") or "User"
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


def fetch_user_jobs(user_id: int):
    supabase = get_supabase()
    rows = supabase.table("jobs").select("*").eq("user_id", user_id).execute().data or []

    for job in rows:
        for key in ["applied_date", "due_date", "follow_up_date", "created_at"]:
            if key in job and job[key] is not None:
                job[key] = str(job[key])
        job["due_badge"] = get_due_badge(to_date_value(job.get("due_date")))

    rows.sort(key=sort_key)
    return rows


@app.route("/dashboard")
@login_required
def dashboard():
    search = request.args.get("search", "").strip().lower()
    status_filter = request.args.get("status", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    source_filter = request.args.get("source", "").strip()

    jobs = fetch_user_jobs(session["user_id"])

    filtered = []
    for job in jobs:
        haystack = " ".join(
            [
                str(job.get("company") or ""),
                str(job.get("role") or ""),
                str(job.get("location") or ""),
                str(job.get("notes") or ""),
                str(job.get("interview_notes") or ""),
                str(job.get("jd_text") or ""),
                str(job.get("rejection_reason") or ""),
                str(job.get("job_source") or ""),
            ]
        ).lower()

        if search and search not in haystack:
            continue
        if status_filter and job.get("status") != status_filter:
            continue
        if priority_filter and job.get("priority") != priority_filter:
            continue
        if source_filter and job.get("job_source") != source_filter:
            continue
        filtered.append(job)

    total_count = len(jobs)
    counts = {
        status: sum(1 for job in jobs if job.get("status") == status)
        for status in STATUS_OPTIONS
    }
    upcoming_followups = sum(
        1
        for job in jobs
        if (job.get("follow_up_date") or "")[:10] >= get_today_str()
        and job.get("follow_up_date")
    )
    overdue_deadlines = sum(
        1
        for job in jobs
        if (job.get("due_date") or "")[:10] < get_today_str()
        and job.get("due_date")
    )

    return render_template(
        "dashboard.html",
        jobs=filtered,
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


def upload_resume(file_storage, user_id: int):
    if not file_storage or not file_storage.filename:
        return None

    safe_name = secure_filename(file_storage.filename)
    if not safe_name:
        return None

    if not allowed_file(safe_name):
        raise ValueError("Only PDF resumes are allowed.")

    unique_name = f"{uuid4().hex}_{safe_name}"
    storage_path = f"user_{user_id}/{unique_name}"

    file_storage.seek(0)
    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    supabase = get_supabase()
    supabase.storage.from_(SUPABASE_BUCKET).upload(
        path=storage_path,
        file=file_bytes,
        file_options={
            "content-type": file_storage.mimetype or "application/pdf",
            "upsert": "false",
        },
    )

    return storage_path


def delete_resume(storage_path):
    if not storage_path:
        return
    supabase = get_supabase()
    supabase.storage.from_(SUPABASE_BUCKET).remove([storage_path])


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

        resume_path = None
        resume_file = request.files.get("resume")
        try:
            if resume_file and resume_file.filename:
                resume_path = upload_resume(resume_file, session["user_id"])
        except Exception as exc:
            flash(f"Resume upload failed: {exc}", "error")
            return redirect(url_for("add_job"))

        get_supabase().table("jobs").insert(
            {
                "user_id": session["user_id"],
                "company": company,
                "role": role,
                "status": status,
                "location": location or None,
                "applied_date": applied_date or None,
                "due_date": due_date or None,
                "follow_up_date": follow_up_date or None,
                "priority": priority or None,
                "job_source": job_source or None,
                "salary": salary or None,
                "work_mode": work_mode or None,
                "resume_version": resume_version or None,
                "interview_notes": interview_notes or None,
                "rejection_reason": rejection_reason or None,
                "jd_text": jd_text or None,
                "link": link or None,
                "notes": notes or None,
                "resume_filename": resume_path,
            }
        ).execute()

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
    supabase = get_supabase()
    rows = (
        supabase.table("jobs")
        .select("*")
        .eq("id", job_id)
        .eq("user_id", session["user_id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    job = one_or_none(rows)

    if not job:
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
            flash("Company and role are required.", "error")
            return redirect(url_for("edit_job", job_id=job_id))

        if status not in STATUS_OPTIONS:
            status = "Applied"
        if priority and priority not in PRIORITY_OPTIONS:
            priority = ""
        if work_mode and work_mode not in WORK_MODE_OPTIONS:
            work_mode = ""

        resume_path = job.get("resume_filename")

        try:
            if remove_resume == "yes" and resume_path:
                delete_resume(resume_path)
                resume_path = None

            resume_file = request.files.get("resume")
            if resume_file and resume_file.filename:
                if resume_path:
                    delete_resume(resume_path)
                resume_path = upload_resume(resume_file, session["user_id"])
        except Exception as exc:
            flash(f"Resume update failed: {exc}", "error")
            return redirect(url_for("edit_job", job_id=job_id))

        supabase.table("jobs").update(
            {
                "company": company,
                "role": role,
                "status": status,
                "location": location or None,
                "applied_date": applied_date or None,
                "due_date": due_date or None,
                "follow_up_date": follow_up_date or None,
                "priority": priority or None,
                "job_source": job_source or None,
                "salary": salary or None,
                "work_mode": work_mode or None,
                "resume_version": resume_version or None,
                "interview_notes": interview_notes or None,
                "rejection_reason": rejection_reason or None,
                "jd_text": jd_text or None,
                "link": link or None,
                "notes": notes or None,
                "resume_filename": resume_path,
            }
        ).eq("id", job_id).eq("user_id", session["user_id"]).execute()

        flash("Job updated successfully.", "success")
        return redirect(url_for("dashboard"))

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
    supabase = get_supabase()
    rows = (
        supabase.table("jobs")
        .select("resume_filename")
        .eq("id", job_id)
        .eq("user_id", session["user_id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    job = one_or_none(rows)

    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("dashboard"))

    if job.get("resume_filename"):
        delete_resume(job["resume_filename"])

    supabase.table("jobs").delete().eq("id", job_id).eq("user_id", session["user_id"]).execute()
    flash("Job deleted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/resume/<path:storage_path>")
@login_required
def preview_resume(storage_path):
    expected_prefix = f"user_{session['user_id']}/"
    if not storage_path.startswith(expected_prefix):
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))

    data = get_supabase().storage.from_(SUPABASE_BUCKET).download(storage_path)
    filename = os.path.basename(storage_path)

    return send_file(
        io.BytesIO(data),
        mimetype="application/pdf",
        download_name=filename,
        as_attachment=False,
    )


@app.route("/export/csv")
@login_required
def export_csv():
    jobs = fetch_user_jobs(session["user_id"])

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "Company",
        "Role",
        "Status",
        "Location",
        "Applied Date",
        "Due Date",
        "Follow Up Date",
        "Priority",
        "Job Source",
        "Salary",
        "Work Mode",
        "Resume Version",
        "Interview Notes",
        "Rejection Reason",
        "JD Snapshot",
        "Link",
        "Notes",
        "Resume File",
        "Created At",
    ]
    writer.writerow(headers)

    for job in jobs:
        writer.writerow(
            [
                job.get("company"),
                job.get("role"),
                job.get("status"),
                job.get("location"),
                job.get("applied_date"),
                job.get("due_date"),
                job.get("follow_up_date"),
                job.get("priority"),
                job.get("job_source"),
                job.get("salary"),
                job.get("work_mode"),
                job.get("resume_version"),
                job.get("interview_notes"),
                job.get("rejection_reason"),
                job.get("jd_text"),
                job.get("link"),
                job.get("notes"),
                job.get("resume_filename"),
                job.get("created_at"),
            ]
        )

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=job_applications.csv"
    response.headers["Content-type"] = "text/csv"
    return response



init_db()

if __name__ == "__main__":
    app.run(debug=True)