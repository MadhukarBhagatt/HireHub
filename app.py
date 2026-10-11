import os
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import re

load_dotenv()

app = Flask(__name__)

# =========================================================
# SECRET KEY
# =========================================================

app.secret_key = "hirehub_secret_key"

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# =========================================================
# MYSQL CONNECTION
# =========================================================

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "hirehub")
    )

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        email_pattern = (
            r"^[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+"
            r"\.[A-Za-z]{2,}$"
        )

        if not re.match(email_pattern, email):
            flash(
                "Please enter a valid email address.",
                "danger"
            )
            return redirect(url_for("register"))

        if role not in ["client", "freelancer"]:
            flash(
                "Please select a valid role.",
                "danger"
            )
            return redirect(url_for("register"))

        if len(password) < 8:
            flash(
                "Password must be at least 8 characters long.",
                "danger"
            )
            return redirect(url_for("register"))

        if not re.search(r"[A-Z]", password):
            flash(
                "Password must contain at least one uppercase letter.",
                "danger"
            )
            return redirect(url_for("register"))

        if not re.search(r"[a-z]", password):
            flash(
                "Password must contain at least one lowercase letter.",
                "danger"
            )
            return redirect(url_for("register"))

        if not re.search(r"\d", password):
            flash(
                "Password must contain at least one number.",
                "danger"
            )
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        db = get_db_connection()
        cursor = db.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users
                (name, email, password, role)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    name,
                    email,
                    hashed_password,
                    role
                )
            )

            db.commit()

            flash(
                "Registration successful! Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except mysql.connector.Error as e:

            db.rollback()

            flash(
                f"Registration error: {e}",
                "danger"
            )

        finally:

            cursor.close()
            db.close()

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password,
                    role
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["email"] = user["email"]
                session["role"] = user["role"]

                flash(
                    "Login successful!",
                    "success"
                )

                return redirect(url_for("dashboard"))

            flash(
                "Invalid email or password.",
                "danger"
            )

        except mysql.connector.Error as e:

            flash(
                f"Login error: {e}",
                "danger"
            )

        finally:

            cursor.close()
            db.close()

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("home"))


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        # =================================================
        # ADMIN DASHBOARD
        # =================================================

        if session.get("role") == "admin":

            cursor.execute(
                """
                SELECT COUNT(*) AS total_users
                FROM users
                """
            )

            total_users = cursor.fetchone()["total_users"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total_clients
                FROM users
                WHERE role = 'client'
                """
            )

            total_clients = cursor.fetchone()["total_clients"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total_freelancers
                FROM users
                WHERE role = 'freelancer'
                """
            )

            total_freelancers = cursor.fetchone()["total_freelancers"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total_jobs
                FROM jobs
                """
            )

            total_jobs = cursor.fetchone()["total_jobs"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total_applications
                FROM applications
                """
            )

            total_applications = cursor.fetchone()["total_applications"]

            cursor.execute(
                """
                SELECT
                    role,
                    COUNT(*) AS total
                FROM users
                GROUP BY role
                ORDER BY role
                """
            )

            user_role_data = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    status,
                    COUNT(*) AS total
                FROM jobs
                GROUP BY status
                ORDER BY status
                """
            )

            job_status_data = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    status,
                    COUNT(*) AS total
                FROM applications
                GROUP BY status
                ORDER BY status
                """
            )

            application_status_data = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    category,
                    COUNT(*) AS total
                FROM jobs
                WHERE category IS NOT NULL
                AND TRIM(category) <> ''
                GROUP BY category
                ORDER BY total DESC
                """
            )

            job_category_data = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    users.id,
                    users.name,
                    users.email,

                    ROUND(
                        AVG(reviews.rating),
                        1
                    ) AS average_rating,

                    COUNT(reviews.id) AS total_reviews

                FROM users

                INNER JOIN reviews
                    ON users.id = reviews.freelancer_id

                WHERE users.role = 'freelancer'

                GROUP BY
                    users.id,
                    users.name,
                    users.email

                ORDER BY
                    average_rating DESC,
                    total_reviews DESC

                LIMIT 5
                """
            )

            top_rated_freelancers = cursor.fetchall()

            for freelancer in top_rated_freelancers:

                if freelancer["average_rating"] is not None:

                    freelancer["average_rating"] = float(
                        freelancer["average_rating"]
                    )

            return render_template(
                "admin_dashboard.html",

                total_users=total_users,
                total_clients=total_clients,
                total_freelancers=total_freelancers,
                total_jobs=total_jobs,
                total_applications=total_applications,

                user_role_data=user_role_data,
                job_status_data=job_status_data,
                application_status_data=application_status_data,
                job_category_data=job_category_data,

                top_freelancers=top_rated_freelancers
            )

        # =================================================
        # CLIENT DASHBOARD
        # =================================================

        if session.get("role") == "client":

            cursor.execute(
                """
                SELECT COUNT(*) AS total_jobs
                FROM jobs
                WHERE client_id = %s
                """,
                (session["user_id"],)
            )

            total_jobs = cursor.fetchone()["total_jobs"]

            cursor.execute(
                """
                SELECT COUNT(*) AS open_jobs
                FROM jobs
                WHERE client_id = %s
                AND status = 'Open'
                """,
                (session["user_id"],)
            )

            open_jobs = cursor.fetchone()["open_jobs"]

            cursor.execute(
                """
                SELECT COUNT(*) AS closed_jobs
                FROM jobs
                WHERE client_id = %s
                AND status = 'Closed'
                """,
                (session["user_id"],)
            )

            closed_jobs = cursor.fetchone()["closed_jobs"]

            cursor.execute(
                """
                SELECT COUNT(*) AS total_applications
                FROM applications

                INNER JOIN jobs
                    ON applications.job_id = jobs.id

                WHERE jobs.client_id = %s
                """,
                (session["user_id"],)
            )

            total_applications = cursor.fetchone()[
                "total_applications"
            ]

        # =================================================
        # FREELANCER DASHBOARD
        # =================================================

        elif session.get("role") == "freelancer":

            cursor.execute(
                """
                SELECT COUNT(*) AS total_applications
                FROM applications
                WHERE freelancer_id = %s
                """,
                (session["user_id"],)
            )

            total_applications = cursor.fetchone()[
                "total_applications"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS pending_applications
                FROM applications
                WHERE freelancer_id = %s
                AND status = 'Pending'
                """,
                (session["user_id"],)
            )

            pending_applications = cursor.fetchone()[
                "pending_applications"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS accepted_applications
                FROM applications
                WHERE freelancer_id = %s
                AND status = 'Accepted'
                """,
                (session["user_id"],)
            )

            accepted_applications = cursor.fetchone()[
                "accepted_applications"
            ]

            cursor.execute(
                """
                SELECT COUNT(*) AS rejected_applications
                FROM applications
                WHERE freelancer_id = %s
                AND status = 'Rejected'
                """,
                (session["user_id"],)
            )

            rejected_applications = cursor.fetchone()[
                "rejected_applications"
            ]

        # =================================================
        # RECENT JOBS
        # =================================================

        cursor.execute(
            """
            SELECT
                jobs.*,
                users.name AS client_name

            FROM jobs

            LEFT JOIN users
                ON jobs.client_id = users.id

            ORDER BY jobs.id DESC
            """
        )

        jobs = cursor.fetchall()

    except mysql.connector.Error as e:

        flash(
            f"Dashboard error: {e}",
            "danger"
        )

        jobs = []

    finally:

        cursor.close()
        db.close()

    # =================================================
    # CLIENT DASHBOARD
    # =================================================

    if session.get("role") == "client":

        return render_template(
            "dashboard.html",

            jobs=jobs,

            total_jobs=total_jobs,
            open_jobs=open_jobs,
            closed_jobs=closed_jobs,
            total_applications=total_applications
        )

    # =================================================
    # FREELANCER DASHBOARD
    # =================================================

    return render_template(
        "dashboard.html",

        jobs=jobs,

        total_applications=total_applications,
        pending_applications=pending_applications,
        accepted_applications=accepted_applications,
        rejected_applications=rejected_applications
    )


# =========================================================
# FIND FREELANCERS
# =========================================================

@app.route("/find-freelancer")
def find_freelancer():

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:

        if search:

            query = """
                SELECT
                    u.id,
                    u.name,
                    u.email,
                    fp.skills,

                    COALESCE(
                        AVG(r.rating),
                        0
                    ) AS average_rating,

                    COUNT(r.id) AS total_reviews

                FROM users u

                LEFT JOIN freelancer_profiles fp
                    ON u.id = fp.user_id

                LEFT JOIN reviews r
                    ON u.id = r.freelancer_id

                WHERE u.role = 'freelancer'

                AND (
                    u.name LIKE %s
                    OR fp.skills LIKE %s
                )

                GROUP BY
                    u.id,
                    u.name,
                    u.email,
                    fp.skills

                ORDER BY average_rating DESC
            """

            search_value = "%" + search + "%"

            cursor.execute(
                query,
                (
                    search_value,
                    search_value
                )
            )

        else:

            query = """
                SELECT
                    u.id,
                    u.name,
                    u.email,
                    fp.skills,

                    COALESCE(
                        AVG(r.rating),
                        0
                    ) AS average_rating,

                    COUNT(r.id) AS total_reviews

                FROM users u

                LEFT JOIN freelancer_profiles fp
                    ON u.id = fp.user_id

                LEFT JOIN reviews r
                    ON u.id = r.freelancer_id

                WHERE u.role = 'freelancer'

                GROUP BY
                    u.id,
                    u.name,
                    u.email,
                    fp.skills

                ORDER BY average_rating DESC
            """

            cursor.execute(query)

        freelancers = cursor.fetchall()

    finally:

        cursor.close()
        conn.close()

    return render_template(
        "freelancers.html",
        freelancers=freelancers,
        search=search
    )


# =========================================================
# POST JOB
# =========================================================

@app.route("/post-job", methods=["GET", "POST"])
def post_job():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can post jobs.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        skills = request.form.get(
            "skills",
            ""
        ).strip()

        budget = request.form.get(
            "budget",
            ""
        ).strip()

        deadline = request.form.get(
            "deadline",
            ""
        ).strip()

        db = get_db_connection()
        cursor = db.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO jobs
                (
                    client_id,
                    title,
                    category,
                    description,
                    skills,
                    budget,
                    deadline,
                    status
                )

                VALUES
                (%s, %s, %s, %s, %s, %s, %s, 'Open')
                """,
                (
                    session["user_id"],
                    title,
                    category,
                    description,
                    skills,
                    budget,
                    deadline
                )
            )

            db.commit()

            flash(
                "Job posted successfully!",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except mysql.connector.Error as e:

            db.rollback()

            flash(
                f"Error posting job: {e}",
                "danger"
            )

        finally:

            cursor.close()
            db.close()

    return render_template(
        "post_job.html"
    )


# =========================================================
# MY JOBS
# =========================================================

@app.route("/my-jobs")
def my_jobs():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can view their jobs.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE client_id = %s
            ORDER BY id DESC
            """,
            (session["user_id"],)
        )

        jobs = cursor.fetchall()

    finally:

        cursor.close()
        db.close()

    return render_template(
        "my_jobs.html",
        jobs=jobs
    )


# =========================================================
# EDIT JOB
# =========================================================

@app.route(
    "/edit-job/<int:job_id>",
    methods=["GET", "POST"]
)
def edit_job(job_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can edit jobs.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = %s
            """,
            (job_id,)
        )

        job = cursor.fetchone()

        if not job:

            flash(
                "Job not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        if job["client_id"] != session["user_id"]:

            flash(
                "You can only edit your own jobs.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        if request.method == "POST":

            title = request.form.get(
                "title",
                ""
            ).strip()

            category = request.form.get(
                "category",
                ""
            ).strip()

            description = request.form.get(
                "description",
                ""
            ).strip()

            skills = request.form.get(
                "skills",
                ""
            ).strip()

            budget = request.form.get(
                "budget",
                ""
            ).strip()

            deadline = request.form.get(
                "deadline",
                ""
            ).strip()

            cursor.execute(
                """
                UPDATE jobs

                SET
                    title = %s,
                    category = %s,
                    description = %s,
                    skills = %s,
                    budget = %s,
                    deadline = %s

                WHERE id = %s
                """,
                (
                    title,
                    category,
                    description,
                    skills,
                    budget,
                    deadline,
                    job_id
                )
            )

            db.commit()

            flash(
                "Job updated successfully!",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error updating job: {e}",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "edit_job.html",
        job=job
    )


# =========================================================
# DELETE JOB
# =========================================================

@app.route(
    "/delete-job/<int:job_id>",
    methods=["POST"]
)
def delete_job(job_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can delete jobs.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                client_id
            FROM jobs
            WHERE id = %s
            """,
            (job_id,)
        )

        job = cursor.fetchone()

        if not job:

            flash(
                "Job not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        if job["client_id"] != session["user_id"]:

            flash(
                "You can only delete your own jobs.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        cursor.execute(
            """
            DELETE FROM applications
            WHERE job_id = %s
            """,
            (job_id,)
        )

        cursor.execute(
            """
            DELETE FROM reviews
            WHERE job_id = %s
            """,
            (job_id,)
        )

        cursor.execute(
            """
            DELETE FROM jobs
            WHERE id = %s
            """,
            (job_id,)
        )

        db.commit()

        flash(
            "Job deleted successfully!",
            "success"
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error deleting job: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return redirect(
        url_for("dashboard")
    )


# =========================================================
# VIEW ALL JOBS
# =========================================================

@app.route("/jobs")
def jobs():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    search = request.args.get(
        "search",
        ""
    ).strip()

    skill = request.args.get(
        "skill",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        query = """
            SELECT
                jobs.id,
                jobs.client_id,
                jobs.title,
                jobs.category,
                jobs.description,
                jobs.skills,
                jobs.budget,
                jobs.deadline,
                jobs.status,

                users.name AS client_name

            FROM jobs

            JOIN users
                ON jobs.client_id = users.id

            WHERE 1 = 1
        """

        values = []

        if search:

            query += """
                AND jobs.title LIKE %s
            """

            values.append(
                f"%{search}%"
            )

        if skill:

            query += """
                AND jobs.skills LIKE %s
            """

            values.append(
                f"%{skill}%"
            )

        if category:

            query += """
                AND jobs.category = %s
            """

            values.append(category)

        if status:

            query += """
                AND jobs.status = %s
            """

            values.append(status)

        query += """
            ORDER BY jobs.id DESC
        """

        cursor.execute(
            query,
            values
        )

        job_list = cursor.fetchall()

    finally:

        cursor.close()
        db.close()

    return render_template(
        "jobs.html",
        jobs=job_list,
        search=search,
        skill=skill,
        category=category,
        status=status
    )


# =========================================================
# APPLY FOR JOB
# =========================================================

@app.route(
    "/apply/<int:job_id>",
    methods=["POST"]
)
def apply_job(job_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "freelancer":

        flash(
            "Only freelancers can apply for jobs.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    # =====================================================
    # GET COVER LETTER
    # =====================================================

    cover_letter = request.form.get(
        "cover_letter",
        ""
    ).strip()


    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # CHECK JOB
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                status
            FROM jobs
            WHERE id = %s
            """,
            (job_id,)
        )

        job = cursor.fetchone()

        if not job:

            flash(
                "Job not found.",
                "danger"
            )

            return redirect(
                url_for("jobs")
            )

        if job["status"] == "Closed":

            flash(
                "This job is closed and no longer accepts applications.",
                "danger"
            )

            return redirect(
                url_for("jobs")
            )

        # -------------------------------------------------
        # CHECK EXISTING APPLICATION
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM applications
            WHERE job_id = %s
            AND freelancer_id = %s
            """,
            (
                job_id,
                session["user_id"]
            )
        )

        existing_application = cursor.fetchone()

        if existing_application:

            flash(
                "You have already applied for this job.",
                "warning"
            )

            return redirect(
                url_for("jobs")
            )

        # -------------------------------------------------
        # INSERT APPLICATION
        # -------------------------------------------------

        cursor.execute(
            """
            INSERT INTO applications
            (
                job_id,
                freelancer_id,
                cover_letter,
                status
            )

            VALUES
            (%s, %s, %s, 'Pending')
            """,
            (
                job_id,
                session["user_id"],
                cover_letter
            )
        )

        db.commit()

        flash(
            "Application submitted successfully!",
            "success"
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error applying for job: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return redirect(
        url_for("jobs")
    )


# =========================================================
# MY APPLICATIONS
# =========================================================

@app.route("/my-applications")
def my_applications():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    applications = []

    try:

        # =================================================
        # CLIENT APPLICATIONS
        # =================================================

        if session.get("role") == "client":

            cursor.execute(
                """
                SELECT
                    applications.id AS application_id,
                    applications.job_id,
                    applications.freelancer_id,
                    applications.cover_letter,
                    applications.status,
                    applications.applied_at,

                    jobs.title AS job_title,

                    users.name AS freelancer_name,
                    users.email AS freelancer_email

                FROM applications

                JOIN jobs
                    ON applications.job_id = jobs.id

                JOIN users
                    ON applications.freelancer_id = users.id

                WHERE jobs.client_id = %s

                ORDER BY applications.id DESC
                """,
                (session["user_id"],)
            )

            applications = cursor.fetchall()

        # =================================================
        # FREELANCER APPLICATIONS
        # =================================================

        elif session.get("role") == "freelancer":

            cursor.execute(
                """
                SELECT
                    applications.id AS application_id,
                    applications.job_id,
                    applications.freelancer_id,
                    applications.cover_letter,
                    applications.status,
                    applications.applied_at,

                    jobs.title AS job_title,

                    users.name AS client_name,
                    users.email AS client_email

                FROM applications

                JOIN jobs
                    ON applications.job_id = jobs.id

                JOIN users
                    ON jobs.client_id = users.id

                WHERE applications.freelancer_id = %s

                ORDER BY applications.id DESC
                """,
                (session["user_id"],)
            )

            applications = cursor.fetchall()

    except mysql.connector.Error as e:

        flash(
            f"Error loading applications: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "applications.html",
        applications=applications
    )

# =========================================================
# ACCEPT APPLICATION
# =========================================================

@app.route(
    "/accept-application/<int:application_id>",
    methods=["POST"]
)
def accept_application(application_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can accept applications.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                applications.id,
                applications.job_id,
                applications.status,
                jobs.client_id

            FROM applications

            JOIN jobs
                ON applications.job_id = jobs.id

            WHERE applications.id = %s
            AND jobs.client_id = %s
            """,
            (
                application_id,
                session["user_id"]
            )
        )

        application = cursor.fetchone()

        if not application:

            flash(
                "Application not found or access denied.",
                "danger"
            )

            return redirect(
                url_for("my_applications")
            )

        if application["status"] != "Pending":

            flash(
                "This application has already been processed.",
                "warning"
            )

            return redirect(
                url_for("my_applications")
            )

        job_id = application["job_id"]

        # -------------------------------------------------
        # ACCEPT SELECTED APPLICATION
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE applications
            SET status = 'Accepted'
            WHERE id = %s
            """,
            (application_id,)
        )

        # -------------------------------------------------
        # REJECT OTHER PENDING APPLICATIONS
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE applications
            SET status = 'Rejected'

            WHERE job_id = %s
            AND id != %s
            AND status = 'Pending'
            """,
            (
                job_id,
                application_id
            )
        )

        # -------------------------------------------------
        # CLOSE JOB
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE jobs
            SET status = 'Closed'
            WHERE id = %s
            """,
            (job_id,)
        )

        db.commit()

        flash(
            "Freelancer accepted! Job is now closed.",
            "success"
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error accepting application: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return redirect(
        url_for("my_applications")
    )


# =========================================================
# REJECT APPLICATION
# =========================================================

@app.route(
    "/reject-application/<int:application_id>",
    methods=["POST"]
)
def reject_application(application_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can reject applications.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                applications.id

            FROM applications

            JOIN jobs
                ON applications.job_id = jobs.id

            WHERE applications.id = %s
            AND jobs.client_id = %s
            """,
            (
                application_id,
                session["user_id"]
            )
        )

        application = cursor.fetchone()

        if not application:

            flash(
                "Application not found or access denied.",
                "danger"
            )

            return redirect(
                url_for("my_applications")
            )

        cursor.execute(
            """
            UPDATE applications

            SET status = 'Rejected'

            WHERE id = %s
            """,
            (application_id,)
        )

        db.commit()

        flash(
            "Application rejected successfully!",
            "success"
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error rejecting application: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return redirect(
        url_for("my_applications")
    )


# =========================================================
# FREELANCER PROFILE
# =========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def freelancer_profile():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "freelancer":

        flash(
            "Only freelancers can manage this profile.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    profile = None

    try:

        cursor.execute(
            """
            SELECT *
            FROM freelancer_profiles
            WHERE user_id = %s
            """,
            (session["user_id"],)
        )

        profile = cursor.fetchone()

        if request.method == "POST":

            bio = request.form.get(
                "bio",
                ""
            ).strip()

            skills = request.form.get(
                "skills",
                ""
            ).strip()

            experience = request.form.get(
                "experience",
                ""
            ).strip()

            if profile:

                cursor.execute(
                    """
                    UPDATE freelancer_profiles

                    SET
                        bio = %s,
                        skills = %s,
                        experience = %s

                    WHERE user_id = %s
                    """,
                    (
                        bio,
                        skills,
                        experience,
                        session["user_id"]
                    )
                )

                flash(
                    "Profile updated successfully!",
                    "success"
                )

            else:

                cursor.execute(
                    """
                    INSERT INTO freelancer_profiles
                    (
                        user_id,
                        bio,
                        skills,
                        experience
                    )

                    VALUES
                    (%s, %s, %s, %s)
                    """,
                    (
                        session["user_id"],
                        bio,
                        skills,
                        experience
                    )
                )

                flash(
                    "Profile created successfully!",
                    "success"
                )

            db.commit()

            return redirect(
                url_for("freelancer_profile")
            )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Profile error: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "freelancer_profile.html",
        profile=profile
    )


# =========================================================
# VIEW FREELANCER PROFILE
# =========================================================

@app.route("/freelancer/<int:user_id>")
def view_freelancer(user_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    freelancer = None
    reviews = []

    try:

        cursor.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,

                freelancer_profiles.bio,
                freelancer_profiles.skills,
                freelancer_profiles.experience,

                COALESCE(
                    ROUND(AVG(reviews.rating), 1),
                    0
                ) AS average_rating,

                COUNT(reviews.id) AS total_reviews

            FROM users

            LEFT JOIN freelancer_profiles
                ON users.id = freelancer_profiles.user_id

            LEFT JOIN reviews
                ON users.id = reviews.freelancer_id

            WHERE users.id = %s
            AND users.role = 'freelancer'

            GROUP BY
                users.id,
                users.name,
                users.email,
                freelancer_profiles.bio,
                freelancer_profiles.skills,
                freelancer_profiles.experience
            """,
            (user_id,)
        )

        freelancer = cursor.fetchone()

        if not freelancer:

            flash(
                "Freelancer not found.",
                "danger"
            )

            return redirect(
                url_for("find_freelancer")
            )

        cursor.execute(
            """
            SELECT
                reviews.rating,
                reviews.review,
                reviews.created_at,
                users.name AS client_name

            FROM reviews

            JOIN users
                ON reviews.client_id = users.id

            WHERE reviews.freelancer_id = %s

            ORDER BY reviews.created_at DESC
            """,
            (user_id,)
        )

        reviews = cursor.fetchall()

    except mysql.connector.Error as e:

        flash(
            f"Error loading freelancer profile: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "view_freelancer.html",
        freelancer=freelancer,
        reviews=reviews
    )


# =========================================================
# RATE / REVIEW FREELANCER
# =========================================================

@app.route("/review-freelancer/<int:job_id>/<int:freelancer_id>", methods=["GET", "POST"])
def review_freelancer(job_id, freelancer_id):

    # User must be logged in
    if "user_id" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    # Only clients can give reviews
    if session.get("role") != "client":
        flash("Only clients can rate freelancers.", "danger")
        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # CHECK THAT THIS JOB BELONGS TO THE LOGGED-IN CLIENT
        # AND THE FREELANCER'S APPLICATION WAS ACCEPTED
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                jobs.id AS job_id,
                jobs.title,
                jobs.client_id,
                applications.freelancer_id,
                applications.status,
                users.name AS freelancer_name

            FROM jobs

            JOIN applications
                ON jobs.id = applications.job_id

            JOIN users
                ON users.id = applications.freelancer_id

            WHERE jobs.id = %s
            AND jobs.client_id = %s
            AND applications.freelancer_id = %s
            AND applications.status = 'Accepted'
            """,
            (
                job_id,
                session["user_id"],
                freelancer_id
            )
        )

        job = cursor.fetchone()

        # Freelancer was not hired for this job
        if not job:
            flash(
                "You can only review a freelancer whose application was accepted.",
                "danger"
            )
            return redirect(url_for("dashboard"))

        # -------------------------------------------------
        # CHECK IF REVIEW ALREADY EXISTS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM reviews
            WHERE job_id = %s
            AND client_id = %s
            AND freelancer_id = %s
            """,
            (
                job_id,
                session["user_id"],
                freelancer_id
            )
        )

        existing_review = cursor.fetchone()

        # -------------------------------------------------
        # SUBMIT REVIEW
        # -------------------------------------------------

        if request.method == "POST":

            rating = request.form.get("rating")
            review = request.form.get("review", "").strip()

            # Validate rating
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                rating = 0

            if rating < 1 or rating > 5:
                flash("Please select a rating between 1 and 5 stars.", "danger")
                return render_template(
                    "review_freelancer.html",
                    job=job,
                    existing_review=existing_review
                )

            # Prevent duplicate review
            if existing_review:
                flash("You have already reviewed this freelancer for this job.", "warning")
                return redirect(
                    url_for(
                        "view_freelancer",
                        user_id=freelancer_id
                    )
                )

            # Insert review
            cursor.execute(
                """
                INSERT INTO reviews
                (
                    job_id,
                    client_id,
                    freelancer_id,
                    rating,
                    review
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    job_id,
                    session["user_id"],
                    freelancer_id,
                    rating,
                    review
                )
            )

            db.commit()

            flash("Rating and review submitted successfully! ⭐", "success")

            return redirect(
                url_for(
                    "view_freelancer",
                    user_id=freelancer_id
                )
            )

        return render_template(
            "review_freelancer.html",
            job=job,
            existing_review=existing_review
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Review error: {e}",
            "danger"
        )

        return redirect(url_for("dashboard"))

    finally:

        cursor.close()
        db.close()

# =========================================================
# CLIENT PROFILE
# =========================================================

@app.route(
    "/client-profile",
    methods=["GET", "POST"]
)
def client_profile():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can manage this profile.",
            "danger"
        )

        return redirect(url_for("dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    profile = None

    try:

        cursor.execute(
            """
            SELECT *
            FROM client_profiles
            WHERE user_id = %s
            """,
            (session["user_id"],)
        )

        profile = cursor.fetchone()

        if request.method == "POST":

            company_name = request.form.get(
                "company_name",
                ""
            ).strip()

            bio = request.form.get(
                "bio",
                ""
            ).strip()

            website = request.form.get(
                "website",
                ""
            ).strip()

            phone = request.form.get(
                "phone",
                ""
            ).strip()

            if profile:

                cursor.execute(
                    """
                    UPDATE client_profiles

                    SET
                        company_name = %s,
                        bio = %s,
                        website = %s,
                        phone = %s

                    WHERE user_id = %s
                    """,
                    (
                        company_name,
                        bio,
                        website,
                        phone,
                        session["user_id"]
                    )
                )

                flash(
                    "Client profile updated successfully!",
                    "success"
                )

            else:

                cursor.execute(
                    """
                    INSERT INTO client_profiles
                    (
                        user_id,
                        company_name,
                        bio,
                        website,
                        phone
                    )

                    VALUES
                    (%s, %s, %s, %s, %s)
                    """,
                    (
                        session["user_id"],
                        company_name,
                        bio,
                        website,
                        phone
                    )
                )

                flash(
                    "Client profile created successfully!",
                    "success"
                )

            db.commit()

            return redirect(
                url_for("client_profile")
            )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Profile error: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "client_profile.html",
        profile=profile
    )


# =========================================================
# VIEW CLIENT PROFILE
# =========================================================

@app.route("/client/<int:user_id>")
def view_client(user_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    client = None

    try:

        cursor.execute(
            """
            SELECT
                users.id,
                users.name,
                users.email,

                client_profiles.company_name,
                client_profiles.bio,
                client_profiles.website,
                client_profiles.phone

            FROM users

            LEFT JOIN client_profiles
                ON users.id = client_profiles.user_id

            WHERE users.id = %s
            AND users.role = 'client'
            """,
            (user_id,)
        )

        client = cursor.fetchone()

        if not client:

            flash(
                "Client not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

    except mysql.connector.Error as e:

        flash(
            f"Error loading client profile: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "view_client.html",
        client=client
    )


# =========================================================
# ADMIN - MANAGE USERS
# =========================================================

@app.route("/admin/users")
def admin_users():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "admin":

        flash(
            "Access denied. Admin only.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    users = []

    try:

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                role

            FROM users

            ORDER BY id DESC
            """
        )

        users = cursor.fetchall()

    except mysql.connector.Error as e:

        flash(
            f"Error loading users: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "admin_users.html",
        users=users
    )


# =========================================================
# ADMIN - MANAGE JOBS
# =========================================================

@app.route("/admin/jobs")
def admin_jobs():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "admin":

        flash(
            "Access denied. Admin only.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    jobs = []

    try:

        cursor.execute(
            """
            SELECT
                jobs.id,
                jobs.title,
                jobs.category,
                jobs.skills,
                jobs.budget,
                jobs.deadline,
                jobs.status,

                users.name AS client_name,
                users.email AS client_email

            FROM jobs

            JOIN users
                ON jobs.client_id = users.id

            ORDER BY jobs.id DESC
            """
        )

        jobs = cursor.fetchall()

    except mysql.connector.Error as e:

        flash(
            f"Error loading jobs: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "admin_jobs.html",
        jobs=jobs
    )


# =========================================================
# ADMIN - MANAGE APPLICATIONS
# =========================================================

@app.route("/admin/applications")
def admin_applications():

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "admin":

        flash(
            "Access denied. Admin only.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    applications = []

    try:

        cursor.execute(
            """
            SELECT
                applications.id AS application_id,
                applications.cover_letter,
                applications.status,
                applications.applied_at,

                jobs.id AS job_id,
                jobs.title AS job_title,

                freelancers.id AS freelancer_id,
                freelancers.name AS freelancer_name,
                freelancers.email AS freelancer_email,

                clients.id AS client_id,
                clients.name AS client_name,
                clients.email AS client_email

            FROM applications

            JOIN jobs
                ON applications.job_id = jobs.id

            JOIN users AS freelancers
                ON applications.freelancer_id = freelancers.id

            JOIN users AS clients
                ON jobs.client_id = clients.id

            ORDER BY applications.id DESC
            """
        )

        applications = cursor.fetchall()

    except mysql.connector.Error as e:

        flash(
            f"Error loading applications: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return render_template(
        "admin_applications.html",
        applications=applications
    )


# =========================================================
# ADMIN - DELETE JOB
# =========================================================

@app.route(
    "/admin/delete-job/<int:job_id>",
    methods=["POST"]
)
def admin_delete_job(job_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "admin":

        flash(
            "Access denied. Admin only.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    db = get_db_connection()
    cursor = db.cursor()

    try:

        cursor.execute(
            """
            DELETE FROM reviews
            WHERE job_id = %s
            """,
            (job_id,)
        )

        cursor.execute(
            """
            DELETE FROM applications
            WHERE job_id = %s
            """,
            (job_id,)
        )

        cursor.execute(
            """
            DELETE FROM jobs
            WHERE id = %s
            """,
            (job_id,)
        )

        db.commit()

        flash(
            "Job and related data deleted successfully!",
            "success"
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error deleting job: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return redirect(
        url_for("admin_jobs")
    )


# =========================================================
# ADMIN - DELETE USER
# =========================================================

@app.route(
    "/admin/delete-user/<int:user_id>",
    methods=["POST"]
)
def admin_delete_user(user_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "admin":

        flash(
            "Access denied. Admin only.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if user_id == session["user_id"]:

        flash(
            "You cannot delete your own admin account.",
            "danger"
        )

        return redirect(
            url_for("admin_users")
        )

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                role
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        user = cursor.fetchone()

        if not user:

            flash(
                "User not found.",
                "danger"
            )

            return redirect(
                url_for("admin_users")
            )

        # -------------------------------------------------
        # DELETE REVIEWS
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM reviews
            WHERE client_id = %s
            OR freelancer_id = %s
            """,
            (
                user_id,
                user_id
            )
        )

        # -------------------------------------------------
        # DELETE FREELANCER PROFILE
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM freelancer_profiles
            WHERE user_id = %s
            """,
            (user_id,)
        )

        # -------------------------------------------------
        # DELETE CLIENT PROFILE
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM client_profiles
            WHERE user_id = %s
            """,
            (user_id,)
        )

        # -------------------------------------------------
        # DELETE APPLICATIONS BY FREELANCER
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM applications
            WHERE freelancer_id = %s
            """,
            (user_id,)
        )

        # -------------------------------------------------
        # FIND USER JOBS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM jobs
            WHERE client_id = %s
            """,
            (user_id,)
        )

        user_jobs = cursor.fetchall()

        # -------------------------------------------------
        # DELETE APPLICATIONS & REVIEWS OF USER JOBS
        # -------------------------------------------------

        for job in user_jobs:

            cursor.execute(
                """
                DELETE FROM reviews
                WHERE job_id = %s
                """,
                (job["id"],)
            )

            cursor.execute(
                """
                DELETE FROM applications
                WHERE job_id = %s
                """,
                (job["id"],)
            )

        # -------------------------------------------------
        # DELETE USER JOBS
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM jobs
            WHERE client_id = %s
            """,
            (user_id,)
        )

        # -------------------------------------------------
        # DELETE USER
        # -------------------------------------------------

        cursor.execute(
            """
            DELETE FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        db.commit()

        flash(
            "User and related data deleted successfully!",
            "success"
        )

    except mysql.connector.Error as e:

        db.rollback()

        flash(
            f"Error deleting user: {e}",
            "danger"
        )

    finally:

        cursor.close()
        db.close()

    return redirect(
        url_for("admin_users")
    )


# =========================================================
# VIEW APPLICANTS FOR A JOB
# =========================================================

@app.route("/job/<int:job_id>/applicants")
def view_applicants(job_id):

    if "user_id" not in session:

        flash(
            "Please login first.",
            "warning"
        )

        return redirect(url_for("login"))

    if session.get("role") != "client":

        flash(
            "Only clients can view applicants.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # CHECK JOB OWNERSHIP
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                title,
                status

            FROM jobs

            WHERE id = %s
            AND client_id = %s
            """,
            (
                job_id,
                session["user_id"]
            )
        )

        job = cursor.fetchone()

        if not job:

            flash(
                "Job not found or you do not have permission to view its applicants.",
                "danger"
            )

            return redirect(
                url_for("my_jobs")
            )

        # -------------------------------------------------
        # GET APPLICANTS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT

                applications.id AS application_id,
                applications.status AS application_status,
                applications.cover_letter,
                applications.applied_at,

                users.id AS freelancer_id,
                users.name AS freelancer_name,
                users.email AS freelancer_email,

                freelancer_profiles.skills,
                freelancer_profiles.bio,
                freelancer_profiles.experience,

                COALESCE(
                    ROUND(AVG(reviews.rating), 1),
                    0
                ) AS average_rating,

                COUNT(reviews.id) AS total_reviews

            FROM applications

            JOIN users
                ON applications.freelancer_id = users.id

            LEFT JOIN freelancer_profiles
                ON users.id = freelancer_profiles.user_id

            LEFT JOIN reviews
                ON users.id = reviews.freelancer_id

            WHERE applications.job_id = %s

            GROUP BY

                applications.id,
                applications.status,
                applications.cover_letter,
                applications.applied_at,

                users.id,
                users.name,
                users.email,

                freelancer_profiles.skills,
                freelancer_profiles.bio,
                freelancer_profiles.experience

            ORDER BY applications.id DESC
            """,
            (job_id,)
        )

        applicants = cursor.fetchall()

        for applicant in applicants:

            if applicant["average_rating"] is not None:

                applicant["average_rating"] = float(
                    applicant["average_rating"]
                )

    except mysql.connector.Error as e:

        flash(
            f"Error loading applicants: {e}",
            "danger"
        )

        applicants = []
        job = None

    finally:

        cursor.close()
        db.close()

    return render_template(
        "applicants.html",
        job=job,
        applicants=applicants
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )