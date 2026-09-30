# SmartExpense — Personal Finance Manager

**CS50x Final Project**  
**Video demonstration:** TODO — add the final video URL before submission

SmartExpense is a full-stack personal finance application built with Flask and SQLite. It lets users record income and expenses, organize categories, create monthly budgets, inspect a live dashboard, and explore trends through charts. It requires no external service or paid infrastructure beyond loading the Bootstrap and Chart.js browser libraries.

## Problem and purpose

Personal spending is difficult to understand when transactions are scattered across receipts, bank applications, and memory. A list of purchases alone does not answer practical questions such as “How much did I save this month?”, “Which category consumes most of my income?”, or “Am I about to exceed my food budget?” SmartExpense converts transaction records into monthly summaries, category totals, budget warnings, and historical trends. Every calculation uses the authenticated user’s SQLite records; the interface never substitutes demonstration values for missing data.

## Features

- Account registration, login, logout, password hashing, and private sessions
- CSRF protection for every state-changing form
- Income and expense creation, editing, and deletion
- Positive integer-cent money storage to avoid floating-point database errors
- Seventeen default income and expense categories plus custom category management
- Transaction search, type/category/date filters, and date/amount sorting
- A dashboard showing all-time balance, monthly income, expenses, savings, recent transactions, category spending, and overall budget utilization
- Month-specific category budgets with remaining values, progress indicators, and overspending warnings
- Four Chart.js analytics views: income versus expenses, monthly spending trend, category distribution, and budget utilization
- Filter-aware CSV export with spreadsheet-formula injection protection
- Helpful empty states, flash messages, responsive tables, and mobile navigation

The currency symbol defaults to `₹` and can be changed using the `CURRENCY_SYMBOL` environment variable.

## Technology and architecture

The backend uses Python 3, Flask, Jinja, Werkzeug password hashing, Python’s built-in `sqlite3` module, and signed Flask sessions. The frontend uses semantic HTML, custom CSS, Bootstrap 5, vanilla JavaScript, and Chart.js. Automated tests use pytest and Flask’s test client with a fresh temporary SQLite database for every test.

`create_app()` is an application factory. Tests can therefore provide a temporary database and secret without modifying production code. SQLite connections are opened once per Flask application context, configured with row objects and foreign-key enforcement, and closed automatically. Routes always include the logged-in user ID in user-owned reads and mutations. The analytics endpoint returns only the current user’s aggregated records as JSON.

## Database design

The `users` table stores a case-insensitive unique username and a password hash—never a plaintext password. `categories` belongs to a user and distinguishes income from expense categories. `transactions` stores a positive `amount_cents`; its type determines whether it increases or decreases balance. `budgets` connects one expense category to one canonical `YYYY-MM` month and a positive limit in cents.

Foreign keys prevent orphaned rows. Check constraints validate transaction types, positive amounts, dates, and month formats. A unique constraint prevents duplicate budgets for the same user, category, and month. Indexes support user/date transaction history, category spending, and monthly budget queries. Application validation additionally ensures that selected categories belong to the active user and match the required type.

## Important files

```text
Smart Expense/
├── app.py                   Flask factory, routes, database queries, and CLI
├── helpers.py               Authentication, CSRF, money, date, and validation helpers
├── schema.sql               Tables, constraints, foreign keys, and indexes
├── requirements.txt         Minimal Python dependencies
├── static/
│   ├── css/styles.css       Responsive visual system
│   └── js/                  Transaction-form behavior and Chart.js setup
├── templates/               Shared layout and page/error templates
├── tests/                   Authentication, transaction, budget, dashboard,
│                            analytics, export, and security tests
└── instance/                Local database; excluded from Git
```

`app.py` deliberately keeps the core SQL near the route using it, making the data flow approachable for a CS50 project. `helpers.py` contains focused logic that is reused across routes. `schema.sql` is checked into Git so a clean database can be reproduced with one command.

## Installation and running

Python 3.11 or newer is recommended. In Windows PowerShell:

```powershell
cd "C:\Documents\Smart Expense"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app:create_app init-db
python -m flask --app app:create_app run --debug
```

Open `http://127.0.0.1:5000/`. Run `init-db` only when creating a new database; it uses `CREATE TABLE IF NOT EXISTS` and does not seed fake financial records. For production, set `APP_ENV=production`, provide a long random `SECRET_KEY`, enable `SESSION_COOKIE_SECURE` behind HTTPS, and do not use Flask’s development server. `.env.example` documents the supported environment values.

## Testing

Run the complete suite from the activated environment:

```powershell
python -m pytest -q
```

Tests cover registration, duplicate usernames, credential failures, logout, CSRF, password hashing, transaction validation and ownership, amount conversion, category rules, dashboard calculations, monthly boundaries, budget uniqueness and overages, analytics JSON, CSV safety, unauthenticated access, security headers, and cross-user isolation.

## Design decisions and security

Money is parsed from a restricted decimal string and converted to cents before reaching SQLite. Month queries use an inclusive first day and exclusive first day of the next month, avoiding month-length and timestamp boundary bugs. SQL parameters are used for all submitted values; transaction sorting selects only from a fixed whitelist. Destructive actions require POST plus a session-bound CSRF token. Login failures use a generic message, Jinja escapes displayed values, responses deny framing and MIME sniffing, and authenticated pages disable browser caching.

## Limitations and future improvements

SmartExpense currently supports one currency symbol per running installation, not currency conversion or per-account currencies. It has no password-reset email, recurring transactions, bank synchronization, receipt uploads, pagination, or hosted deployment. Possible future work includes recurring entries, import workflows, savings goals, encrypted backups, accessibility testing with assistive technology, and optional deployment with persistent storage.

## AI assistance acknowledgment

AI was used as a mentoring and pair-programming aid for architecture discussion, implementation suggestions, debugging, tests, security review, and documentation. The project owner is responsible for reviewing and understanding the code, verifying the final behavior, and accurately describing this assistance in the CS50 submission. No CS50 Finance distribution solution was copied into this project.
