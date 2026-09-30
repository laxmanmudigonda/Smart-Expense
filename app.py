"""SmartExpense Flask application.

Developed with AI-assisted mentoring; the project owner should review and
understand all code before submitting it as coursework.
"""

import csv
import io
import os
import secrets
import sqlite3
from datetime import date, datetime
from pathlib import Path

import click
from flask import (
    Flask,
    Response,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import (
    escape_like,
    generate_csrf_token,
    login_required,
    parse_amount_cents,
    validate_csrf,
    validate_iso_date,
    validate_password,
    validate_username,
)


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_CATEGORIES = {
    "expense": (
        "Food & Dining",
        "Groceries",
        "Transportation",
        "Shopping",
        "Entertainment",
        "Healthcare",
        "Education",
        "Rent & Housing",
        "Utilities",
        "Travel",
        "Other Expenses",
    ),
    "income": (
        "Salary",
        "Freelancing",
        "Business",
        "Investments",
        "Gifts",
        "Other Income",
    ),
}

TRANSACTION_SORTS = {
    "date_desc": "t.transaction_date DESC, t.id DESC",
    "date_asc": "t.transaction_date ASC, t.id ASC",
    "amount_desc": "t.amount_cents DESC, t.transaction_date DESC",
    "amount_asc": "t.amount_cents ASC, t.transaction_date DESC",
}


def create_app(test_config=None):
    """Create and configure the SmartExpense Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    configured_secret = os.environ.get("SECRET_KEY")
    if os.environ.get("APP_ENV") == "production" and not configured_secret:
        raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH")
        or str(Path(app.instance_path) / "smartexpense.db"),
        CURRENCY_SYMBOL=os.environ.get("CURRENCY_SYMBOL", "₹"),
        SECRET_KEY=configured_secret or secrets.token_hex(32),
        SESSION_COOKIE_NAME="smartexpense_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=(
            os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
        ),
        MAX_CONTENT_LENGTH=1_048_576,
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    register_database(app)
    app.jinja_env.globals["csrf_token"] = generate_csrf_token
    app.jinja_env.filters["money"] = format_money

    @app.before_request
    def load_logged_in_user():
        """Load the session user, clearing stale or invalid sessions."""
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
            return

        g.user = get_db().execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if g.user is None:
            session.clear()

    @app.before_request
    def protect_state_changing_requests():
        """Require a session-bound CSRF token for every unsafe request."""
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not validate_csrf(request.form.get("csrf_token")):
                abort(400)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        if g.get("user") is not None:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def landing():
        if g.user is not None:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if g.user is not None:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirmation = request.form.get("confirmation", "")

            error = validate_username(username)
            if error is None:
                error = validate_password(password)
            if error is None and password != confirmation:
                error = "Password and confirmation must match."

            if error is None:
                try:
                    database = get_db()
                    cursor = database.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    database.commit()
                except sqlite3.IntegrityError:
                    error = "That username is already registered."
                else:
                    seed_default_categories(cursor.lastrowid)
                    database.commit()
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    flash("Your SmartExpense account is ready.", "success")
                    return redirect(url_for("dashboard"))

            flash(error, "danger")

        return render_template("register.html")

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if g.user is not None:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid username or password.", "danger")
            else:
                seed_default_categories(user["id"])
                session.clear()
                session["user_id"] = user["id"]
                flash(f"Welcome back, {user['username']}.", "success")
                return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("landing"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        selected_month, month_start, next_month = parse_month(
            request.args.get("month", "")
        )
        database = get_db()
        balance = database.execute(
            """
            SELECT COALESCE(SUM(
                CASE WHEN type = 'income' THEN amount_cents ELSE -amount_cents END
            ), 0) AS balance_cents
            FROM transactions
            WHERE user_id = ?
            """,
            (g.user["id"],),
        ).fetchone()["balance_cents"]
        monthly = database.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount_cents ELSE 0 END), 0)
                    AS income_cents,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount_cents ELSE 0 END), 0)
                    AS expense_cents
            FROM transactions
            WHERE user_id = ? AND transaction_date >= ? AND transaction_date < ?
            """,
            (g.user["id"], month_start, next_month),
        ).fetchone()
        recent_transactions = database.execute(
            """
            SELECT t.id, t.type, t.amount_cents, t.description,
                   t.transaction_date, c.name AS category_name
            FROM transactions AS t
            JOIN categories AS c ON c.id = t.category_id
            WHERE t.user_id = ?
            ORDER BY t.transaction_date DESC, t.id DESC
            LIMIT 5
            """,
            (g.user["id"],),
        ).fetchall()
        category_rows = database.execute(
            """
            SELECT c.name, SUM(t.amount_cents) AS amount_cents
            FROM transactions AS t
            JOIN categories AS c ON c.id = t.category_id
            WHERE t.user_id = ? AND t.type = 'expense'
              AND t.transaction_date >= ? AND t.transaction_date < ?
            GROUP BY c.id, c.name
            ORDER BY amount_cents DESC, c.name
            """,
            (g.user["id"], month_start, next_month),
        ).fetchall()
        total_category_spending = sum(row["amount_cents"] for row in category_rows)
        category_spending = [
            {
                "name": row["name"],
                "amount_cents": row["amount_cents"],
                "percentage": round(
                    row["amount_cents"] / total_category_spending * 100, 1
                )
                if total_category_spending
                else 0,
            }
            for row in category_rows
        ]
        budget_rows = get_budget_rows(
            g.user["id"], selected_month, month_start, next_month
        )
        budget_limit_cents = sum(row["limit_cents"] for row in budget_rows)
        budget_spent_cents = sum(row["spent_cents"] for row in budget_rows)
        budget_utilization = (
            round(budget_spent_cents / budget_limit_cents * 100, 1)
            if budget_limit_cents
            else 0
        )
        income_cents = monthly["income_cents"]
        expense_cents = monthly["expense_cents"]
        return render_template(
            "dashboard.html",
            selected_month=selected_month,
            month_label=datetime.strptime(selected_month, "%Y-%m").strftime("%B %Y"),
            balance_cents=balance,
            income_cents=income_cents,
            expense_cents=expense_cents,
            savings_cents=income_cents - expense_cents,
            recent_transactions=recent_transactions,
            category_spending=category_spending,
            budget_count=len(budget_rows),
            budget_limit_cents=budget_limit_cents,
            budget_spent_cents=budget_spent_cents,
            budget_utilization=budget_utilization,
        )

    @app.get("/transactions")
    @login_required
    def transactions():
        seed_default_categories(g.user["id"])
        database = get_db()
        rows, filters = get_filtered_transactions(g.user["id"], request.args)
        categories = database.execute(
            "SELECT id, name, type FROM categories WHERE user_id = ? ORDER BY type, name",
            (g.user["id"],),
        ).fetchall()
        return render_template(
            "transactions.html",
            transactions=rows,
            categories=categories,
            filters=filters,
        )

    @app.get("/transactions/export")
    @login_required
    def export_transactions():
        rows, filters = get_filtered_transactions(g.user["id"], request.args)
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("Date", "Type", "Category", "Description", "Amount"))
        for row in rows:
            writer.writerow(
                (
                    csv_safe(row["transaction_date"]),
                    csv_safe(row["type"].title()),
                    csv_safe(row["category_name"]),
                    csv_safe(row["description"]),
                    f"{row['amount_cents'] / 100:.2f}",
                )
            )
        filename_month = filters["date_from"][:7] if filters["date_from"] else "all"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="smartexpense-transactions-{filename_month}.csv"'
                )
            },
        )

    @app.route("/transactions/add", methods=("GET", "POST"))
    @login_required
    def add_transaction():
        seed_default_categories(g.user["id"])
        transaction = None
        if request.method == "POST":
            values, error = validate_transaction_form(g.user["id"], request.form)
            if error is None:
                database = get_db()
                database.execute(
                    """
                    INSERT INTO transactions
                        (user_id, category_id, type, amount_cents, description, transaction_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        g.user["id"],
                        values["category_id"],
                        values["type"],
                        values["amount_cents"],
                        values["description"],
                        values["transaction_date"],
                    ),
                )
                database.commit()
                flash("Transaction added.", "success")
                return redirect(url_for("transactions"))
            flash(error, "danger")

        categories = get_db().execute(
            "SELECT id, name, type FROM categories WHERE user_id = ? ORDER BY type, name",
            (g.user["id"],),
        ).fetchall()
        return render_template(
            "transaction_form.html",
            transaction=transaction,
            categories=categories,
            today=date.today().isoformat(),
        )

    @app.route("/transactions/<int:transaction_id>/edit", methods=("GET", "POST"))
    @login_required
    def edit_transaction(transaction_id):
        transaction = get_owned_transaction(transaction_id, g.user["id"])
        if transaction is None:
            abort(404)

        if request.method == "POST":
            values, error = validate_transaction_form(g.user["id"], request.form)
            if error is None:
                database = get_db()
                database.execute(
                    """
                    UPDATE transactions
                    SET category_id = ?, type = ?, amount_cents = ?, description = ?,
                        transaction_date = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        values["category_id"],
                        values["type"],
                        values["amount_cents"],
                        values["description"],
                        values["transaction_date"],
                        transaction_id,
                        g.user["id"],
                    ),
                )
                database.commit()
                flash("Transaction updated.", "success")
                return redirect(url_for("transactions"))
            flash(error, "danger")

        categories = get_db().execute(
            "SELECT id, name, type FROM categories WHERE user_id = ? ORDER BY type, name",
            (g.user["id"],),
        ).fetchall()
        return render_template(
            "transaction_form.html",
            transaction=transaction,
            categories=categories,
            today=date.today().isoformat(),
        )

    @app.post("/transactions/<int:transaction_id>/delete")
    @login_required
    def delete_transaction(transaction_id):
        cursor = get_db().execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (transaction_id, g.user["id"]),
        )
        get_db().commit()
        if cursor.rowcount == 0:
            abort(404)
        flash("Transaction deleted.", "success")
        return redirect(url_for("transactions"))

    @app.get("/categories")
    @login_required
    def categories():
        seed_default_categories(g.user["id"])
        rows = get_db().execute(
            """
            SELECT c.id, c.name, c.type, c.is_default,
                   COUNT(DISTINCT t.id) AS transaction_count,
                   COUNT(DISTINCT b.id) AS budget_count
            FROM categories AS c
            LEFT JOIN transactions AS t ON t.category_id = c.id AND t.user_id = c.user_id
            LEFT JOIN budgets AS b ON b.category_id = c.id AND b.user_id = c.user_id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.type, c.is_default DESC, c.name
            """,
            (g.user["id"],),
        ).fetchall()
        return render_template("categories.html", categories=rows)

    @app.post("/categories/add")
    @login_required
    def add_category():
        name = request.form.get("name", "").strip()
        category_type = request.form.get("type", "")
        error = validate_category(name, category_type)
        if error is None:
            try:
                database = get_db()
                database.execute(
                    "INSERT INTO categories (user_id, name, type) VALUES (?, ?, ?)",
                    (g.user["id"], name, category_type),
                )
                database.commit()
            except sqlite3.IntegrityError:
                error = "A category with that name and type already exists."
            else:
                flash("Custom category created.", "success")
                return redirect(url_for("categories"))
        flash(error, "danger")
        return redirect(url_for("categories"))

    @app.post("/categories/<int:category_id>/edit")
    @login_required
    def edit_category(category_id):
        category = get_db().execute(
            "SELECT id, type, is_default FROM categories WHERE id = ? AND user_id = ?",
            (category_id, g.user["id"]),
        ).fetchone()
        if category is None:
            abort(404)
        if category["is_default"]:
            flash("Default categories cannot be edited.", "danger")
            return redirect(url_for("categories"))

        name = request.form.get("name", "").strip()
        error = validate_category(name, category["type"])
        if error is None:
            try:
                database = get_db()
                database.execute(
                    "UPDATE categories SET name = ? WHERE id = ? AND user_id = ?",
                    (name, category_id, g.user["id"]),
                )
                database.commit()
            except sqlite3.IntegrityError:
                error = "A category with that name and type already exists."
            else:
                flash("Category updated.", "success")
                return redirect(url_for("categories"))
        flash(error, "danger")
        return redirect(url_for("categories"))

    @app.post("/categories/<int:category_id>/delete")
    @login_required
    def delete_category(category_id):
        category = get_db().execute(
            """
            SELECT c.id, c.is_default,
                   EXISTS(SELECT 1 FROM transactions t WHERE t.category_id = c.id) AS in_transactions,
                   EXISTS(SELECT 1 FROM budgets b WHERE b.category_id = c.id) AS in_budgets
            FROM categories c
            WHERE c.id = ? AND c.user_id = ?
            """,
            (category_id, g.user["id"]),
        ).fetchone()
        if category is None:
            abort(404)
        if category["is_default"]:
            flash("Default categories cannot be deleted.", "danger")
        elif category["in_transactions"] or category["in_budgets"]:
            flash("This category is in use and cannot be deleted.", "danger")
        else:
            database = get_db()
            database.execute(
                "DELETE FROM categories WHERE id = ? AND user_id = ?",
                (category_id, g.user["id"]),
            )
            database.commit()
            flash("Category deleted.", "success")
        return redirect(url_for("categories"))

    @app.get("/budgets")
    @login_required
    def budgets():
        seed_default_categories(g.user["id"])
        selected_month, month_start, next_month = parse_month(
            request.args.get("month", "")
        )
        database = get_db()
        rows = get_budget_rows(
            g.user["id"], selected_month, month_start, next_month
        )
        expense_categories = database.execute(
            """
            SELECT id, name FROM categories
            WHERE user_id = ? AND type = 'expense'
            ORDER BY name
            """,
            (g.user["id"],),
        ).fetchall()
        return render_template(
            "budgets.html",
            budgets=rows,
            expense_categories=expense_categories,
            selected_month=selected_month,
            month_label=datetime.strptime(selected_month, "%Y-%m").strftime("%B %Y"),
        )

    @app.post("/budgets/add")
    @login_required
    def add_budget():
        values, error = validate_budget_form(g.user["id"], request.form)
        if error is None:
            try:
                database = get_db()
                database.execute(
                    """
                    INSERT INTO budgets (user_id, category_id, month, limit_cents)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        g.user["id"],
                        values["category_id"],
                        values["month"],
                        values["limit_cents"],
                    ),
                )
                database.commit()
            except sqlite3.IntegrityError:
                error = "A budget for that category and month already exists."
            else:
                flash("Budget created.", "success")
                return redirect(url_for("budgets", month=values["month"]))
        flash(error, "danger")
        return redirect(url_for("budgets", month=request.form.get("month", "")))

    @app.post("/budgets/<int:budget_id>/edit")
    @login_required
    def edit_budget(budget_id):
        budget = get_db().execute(
            "SELECT id, month FROM budgets WHERE id = ? AND user_id = ?",
            (budget_id, g.user["id"]),
        ).fetchone()
        if budget is None:
            abort(404)
        try:
            limit_cents = parse_amount_cents(request.form.get("limit", ""))
        except ValueError as error:
            flash(str(error).replace("Amount", "Budget limit"), "danger")
        else:
            database = get_db()
            database.execute(
                """
                UPDATE budgets
                SET limit_cents = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                (limit_cents, budget_id, g.user["id"]),
            )
            database.commit()
            flash("Budget updated.", "success")
        return redirect(url_for("budgets", month=budget["month"]))

    @app.post("/budgets/<int:budget_id>/delete")
    @login_required
    def delete_budget(budget_id):
        budget = get_db().execute(
            "SELECT month FROM budgets WHERE id = ? AND user_id = ?",
            (budget_id, g.user["id"]),
        ).fetchone()
        if budget is None:
            abort(404)
        database = get_db()
        database.execute(
            "DELETE FROM budgets WHERE id = ? AND user_id = ?",
            (budget_id, g.user["id"]),
        )
        database.commit()
        flash("Budget deleted.", "success")
        return redirect(url_for("budgets", month=budget["month"]))

    @app.get("/analytics")
    @login_required
    def analytics():
        selected_month, _, _ = parse_month(request.args.get("month", ""))
        return render_template(
            "analytics.html",
            selected_month=selected_month,
            month_label=datetime.strptime(selected_month, "%Y-%m").strftime("%B %Y"),
        )

    @app.get("/api/analytics")
    @login_required
    def analytics_data():
        selected_month, month_start, next_month = parse_month(
            request.args.get("month", "")
        )
        months = month_sequence(selected_month, 12)
        first_month_start = f"{months[0]}-01"
        database = get_db()
        monthly_rows = database.execute(
            """
            SELECT substr(transaction_date, 1, 7) AS month,
                   SUM(CASE WHEN type = 'income' THEN amount_cents ELSE 0 END)
                       AS income_cents,
                   SUM(CASE WHEN type = 'expense' THEN amount_cents ELSE 0 END)
                       AS expense_cents
            FROM transactions
            WHERE user_id = ? AND transaction_date >= ? AND transaction_date < ?
            GROUP BY substr(transaction_date, 1, 7)
            """,
            (g.user["id"], first_month_start, next_month),
        ).fetchall()
        monthly_lookup = {row["month"]: row for row in monthly_rows}
        category_rows = database.execute(
            """
            SELECT c.name, SUM(t.amount_cents) AS amount_cents
            FROM transactions t
            JOIN categories c ON c.id = t.category_id
            WHERE t.user_id = ? AND t.type = 'expense'
              AND t.transaction_date >= ? AND t.transaction_date < ?
            GROUP BY c.id, c.name
            ORDER BY amount_cents DESC
            """,
            (g.user["id"], month_start, next_month),
        ).fetchall()
        budgets_for_month = get_budget_rows(
            g.user["id"], selected_month, month_start, next_month
        )
        return jsonify(
            {
                "currency_symbol": current_app.config["CURRENCY_SYMBOL"],
                "selected_month": selected_month,
                "monthly": {
                    "labels": [month_display_label(month) for month in months],
                    "income_cents": [
                        monthly_lookup[month]["income_cents"]
                        if month in monthly_lookup
                        else 0
                        for month in months
                    ],
                    "expense_cents": [
                        monthly_lookup[month]["expense_cents"]
                        if month in monthly_lookup
                        else 0
                        for month in months
                    ],
                },
                "categories": {
                    "labels": [row["name"] for row in category_rows],
                    "expense_cents": [row["amount_cents"] for row in category_rows],
                },
                "budgets": {
                    "labels": [row["category_name"] for row in budgets_for_month],
                    "limit_cents": [row["limit_cents"] for row in budgets_for_month],
                    "spent_cents": [row["spent_cents"] for row in budgets_for_month],
                },
            }
        )

    @app.get("/health")
    def health():
        """Small local health check used during development."""
        return {"status": "ok"}

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template("errors/500.html"), 500

    return app


def get_db():
    """Return one SQLite connection per request/application context."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def seed_default_categories(user_id):
    """Create the standard income and expense categories for one user."""
    database = get_db()
    database.executemany(
        """
        INSERT OR IGNORE INTO categories (user_id, name, type, is_default)
        VALUES (?, ?, ?, 1)
        """,
        (
            (user_id, category_name, category_type)
            for category_type, names in DEFAULT_CATEGORIES.items()
            for category_name in names
        ),
    )
    database.commit()


def get_owned_transaction(transaction_id, user_id):
    """Return a transaction only when it belongs to the active user."""
    return get_db().execute(
        """
        SELECT id, category_id, type, amount_cents, description, transaction_date
        FROM transactions
        WHERE id = ? AND user_id = ?
        """,
        (transaction_id, user_id),
    ).fetchone()


def get_filtered_transactions(user_id, query_args):
    """Return owned transactions using validated search, filter, and sort inputs."""
    filters = {
        "search": query_args.get("search", "").strip(),
        "type": query_args.get("type", ""),
        "category": query_args.get("category", ""),
        "date_from": query_args.get("date_from", ""),
        "date_to": query_args.get("date_to", ""),
        "sort": query_args.get("sort", "date_desc"),
    }
    where = ["t.user_id = ?"]
    parameters = [user_id]
    if filters["search"]:
        where.append("t.description LIKE ? ESCAPE '\\'")
        parameters.append(f"%{escape_like(filters['search'])}%")
    if filters["type"] in {"income", "expense"}:
        where.append("t.type = ?")
        parameters.append(filters["type"])
    else:
        filters["type"] = ""
    if filters["category"].isdigit():
        where.append("t.category_id = ?")
        parameters.append(int(filters["category"]))
    else:
        filters["category"] = ""
    for field, operator in (("date_from", ">="), ("date_to", "<=")):
        if filters[field]:
            try:
                filters[field] = validate_iso_date(filters[field])
            except ValueError:
                filters[field] = ""
            else:
                where.append(f"t.transaction_date {operator} ?")
                parameters.append(filters[field])
    sort_sql = TRANSACTION_SORTS.get(filters["sort"])
    if sort_sql is None:
        filters["sort"] = "date_desc"
        sort_sql = TRANSACTION_SORTS["date_desc"]
    rows = get_db().execute(
        f"""
        SELECT t.id, t.type, t.amount_cents, t.description,
               t.transaction_date, c.name AS category_name
        FROM transactions AS t
        JOIN categories AS c ON c.id = t.category_id
        WHERE {' AND '.join(where)}
        ORDER BY {sort_sql}
        """,
        parameters,
    ).fetchall()
    return rows, filters


def csv_safe(value):
    """Prevent spreadsheet applications from interpreting exported text as formulas."""
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def validate_transaction_form(user_id, form):
    """Validate transaction fields and return normalized values plus an error."""
    transaction_type = form.get("type", "")
    if transaction_type not in {"income", "expense"}:
        return None, "Choose income or expense."

    try:
        category_id = int(form.get("category_id", ""))
    except (TypeError, ValueError):
        return None, "Choose a category."

    category = get_db().execute(
        "SELECT id FROM categories WHERE id = ? AND user_id = ? AND type = ?",
        (category_id, user_id, transaction_type),
    ).fetchone()
    if category is None:
        return None, "Choose a category that matches the transaction type."

    try:
        amount_cents = parse_amount_cents(form.get("amount", ""))
        transaction_date = validate_iso_date(form.get("transaction_date", ""))
    except ValueError as error:
        return None, str(error)

    description = form.get("description", "").strip()
    if len(description) > 200:
        return None, "Description must contain no more than 200 characters."

    return {
        "category_id": category_id,
        "type": transaction_type,
        "amount_cents": amount_cents,
        "description": description,
        "transaction_date": transaction_date,
    }, None


def validate_category(name, category_type):
    """Return a category validation error or None."""
    if not name:
        return "Category name is required."
    if len(name) > 50:
        return "Category name must contain no more than 50 characters."
    if category_type not in {"income", "expense"}:
        return "Choose a valid category type."
    return None


def format_money(amount_cents):
    """Format signed integer cents with grouping and two decimal places."""
    amount_cents = int(amount_cents)
    sign = "−" if amount_cents < 0 else ""
    whole, fraction = divmod(abs(amount_cents), 100)
    return f"{sign}{whole:,}.{fraction:02d}"


def parse_month(value):
    """Return a valid YYYY-MM value and its inclusive/exclusive boundaries."""
    try:
        selected = datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        selected = date.today().replace(day=1)

    if selected.month == 12:
        following = selected.replace(year=selected.year + 1, month=1)
    else:
        following = selected.replace(month=selected.month + 1)
    return selected.strftime("%Y-%m"), selected.isoformat(), following.isoformat()


def month_sequence(end_month, count):
    """Return canonical months ending at end_month, oldest first."""
    end = datetime.strptime(end_month, "%Y-%m")
    end_index = end.year * 12 + end.month - 1
    result = []
    for offset in range(count - 1, -1, -1):
        year, zero_based_month = divmod(end_index - offset, 12)
        result.append(f"{year:04d}-{zero_based_month + 1:02d}")
    return result


def month_display_label(month):
    """Format YYYY-MM for compact analytics chart labels."""
    return datetime.strptime(month, "%Y-%m").strftime("%b %Y")


def validate_month(value):
    """Return a canonical budget month or raise a user-facing error."""
    try:
        selected = datetime.strptime(value, "%Y-%m")
    except (TypeError, ValueError):
        raise ValueError("Choose a valid budget month.") from None
    canonical = selected.strftime("%Y-%m")
    if value != canonical:
        raise ValueError("Choose a valid budget month.")
    return canonical


def validate_budget_form(user_id, form):
    """Validate a new budget and its owned expense category."""
    try:
        category_id = int(form.get("category_id", ""))
    except (TypeError, ValueError):
        return None, "Choose an expense category."
    category = get_db().execute(
        """
        SELECT id FROM categories
        WHERE id = ? AND user_id = ? AND type = 'expense'
        """,
        (category_id, user_id),
    ).fetchone()
    if category is None:
        return None, "Choose one of your expense categories."
    try:
        month = validate_month(form.get("month", ""))
        limit_cents = parse_amount_cents(form.get("limit", ""))
    except ValueError as error:
        return None, str(error).replace("Amount", "Budget limit")
    return {
        "category_id": category_id,
        "month": month,
        "limit_cents": limit_cents,
    }, None


def get_budget_rows(user_id, month, month_start, next_month):
    """Return budgets enriched with spending, remaining value, and utilization."""
    rows = get_db().execute(
        """
        SELECT b.id, b.category_id, b.month, b.limit_cents, c.name AS category_name,
               COALESCE(SUM(t.amount_cents), 0) AS spent_cents
        FROM budgets AS b
        JOIN categories AS c ON c.id = b.category_id
        LEFT JOIN transactions AS t
          ON t.user_id = b.user_id
         AND t.category_id = b.category_id
         AND t.type = 'expense'
         AND t.transaction_date >= ?
         AND t.transaction_date < ?
        WHERE b.user_id = ? AND b.month = ?
        GROUP BY b.id, c.name
        ORDER BY c.name
        """,
        (month_start, next_month, user_id, month),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "category_id": row["category_id"],
            "month": row["month"],
            "category_name": row["category_name"],
            "limit_cents": row["limit_cents"],
            "spent_cents": row["spent_cents"],
            "remaining_cents": row["limit_cents"] - row["spent_cents"],
            "utilization": round(row["spent_cents"] / row["limit_cents"] * 100, 1),
            "progress_width": min(
                round(row["spent_cents"] / row["limit_cents"] * 100, 1), 100
            ),
        }
        for row in rows
    ]


def close_db(error=None):
    """Close the request's database connection, if one was opened."""
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db():
    """Create an empty database from the checked-in schema."""
    database = get_db()
    schema_path = BASE_DIR / "schema.sql"
    database.executescript(schema_path.read_text(encoding="utf-8"))


@click.command("init-db")
def init_db_command():
    """Initialize the configured SQLite database."""
    init_db()
    click.echo("Initialized the SmartExpense database.")


def register_database(app):
    """Register database cleanup and the Flask CLI command."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


app = create_app()


if __name__ == "__main__":
    app.run()
